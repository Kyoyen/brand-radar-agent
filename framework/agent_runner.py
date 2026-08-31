"""
Agent Runner — 多场景路由引擎
================================
用自然语言描述任务，自动识别场景、加载工具、执行 ReAct 循环。
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
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

# 全局营销方法论约束 — 注入所有场景的 system prompt
# 避免 LLM 在数据稀疏时编造，并强制把数据加工成商业判断
UNIVERSAL_METHODOLOGY = """=== 全局方法论约束 ===
1. 拒绝幻觉：所有定性/定量判断必须 100% 来自工具返回数据，不可编造数据、KPI、热榜
2. 洞察商业机会：不止搬运数据，必须加工为「品牌商业机会」或「风险警示」
3. 专业客观：资深分析师口吻，无套话、无热情服务话术，直接抛业务结论
"""


class AgentRunner:
    def __init__(self, require_api: bool = False, llm: LLMClient | None = None):
        self.llm        = llm or LLMClient(require_api=require_api)
        self.registry   = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.summarizer = SessionSummarizer()
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

    def run_weekly(self, source_pack: str | Path, task_description: str = "",
                   output_dir: str | Path | None = None):
        """Run the fixed Replay pipeline and return ``(validated_output, path)``.

        The legacy context/experience writers are intentionally not used here:
        the validated JSON artifact is the single run record for this scenario.
        """
        from scenarios.brand_radar_weekly import (
            WEEKLY_TOOL_ORDER,
            WeeklyPipelineError,
            WeeklyScenarioRuntime,
        )
        from .brand_radar_output import get_brand_radar_schema_prompt, parse_brand_radar_output

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
        if self.llm.is_mock:
            candidate = runtime.load_expected_candidate()
            summary = str(candidate.get("executive_summary", ""))
            candidate["executive_summary"] = (
                "[MOCK 输出｜仅供程序烟雾测试，不能作为业务验收] " + summary
            ).strip()
            raw = json.dumps(candidate, ensure_ascii=False)
        else:
            evidence = json.dumps(runtime.prompt_payload(), ensure_ascii=False, indent=2)
            response = self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": sc["system_prompt"] + "\n\n" + get_brand_radar_schema_prompt(),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"业务任务：{task_description}\n\n"
                            "以下是程序按固定阶段读取、核对和合并后的全部证据。"
                            "只能使用这些证据；被标记 expired、superseded 或 failed 的材料不能写入事实卡。"
                            "unverified 材料只能形成 needs_verification 卡。\n\n"
                            f"{evidence}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=7000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""

        completed_at = datetime.now(timezone.utc).isoformat()
        validator_payload = runtime.validator_payload()
        validated = parse_brand_radar_output(
            raw,
            **validator_payload,
            run_info={
                "mode": "mock" if self.llm.is_mock else "real",
                "provider": self.llm.provider,
                "model": self.llm.model,
                "source_pack": runtime.display_path,
                "stages_completed": [
                    *WEEKLY_TOOL_ORDER,
                    "generate_weekly_result",
                    "awaiting_human_review",
                ],
                "started_at": started_at,
                "completed_at": completed_at,
            },
        )

        destination = Path(output_dir) if output_dir is not None else Path(__file__).parent.parent / "outputs"
        destination.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        mode = "mock" if self.llm.is_mock else "real"
        output_path = destination / f"brand_radar_weekly-{mode}-{stamp}.json"
        temporary = output_path.with_suffix(".json.tmp")
        temporary.write_text(validated.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(output_path)
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
