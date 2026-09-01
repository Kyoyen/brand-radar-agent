"""
Agent Runner — 多场景路由引擎
================================
用自然语言描述任务，自动识别场景、加载工具、执行 ReAct 循环。
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .context_manager import ContextManager
from .session_summarizer import SessionSummarizer
from .llm_client import LLMClient
from .output_schema import AgentOutput, get_schema_prompt

load_dotenv()
console = Console()

REGISTRY_PATH = Path(__file__).parent / "scenario_registry.json"
MAX_TURNS_DEFAULT = int(os.getenv("AGENT_MAX_TURNS", 12))
MARKETING_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills" / "brand-radar"
MAX_MARKETING_SKILL_BYTES = 16 * 1024
MARKETING_SKILL_NAMES = (
    "signal-triage",
    "brand-fit",
    "brief-distillation",
)
_MARKETING_SKILL_METADATA_FIELDS = frozenset({"name", "description"})
_MARKETING_SKILL_NAME_PATTERN = re.compile(r"[a-z]+(?:-[a-z]+)*")
_MARKETING_SKILL_RESERVED_SCALAR_STARTS = frozenset("-?:,[]{}#&*!|>@`\"'")
_MARKETING_SKILL_METADATA_SUBSET = (
    "只支持 name 和 description 两个单行字段（可穿插空行或 # 注释）；"
    "name 必须是小写 kebab-case，description 必须是非空的无引号纯文本"
)


@dataclass(frozen=True)
class _MarketingSkill:
    """A small, local-only marketing skill used by the weekly Agent loop."""

    name: str
    description: str
    content: str


def _parse_marketing_skill(skill_path: Path) -> _MarketingSkill:
    """Read a strict, YAML-compatible single-line metadata subset.

    The subset accepts only ``name`` and ``description`` fields plus blank or
    comment lines.  It intentionally excludes YAML sequences, mappings,
    anchors, aliases and quoted scalars so this dependency-free parser has one
    unambiguous contract.
    """
    def metadata_error(message: str) -> ValueError:
        return ValueError(
            f"营销技能 front matter {message}；"
            f"{_MARKETING_SKILL_METADATA_SUBSET}：{skill_path}"
        )

    size = skill_path.stat().st_size
    if size > MAX_MARKETING_SKILL_BYTES:
        raise ValueError(
            f"营销技能文件大小超出 {MAX_MARKETING_SKILL_BYTES} bytes 限制：{skill_path}"
        )
    text = skill_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise metadata_error("缺少 YAML front matter")
    closing_marker = text.find("\n---\n", 4)
    if closing_marker == -1:
        raise metadata_error("未闭合")

    metadata: dict[str, str] = {}
    for line in text[4:closing_marker].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        matched = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)", line)
        if not matched:
            raise metadata_error("格式无效")
        key, value = matched.groups()
        if key not in _MARKETING_SKILL_METADATA_FIELDS:
            raise metadata_error(f"不支持字段 {key}")
        if key in metadata:
            raise metadata_error(f"重复字段 {key}")
        metadata[key] = value

    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not _MARKETING_SKILL_NAME_PATTERN.fullmatch(name):
        raise metadata_error("name 必须是非空小写 kebab-case")
    if (
        not description
        or description != description.strip()
        or description[0] in _MARKETING_SKILL_RESERVED_SCALAR_STARTS
        or any(character in description for character in "\"'[]{}")
        or re.search(r":\s|(?:^|\s)#", description)
    ):
        raise metadata_error("description 必须是非空单行纯文本")
    content = text[closing_marker + len("\n---\n"):].strip()
    if not content:
        raise ValueError(f"营销技能正文不能为空：{skill_path}")
    return _MarketingSkill(name=name, description=description, content=content)


def _load_marketing_skills(
    skills_dir: str | Path = MARKETING_SKILLS_DIR,
) -> tuple[_MarketingSkill, ...]:
    """Load only one-level Brand Radar skills and fail closed on malformed input."""
    root = Path(skills_dir)
    if not root.is_dir():
        raise ValueError(f"营销技能目录不存在：{root}")
    skill_paths = sorted(root.glob("*/SKILL.md"))
    if not skill_paths:
        raise ValueError(f"营销技能目录为空：{root}")
    skills = tuple(_parse_marketing_skill(path) for path in skill_paths)
    names = [skill.name for skill in skills]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"营销技能存在重复技能 name：{', '.join(duplicates)}")
    return skills


def _marketing_skills_by_name(
    skills_dir: str | Path = MARKETING_SKILLS_DIR,
) -> dict[str, _MarketingSkill]:
    skills = _load_marketing_skills(skills_dir)
    by_name = {skill.name: skill for skill in skills}
    actual_names = set(by_name)
    expected_names = set(MARKETING_SKILL_NAMES)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        details = []
        if missing:
            details.append(f"缺少：{', '.join(missing)}")
        if unexpected:
            details.append(f"不支持：{', '.join(unexpected)}")
        raise ValueError("营销技能目录名称不符合约定（" + "；".join(details) + "）")
    return by_name


def get_marketing_skill_catalog(
    skills_dir: str | Path = MARKETING_SKILLS_DIR,
) -> list[dict[str, str]]:
    """Return the first-turn directory without leaking any skill body text."""
    by_name = _marketing_skills_by_name(skills_dir)
    return [
        {"name": name, "description": by_name[name].description}
        for name in MARKETING_SKILL_NAMES
    ]


def get_marketing_skill_content(
    name: str,
    skills_dir: str | Path = MARKETING_SKILLS_DIR,
) -> str:
    """Return full instructions only after a valid catalog name has been selected."""
    by_name = _marketing_skills_by_name(skills_dir)
    skill = by_name.get(name)
    if skill is None:
        raise ValueError(f"未知营销技能：{name}")
    return skill.content

class _StrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


InvestigationAction = Literal[
    "inspect_local_evidence",
    "compare_event_versions",
    "compare_competitor_evidence",
    "cross_check_conflicting_evidence",
]


class _InvestigationDecision(_StrictResponse):
    decision: Literal["investigate", "generate"]
    skill_name: Literal[
        "signal-triage",
        "brand-fit",
        "brief-distillation",
    ]
    objective: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    action_type: InvestigationAction | None = None
    arguments: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_decision_shape(self):
        if self.decision == "investigate":
            if self.action_type is None:
                raise ValueError("investigate 决策必须包含一个白名单动作")
            if not self.arguments:
                raise ValueError("investigate 决策必须包含动作参数")
        elif self.action_type is not None or self.arguments:
            raise ValueError("generate 决策不得包含动作或动作参数")
        return self


class _AdjustmentDraft(_StrictResponse):
    adjustment_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    feedback_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class _GenerationResponse(_StrictResponse):
    adjustment_reasons: list[_AdjustmentDraft] = Field(min_length=1, max_length=4)
    result: dict[str, Any]

# 全局营销方法论约束 — 注入所有场景的 system prompt
# 避免 LLM 在数据稀疏时编造，并强制把数据加工成商业判断
UNIVERSAL_METHODOLOGY = """=== 全局方法论约束 ===
1. 拒绝幻觉：所有定性/定量判断必须 100% 来自工具返回数据，不可编造数据、KPI、热榜
2. 洞察商业机会：不止搬运数据，必须加工为「品牌商业机会」或「风险警示」
3. 专业客观：资深分析师口吻，无套话、无热情服务话术，直接抛业务结论
"""


class AgentRunner:
    def __init__(
        self,
        require_api: bool = False,
        llm: LLMClient | None = None,
        *,
        brand_file: str | Path | None = None,
        runtime_agents_file: str | Path | None = None,
        skills_dir: str | Path = MARKETING_SKILLS_DIR,
    ):
        self.llm        = llm or LLMClient(require_api=require_api)
        self.registry   = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.summarizer = SessionSummarizer()
        self.brand_file = Path(brand_file).expanduser() if brand_file is not None else None
        self.runtime_agents_file = (
            Path(runtime_agents_file).expanduser()
            if runtime_agents_file is not None
            else Path(__file__).resolve().parents[1] / "agent" / "AGENTS.md"
        )
        self.skills_dir = Path(skills_dir).expanduser()
        console.print(f"  [dim]LLM: {self.llm}[/dim]")

    # ── 场景列表 ──────────────────────────────────────────────────────────────

    def list_scenarios(self):
        t = Table(title="营销 Agent OS — 可用场景", show_lines=True)
        t.add_column("场景ID", style="cyan", width=22)
        t.add_column("名称", width=16)
        t.add_column("适用情况", width=38)
        t.add_column("预计耗时", width=8)
        t.add_column("配置估算*", width=10)
        for sid, sc in self.registry["scenarios"].items():
            t.add_row(sid, sc["name"], sc["description"][:36]+"...",
                      f"~{sc['estimated_duration_min']}min",
                      f"~{sc['roi_metrics']['time_saved_hours_per_week']}h")
        console.print(t)
        console.print("[dim]* 来自场景配置的规划假设，尚未经过人工基线与真实使用验证。[/dim]")

    def show_roi_summary(self):
        total = sum(sc["roi_metrics"]["time_saved_hours_per_week"]
                    for sc in self.registry["scenarios"].values())
        console.print(Panel(
            "[bold]以下为场景配置中的未验证工时假设，不是实测提效或 ROI。[/bold]\n\n" +
            f"配置合计：~{total}h/周（待建立人工基线）\n" +
            "\n".join(f"• {sc['name']}：假设 ~{sc['roi_metrics']['time_saved_hours_per_week']}h/周"
                      for sc in self.registry["scenarios"].values()),
            title="规划估算（未验证）", border_style="yellow",
        ))

    # ── 自动路由 ──────────────────────────────────────────────────────────────

    def _detect_scenario(self, task: str) -> str:
        """场景路由：优先关键词命中（零 token 消耗），fallback 到 LLM。"""
        task_lower = task.lower()
        for sid, sc in self.registry["scenarios"].items():
            if any(kw in task_lower for kw in sc["trigger_keywords"]):
                console.print(f"  [dim]场景识别：关键词 → [cyan]{sid}[/cyan][/dim]")
                return sid

        # LLM fallback：只输出 ID，30 tokens 内即可
        scenario_list = "\n".join(f"- {sid}: {sc['name']}"
                                   for sid, sc in self.registry["scenarios"].items())
        resp = self.llm.chat(
            messages=[
                {"role": "system", "content": f"从下列场景选 1 个最匹配的ID，只回 ID 无其他：\n{scenario_list}"},
                {"role": "user",   "content": task},
            ],
            temperature=0, max_tokens=20,
        )
        detected = (resp.choices[0].message.content or "").strip()
        if detected in self.registry["scenarios"]:
            console.print(f"  [dim]场景识别：LLM → [cyan]{detected}[/cyan][/dim]")
            return detected

        console.print("  [dim]场景识别：默认 → competitive_analysis[/dim]")
        return "competitive_analysis"

    # ── 工具加载 ──────────────────────────────────────────────────────────────

    def _load_tools(self, scenario_id: str, weekly_runtime=None):
        from v3_agent.tools import TOOLS as base_tools, execute_tool as base_exec
        try:
            from scenarios.tools_extended import EXTENDED_TOOLS, execute_extended_tool
        except ImportError:
            EXTENDED_TOOLS, execute_extended_tool = [], None
        try:
            from scenarios.tools_real import REAL_TOOLS, execute_real_tool
        except ImportError:
            REAL_TOOLS, execute_real_tool = [], None
        try:
            from scenarios.brand_radar_weekly import WEEKLY_TOOLS, execute_weekly_tool
        except ImportError:
            WEEKLY_TOOLS, execute_weekly_tool = [], None

        required = set(self.registry["scenarios"][scenario_id]["tools"])
        all_tools = base_tools + EXTENDED_TOOLS + REAL_TOOLS + WEEKLY_TOOLS
        tools = [t for t in all_tools if t["function"]["name"] in required]

        # 工具来源映射，按名查找 → 调用对应 executor
        tool_routes = {}
        for t in base_tools:     tool_routes[t["function"]["name"]] = ("base", base_exec)
        for t in EXTENDED_TOOLS: tool_routes[t["function"]["name"]] = ("ext",  execute_extended_tool)
        for t in REAL_TOOLS:     tool_routes[t["function"]["name"]] = ("real", execute_real_tool)
        for t in WEEKLY_TOOLS:
            executor = None
            if weekly_runtime is not None and execute_weekly_tool is not None:
                executor = lambda name, args: execute_weekly_tool(weekly_runtime, name, args)
            tool_routes[t["function"]["name"]] = ("weekly", executor)

        def execute(name, args):
            route = tool_routes.get(name)
            if not route or not route[1]:
                return json.dumps({"error": f"工具 {name} 不可用"}, ensure_ascii=False)
            return route[1](name, args)

        return tools, execute

    # ── ReAct 主循环 ──────────────────────────────────────────────────────────

    def run(self, scenario_id: str, task_description: str = "", **kwargs) -> str:
        if scenario_id == "brand_radar_weekly":
            source_pack = kwargs.pop(
                "source_pack",
                Path(__file__).parent.parent / "data/replay/coffee-week-2026-09-07/manifest.json",
            )
            output, output_path = self.run_weekly(
                source_pack=source_pack,
                task_description=task_description,
            )
            console.print(f"  [dim]结果：{output_path}[/dim]")
            return output.model_dump_json(indent=2)

        sc = self.registry["scenarios"][scenario_id]
        task_description = task_description or sc["name"]

        console.print(Panel(
            f"[bold]{sc['name']}[/bold]\n[dim]{task_description}[/dim]",
            title=f"🤖 {scenario_id}", border_style="cyan",
        ))

        ctx = ContextManager(scenario_id, task_description)

        # 注入历史记忆 + 执行经验
        history    = ctx.load_relevant_history(limit=2)
        experience = self.summarizer.recall_experience(scenario_id, task_description, limit=2)
        extra_ctx  = ("\n\n" + history if history else "") + ("\n\n" + experience if experience else "")

        brand = kwargs.get("brand", os.getenv("TARGET_BRAND", "品牌方"))
        system_content = (
            UNIVERSAL_METHODOLOGY + "\n\n"
            + sc["system_prompt"].format(brand=brand, our_brand=brand, **{
                k: v for k, v in kwargs.items() if k not in ("brand","our_brand")
            })
            + extra_ctx
            + "\n\n" + get_schema_prompt()
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": f"请执行：{task_description}\n参数：{kwargs}"},
        ]

        tools, execute_tool = self._load_tools(scenario_id)
        max_turns        = sc.get("max_turns", MAX_TURNS_DEFAULT)
        checkpoint_every = sc.get("checkpoint_every", 5)
        final_output     = ""
        # ReAct 防死循环：同一工具+同一参数最多调用 2 次
        call_signatures  = {}

        for turn in range(1, max_turns + 1):
            with console.status(f"[cyan]第 {turn} 轮推理...[/cyan]"):
                response = self.llm.chat(messages=messages, tools=tools or None, temperature=0.2)

            msg = response.choices[0].message
            messages.append(msg)

            if response.choices[0].finish_reason == "stop":
                raw = msg.content or "完成。"
                final_output = self._parse_structured(raw, scenario_id, task_description)
                console.print(f"\n[green]✓ 完成（{turn}轮 / {ctx.tool_call_count}次工具调用）[/green]")
                break

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments)

                    # 去重：同 name+args 出现第 3 次直接返回提示，逼 Agent 收敛
                    sig = f"{name}::{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
                    call_signatures[sig] = call_signatures.get(sig, 0) + 1
                    if call_signatures[sig] > 2:
                        console.print(f"  [red]✗ 工具 {name} 重复调用 >2 次，强制中断本工具[/red]")
                        result = json.dumps({
                            "warning": "重复调用，请基于已有数据生成最终结论，不要再调用此工具",
                            "tool": name,
                        }, ensure_ascii=False)
                    else:
                        console.print(f"  [yellow]→[/yellow] [bold]{name}[/bold]  {args}")
                        result = execute_tool(name, args)

                    ctx.record_tool_call()
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

                if ctx.should_checkpoint():
                    messages = ctx.compress(messages)
        else:
            final_output = "已达最大轮次，任务可能未完全完成。"

        # 持久化记忆 + 沉淀经验
        ctx.save_session(final_output, {"scenario_id": scenario_id, "tool_calls": ctx.tool_call_count})
        try:
            fp = self.summarizer.save_experience(scenario_id, task_description, final_output, messages)
            console.print(f"  [dim]经验已归档：{fp.name}[/dim]")
        except Exception as e:
            console.print(f"  [dim yellow]经验归档跳过：{e}[/dim yellow]")

        return final_output

    def run_auto(self, task: str, **kwargs) -> str:
        return self.run(self._detect_scenario(task), task_description=task, **kwargs)

    # ── Brand Radar weekly 单场景 ────────────────────────────────────────────

    @staticmethod
    def _decode_json_object(raw: str, label: str) -> dict[str, Any]:
        candidate = (raw or "").strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if len(lines) < 3 or lines[-1].strip() != "```":
                raise ValueError(f"{label}不是完整的 JSON 代码围栏")
            candidate = "\n".join(lines[1:-1]).strip()
        try:
            decoded = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{label}不是有效 JSON（line {exc.lineno}, column {exc.colno}）"
            ) from exc
        if not isinstance(decoded, dict):
            raise ValueError(f"{label}顶层必须是 JSON 对象")
        return decoded

    @classmethod
    def _parse_investigation_decision(cls, raw: str) -> _InvestigationDecision:
        try:
            return _InvestigationDecision.model_validate(
                cls._decode_json_object(raw, "调查决策")
            )
        except (ValueError, ValidationError) as exc:
            raise RuntimeError(f"调查决策无效：{exc}") from exc

    @staticmethod
    def _validation_error(message: str, issues: list[dict[str, str]]):
        from .brand_radar_output import BrandRadarValidationError

        return BrandRadarValidationError(message, issues=issues)

    @classmethod
    def _parse_generation_response(
        cls,
        raw: str,
        *,
        selected_actions: list[dict[str, Any]],
        tool_feedback: list[dict[str, Any]],
    ) -> _GenerationResponse:
        try:
            generated = _GenerationResponse.model_validate(
                cls._decode_json_object(raw, "企划生成结果")
            )
        except (ValueError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                issues = [
                    {
                        "location": ".".join(str(part) for part in item["loc"]) or "result",
                        "message": item["msg"],
                        "type": item["type"],
                    }
                    for item in exc.errors(include_input=False)
                ]
            else:
                issues = [
                    {
                        "location": "generation_response",
                        "message": str(exc),
                        "type": "invalid_json",
                    }
            ]
            raise cls._validation_error("企划生成结果结构无效", issues) from exc

        action_ids = [item["action_id"] for item in selected_actions]
        feedback_by_action = {
            item["action_id"]: item["feedback_id"] for item in tool_feedback
        }
        adjustments = generated.adjustment_reasons
        adjustment_ids = [item.adjustment_id for item in adjustments]
        adjusted_actions = [item.action_id for item in adjustments]
        issues: list[dict[str, str]] = []
        if len(adjustment_ids) != len(set(adjustment_ids)):
            issues.append(
                {
                    "location": "adjustment_reasons.adjustment_id",
                    "message": "adjustment_id 必须唯一",
                    "type": "duplicate_id",
                }
            )
        if sorted(adjusted_actions) != sorted(action_ids):
            issues.append(
                {
                    "location": "adjustment_reasons.action_id",
                    "message": "每个实际调查动作必须恰好有一条调整理由",
                    "type": "cross_reference",
                }
            )
        for index, item in enumerate(adjustments):
            expected_feedback = feedback_by_action.get(item.action_id)
            if expected_feedback is not None and item.feedback_id != expected_feedback:
                issues.append(
                    {
                        "location": f"adjustment_reasons.{index}.feedback_id",
                        "message": "feedback_id 必须引用该动作的真实工具反馈",
                        "type": "cross_reference",
                    }
                )
        if issues:
            raise cls._validation_error("企划生成结果没有正确回应调查反馈", issues)
        return generated

    @staticmethod
    def _error_issues(error: Exception) -> list[dict[str, str]]:
        issues = getattr(error, "issues", None)
        if isinstance(issues, (list, tuple)) and issues:
            return [
                item.as_dict() if hasattr(item, "as_dict") else dict(item)
                for item in issues
            ]
        return [
            {
                "location": "result",
                "message": str(error),
                "type": "brand_radar_validation_error",
            }
        ]

    @staticmethod
    def _goal_snapshot(settings: dict[str, Any], task_description: str) -> dict[str, Any]:
        return {
            "brand": settings["brand"],
            "category": settings["category"],
            "regions": settings["regions"],
            "competitors": settings["competitors"],
            "keywords": settings["keywords"],
            "business_question": task_description,
        }

    @staticmethod
    def _execute_investigation_decision(
        runtime,
        decision: _InvestigationDecision,
        action_index: int,
    ):
        from scenarios.brand_radar_weekly import WeeklyPipelineError

        if decision.action_type is None:
            raise WeeklyPipelineError("investigate 决策缺少调查动作")
        result = runtime.execute_investigation_action(
            decision.action_type,
            decision.arguments,
        )
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError as exc:
                raise WeeklyPipelineError(
                    f"调查动作 {decision.action_type} 返回无效 JSON"
                ) from exc
        if not isinstance(result, dict):
            raise WeeklyPipelineError(
                f"调查动作 {decision.action_type} 返回结果无效"
            )
        if result.get("error"):
            raise WeeklyPipelineError(str(result["error"]))

        step_id = f"step-{action_index}"
        action_id = f"action-{action_index}"
        source_ids = result.get("source_ids", [])
        plan_step = {
            "step_id": step_id,
            "objective": decision.objective,
        }
        selected_action = {
            "action_id": action_id,
            "step_id": step_id,
            "action_type": decision.action_type,
            "reason": decision.reason,
            "arguments": decision.arguments,
            "source_ids": source_ids,
        }
        tool_feedback = {
            "feedback_id": f"feedback-{action_id}",
            "action_id": action_id,
            "source_ids": source_ids,
            "summary": result.get("summary", "调查动作已完成"),
            "outcome": result.get("outcome", "completed"),
            "decision_hint": result.get(
                "decision_hint", "根据实际来源充分度保守判断"
            ),
        }
        return plan_step, selected_action, tool_feedback

    def run_weekly(self, source_pack: str | Path, task_description: str = "",
                   output_dir: str | Path | None = None):
        """Run the bounded single-Agent Replay loop and return its reviewed artifact.

        The legacy context/experience writers are intentionally not used here:
        the validated JSON artifact is the single run record for this scenario.
        """
        from scenarios.brand_radar_weekly import (
            INVESTIGATION_TOOLS,
            MAX_INVESTIGATION_ACTIONS,
            WEEKLY_TOOL_ORDER,
            WeeklyPipelineError,
            WeeklyScenarioRuntime,
        )
        from .brand_profile import load_brand_profile
        from .brand_radar_output import (
            BrandRadarValidationError,
            get_brand_radar_result_contract,
            parse_brand_radar_output,
            validate_investigation_preflight,
            validate_investigation_trace,
        )

        started_at = datetime.now(timezone.utc).isoformat()
        runtime = WeeklyScenarioRuntime(source_pack)
        tools, execute_tool = self._load_tools("brand_radar_weekly", weekly_runtime=runtime)
        tool_names = tuple(tool["function"]["name"] for tool in tools)
        if tool_names != WEEKLY_TOOL_ORDER:
            raise WeeklyPipelineError(
                "brand_radar_weekly 工具注册与固定阶段不一致："
                f"expected={WEEKLY_TOOL_ORDER}, actual={tool_names}"
            )

        for tool_name in tool_names:
            encoded = execute_tool(tool_name, {})
            try:
                result = json.loads(encoded)
            except json.JSONDecodeError as exc:
                raise WeeklyPipelineError(f"工具 {tool_name} 返回了无效 JSON") from exc
            if isinstance(result, dict) and result.get("error"):
                raise WeeklyPipelineError(result["error"])

        sc = self.registry["scenarios"]["brand_radar_weekly"]
        task_description = task_description or runtime.settings["business_question"]
        goal_snapshot = self._goal_snapshot(runtime.settings, task_description)
        try:
            brand_profile = load_brand_profile(self.brand_file)
            runtime_rules = self.runtime_agents_file.read_text(encoding="utf-8")
            skill_catalog = get_marketing_skill_catalog(self.skills_dir)
        except (OSError, UnicodeError, ValueError) as exc:
            raise WeeklyPipelineError(f"品牌或 Agent 运行上下文无法加载：{exc}") from exc

        repo_root = Path(__file__).resolve().parents[1]
        try:
            brand_display_file = brand_profile.path.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            brand_display_file = str(brand_profile.path)
        brand_run_info = {
            "mode": brand_profile.mode,
            "file": brand_display_file,
            "answered_questions": brand_profile.answered_questions,
            "fingerprint": brand_profile.fingerprint,
        }
        selected_skill_bodies: dict[str, str] = {}
        generation_contract = (
            "【唯一允许的生成结构】\n"
            "外层顶级字段只能是 adjustment_reasons 和 result，不能直接输出 result 的六个字段。\n"
            "adjustment_reasons 中每项必须包含 adjustment_id、action_id、feedback_id、reason；"
            "result 中必须包含 executive_summary、intelligence_cards、calendar、keywords、briefs、human_review。\n"
            "只输出 JSON 对象，不要 Markdown 或解释文字。\n\n"
            "【外层层级示意（不是可复制的数据样例）】\n"
            "根对象.adjustment_reasons：数组，每个已执行动作恰好一项。\n"
            "根对象.result：对象，承载下方完整且非空的周企划字段。\n\n"
            "【外层 JSON Schema】\n"
            + json.dumps(
                _GenerationResponse.model_json_schema(),
                ensure_ascii=False,
                indent=2,
            )
            + "\n\n"
            + get_brand_radar_result_contract()
        )

        plan_steps: list[dict[str, Any]] = []
        selected_actions: list[dict[str, Any]] = []
        tool_feedback: list[dict[str, Any]] = []
        decision_log: list[dict[str, Any]] = []
        preflight_known_source_ids = {
            item["source_id"] for item in runtime.validator_payload()["source_catalog"]
        }

        if self.llm.is_mock:
            mock_decision = _InvestigationDecision.model_validate(
                {
                    "decision": "investigate",
                    "skill_name": "signal-triage",
                    "objective": "读取一条本地材料，验证受限调查接缝",
                    "reason": "Mock 只验证程序链路，不代表业务判断。",
                    "action_type": "inspect_local_evidence",
                    "arguments": {"source_id": runtime.materials[0]["source_id"]},
                }
            )
            step, action, feedback = self._execute_investigation_decision(
                runtime, mock_decision, 1
            )
            plan_steps.append(step)
            selected_actions.append(action)
            tool_feedback.append(feedback)
            selected_skill_bodies["signal-triage"] = get_marketing_skill_content(
                "signal-triage", self.skills_dir
            )
            selected_skill_bodies["brief-distillation"] = get_marketing_skill_content(
                "brief-distillation", self.skills_dir
            )
            decision_log.extend(
                [
                    {
                        "round": 1,
                        "decision": "investigate",
                        "skill_name": "signal-triage",
                        "reason": mock_decision.reason,
                        "based_on_feedback_ids": [],
                        "action_id": "action-1",
                    },
                    {
                        "round": 2,
                        "decision": "generate",
                        "skill_name": "brief-distillation",
                        "reason": "Mock 已读取一次本地反馈，开始生成固定烟雾测试结果。",
                        "based_on_feedback_ids": ["feedback-action-1"],
                        "action_id": None,
                    },
                ]
            )
            adjustments = [
                {
                    "adjustment_id": "mock-adjustment-1",
                    "action_id": "action-1",
                    "feedback_id": "feedback-action-1",
                    "reason": "Mock 仅确认本地反馈可进入固定输出，不作为营销判断。",
                }
            ]
            candidate = runtime.load_expected_candidate()
            summary = str(candidate.get("executive_summary", ""))
            candidate["executive_summary"] = (
                "[MOCK 输出｜仅供程序烟雾测试，不能作为业务验收] " + summary
            ).strip()
            generation_raw = json.dumps(candidate, ensure_ascii=False)
        else:
            observation = runtime.observation_payload()
            decision_schema = json.dumps(
                _InvestigationDecision.model_json_schema(),
                ensure_ascii=False,
                indent=2,
            )
            for round_number in range(1, MAX_INVESTIGATION_ACTIONS + 2):
                prior_feedback_ids = [item["feedback_id"] for item in tool_feedback]
                remaining_actions = MAX_INVESTIGATION_ACTIONS - len(selected_actions)
                decision_context = {
                    "business_task": task_description,
                    "brand_profile": {
                        **brand_run_info,
                        "content": brand_profile.content,
                    },
                    "runtime_rules": runtime_rules,
                    "skill_catalog": skill_catalog,
                    "selected_skill_bodies": selected_skill_bodies,
                    "observation": observation,
                    "selected_actions": selected_actions,
                    "tool_feedback": tool_feedback,
                    "remaining_action_count": remaining_actions,
                }
                console.print(
                    f"  [dim]Agent：第 {round_number} 轮调查决策（剩余 {remaining_actions} 动作）[/dim]"
                )
                decision_response = self.llm.chat(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                sc["system_prompt"]
                                + "\n\n你是逐轮决策的单一营销企划 Agent。每轮只能选择一项营销技能，"
                                "并且只能决定执行一个白名单本地动作或开始生成。"
                                "至少完成一次调查后才能 generate；最多执行三次调查。"
                                "第三次反馈后的最终决策必须是 generate。"
                                "动作 ID、步骤 ID 和反馈 ID 由程序生成，禁止输出这些 ID。"
                                "只输出符合 JSON Schema 的对象。\n\n"
                                "【实际生效的 BRAND.md】\n"
                                + brand_profile.content
                                + "\n\n【实际生效的 agent/AGENTS.md】\n"
                                + runtime_rules
                                + "\n\n【调查决策 JSON Schema】\n"
                                + decision_schema
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "请基于 observation 中的已知信号与 open_questions、"
                                "累计 selected_actions 和 tool_feedback 作出本轮唯一决策。"
                                "调查动作及参数契约如下：\n"
                                + json.dumps(
                                    INVESTIGATION_TOOLS,
                                    ensure_ascii=False,
                                    indent=2,
                                )
                                + "\n\n决策上下文：\n"
                                + json.dumps(
                                    decision_context,
                                    ensure_ascii=False,
                                    indent=2,
                                )
                            ),
                        },
                    ],
                    temperature=0.1,
                    max_tokens=2200,
                    response_format={"type": "json_object"},
                    stream_progress=True,
                )
                try:
                    decision = self._parse_investigation_decision(
                        decision_response.choices[0].message.content or ""
                    )
                except RuntimeError as exc:
                    raise WeeklyPipelineError(str(exc)) from exc

                selected_skill_bodies[decision.skill_name] = (
                    get_marketing_skill_content(decision.skill_name, self.skills_dir)
                )
                if decision.decision == "generate":
                    if not selected_actions:
                        raise WeeklyPipelineError(
                            "至少完成一次调查并读取反馈后才能 generate"
                        )
                    decision_log.append(
                        {
                            "round": round_number,
                            "decision": "generate",
                            "skill_name": decision.skill_name,
                            "reason": decision.reason,
                            "based_on_feedback_ids": prior_feedback_ids,
                            "action_id": None,
                        }
                    )
                    break

                if len(selected_actions) >= MAX_INVESTIGATION_ACTIONS:
                    raise WeeklyPipelineError(
                        "第三次反馈后必须最终决定 generate；不允许第四次调查动作"
                    )
                action_index = len(selected_actions) + 1
                step, action, feedback = self._execute_investigation_decision(
                    runtime, decision, action_index
                )
                plan_steps.append(step)
                selected_actions.append(action)
                tool_feedback.append(feedback)
                decision_log.append(
                    {
                        "round": round_number,
                        "decision": "investigate",
                        "skill_name": decision.skill_name,
                        "reason": decision.reason,
                        "based_on_feedback_ids": prior_feedback_ids,
                        "action_id": action["action_id"],
                    }
                )
                try:
                    validate_investigation_preflight(
                        {
                            "goal_snapshot": goal_snapshot,
                            "plan_steps": plan_steps,
                            "selected_actions": selected_actions,
                            "tool_feedback": tool_feedback,
                        },
                        known_source_ids=preflight_known_source_ids,
                    )
                except BrandRadarValidationError as exc:
                    raise WeeklyPipelineError(
                        f"调查计划或工具反馈轨迹无效：{exc}"
                    ) from exc
            else:
                raise WeeklyPipelineError("调查决策未能在有界轮次内收敛到 generate")

            investigation_context = {
                "goal_snapshot": goal_snapshot,
                "plan_steps": plan_steps,
                "selected_actions": selected_actions,
                "tool_feedback": tool_feedback,
                "decision_log": decision_log,
            }
            generation_evidence = runtime.generation_payload(investigation_context)
            generation_evidence.update(
                {
                    "brand_profile": {
                        **brand_run_info,
                        "content": brand_profile.content,
                    },
                    "runtime_rules": runtime_rules,
                    "selected_skill_bodies": selected_skill_bodies,
                }
            )
            console.print(
                f"  [dim]Agent：已完成 {len(selected_actions)} 项本地调查，开始生成企划[/dim]"
            )
            generation_response = self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            sc["system_prompt"]
                            + "\n\n现在根据全部实际 tool_feedback 生成周企划。"
                            "adjustment_reasons 必须逐一引用实际 action_id 与 feedback_id，"
                            "解释反馈怎样确认、改变或保留待核判断。\n\n"
                            "【实际生效的 BRAND.md】\n"
                            + brand_profile.content
                            + "\n\n【实际生效的 agent/AGENTS.md】\n"
                            + runtime_rules
                            + "\n\n【本次已选营销技能正文】\n"
                            + json.dumps(
                                selected_skill_bodies,
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n\n"
                            + generation_contract
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"业务任务：{task_description}\n\n"
                            "以下是固定材料处理、逐轮决策、所选调查动作以及全部真实 tool_feedback。"
                            "只能使用这些证据；expired、superseded 或 failed 材料不能写入事实卡，"
                            "unverified 或 unresolved_conflict 只能形成 needs_verification 卡。"
                            "如果 tool_feedback.outcome 是 no_pack_evidence 或 no_current_pack_evidence，"
                            "只能把它写成引用该 feedback_id 的缺证卡，不得附会到无关 source_ids。"
                            "其中 no_current_pack_evidence 返回的旧 source_ids 只用于追溯，不能进入卡片 source_ids。"
                            "没有收到某竞品的 evidence-gap 反馈时，不得凭空创建该竞品的无来源缺证卡；"
                            "其他已有当前材料的卡必须引用反馈中实际返回的 source_ids。\n\n"
                            "生成证据：\n"
                            + json.dumps(
                                generation_evidence,
                                ensure_ascii=False,
                                indent=2,
                            )
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=7000,
                response_format={"type": "json_object"},
                stream_progress=True,
            )
            generation_raw = generation_response.choices[0].message.content or ""

        validator_payload = runtime.validator_payload()
        validator_payload["observation_settings"] = {
            **validator_payload["observation_settings"],
            "business_question": task_description,
        }
        known_source_ids = {
            item["source_id"] for item in validator_payload["source_catalog"]
        }

        # Validate the program-owned goal/plan/action/feedback graph before the
        # model is allowed to generate adjustment IDs.  Any later trace error
        # is therefore model-owned and may use the single repair allowance.
        try:
            validate_investigation_preflight(
                {
                    "goal_snapshot": goal_snapshot,
                    "plan_steps": plan_steps,
                    "selected_actions": selected_actions,
                    "tool_feedback": tool_feedback,
                },
                known_source_ids=known_source_ids,
            )
        except BrandRadarValidationError as exc:
            raise WeeklyPipelineError(f"调查计划或工具反馈轨迹无效：{exc}") from exc

        def build_trace(adjustment_reasons, generation_attempts):
            return {
                "goal_snapshot": goal_snapshot,
                "plan_steps": plan_steps,
                "selected_actions": selected_actions,
                "tool_feedback": tool_feedback,
                "decision_log": decision_log,
                "adjustment_reasons": adjustment_reasons,
                "generation_attempts": generation_attempts,
            }

        def validate_candidate(raw_response, attempts, repaired=False):
            nonlocal adjustments
            if self.llm.is_mock:
                result_raw = raw_response
            else:
                generated = self._parse_generation_response(
                    raw_response,
                    selected_actions=selected_actions,
                    tool_feedback=tool_feedback,
                )
                adjustments = [
                    item.model_dump() for item in generated.adjustment_reasons
                ]
                result_raw = json.dumps(generated.result, ensure_ascii=False)
            trace = build_trace(adjustments, attempts)
            try:
                validate_investigation_trace(
                    trace,
                    known_source_ids=known_source_ids,
                )
            except ValidationError as exc:
                raise WeeklyPipelineError(f"调查轨迹校验失败：{exc}") from exc
            stages = [
                *WEEKLY_TOOL_ORDER,
                "decide_weekly_investigation",
                "execute_weekly_investigation",
                "generate_weekly_result",
            ]
            if repaired:
                stages.append("repair_weekly_result")
            stages.append("awaiting_human_review")
            return parse_brand_radar_output(
                result_raw,
                **validator_payload,
                investigation_trace=trace,
                run_info={
                    "mode": "mock" if self.llm.is_mock else "real",
                    "provider": self.llm.provider,
                    "model": self.llm.model,
                    "source_pack": runtime.display_path,
                    "brand_profile": brand_run_info,
                    "stages_completed": stages,
                    "started_at": started_at,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        try:
            validated = validate_candidate(
                generation_raw,
                [{"attempt": 1, "status": "validated", "issues": []}],
            )
        except BrandRadarValidationError as first_error:
            if self.llm.is_mock:
                raise
            first_issues = self._error_issues(first_error)
            console.print("  [dim]Agent：专用校验未通过，执行唯一一次受限修正[/dim]")
            repair_response = self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你只能修正上一份 Brand Radar 周企划 JSON。"
                            "不得重新规划、选择或执行工具；不得新增来源。"
                            "回应全部校验问题，并严格遵守以下同一生成契约。\n\n"
                            "【实际生效的 BRAND.md】\n"
                            + brand_profile.content
                            + "\n\n【实际生效的 agent/AGENTS.md】\n"
                            + runtime_rules
                            + "\n\n【本次已选营销技能正文】\n"
                            + json.dumps(
                                selected_skill_bodies,
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n\n"
                            + generation_contract
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "validation_issues": first_issues,
                                "previous_response": generation_raw,
                                "generation_evidence": generation_evidence,
                                "validation_context": validator_payload,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                ],
                temperature=0,
                max_tokens=7000,
                response_format={"type": "json_object"},
                stream_progress=True,
            )
            repair_raw = repair_response.choices[0].message.content or ""
            validated = validate_candidate(
                repair_raw,
                [
                    {
                        "attempt": 1,
                        "status": "validation_failed",
                        "issues": first_issues,
                    },
                    {"attempt": 2, "status": "validated", "issues": []},
                ],
                repaired=True,
            )

        destination = Path(output_dir) if output_dir is not None else Path(__file__).parent.parent / "outputs"
        destination.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        mode = "mock" if self.llm.is_mock else "real"
        output_path = destination / f"brand_radar_weekly-{mode}-{stamp}.json"
        temporary = output_path.with_suffix(".json.tmp")
        try:
            temporary.write_text(validated.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(output_path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return validated, output_path

    # ── 结构化输出解析 ────────────────────────────────────────────────────────

    def _parse_structured(self, raw: str, scenario_id: str, task_description: str) -> str:
        """尝试将 LLM 输出解析为 AgentOutput；失败则降级返回原文。"""
        import re
        # 抽取 JSON（兼容 ```json 包裹）
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            console.print("[dim yellow]  ⚠ 输出未含 JSON，保持原文[/dim yellow]")
            return raw
        try:
            data = json.loads(m.group(0))
            data.setdefault("scenario_id", scenario_id)
            data.setdefault("task_description", task_description)
            output = AgentOutput.model_validate(data)
            md = output.to_markdown()
            console.print("[dim]  ✓ 输出已结构化（观察/洞察/决策点/建议）[/dim]")
            return md
        except Exception as e:
            console.print(f"[dim yellow]  ⚠ 结构化解析失败（{type(e).__name__}），保持原文[/dim yellow]")
            return raw
