"""
Agent Runner — 多场景路由引擎
================================
用自然语言描述任务，自动识别场景、加载工具、执行 ReAct 循环。
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .context_manager import ContextManager
from .session_summarizer import SessionSummarizer
from .llm_client import LLMClient

load_dotenv()
console = Console()

REGISTRY_PATH = Path(__file__).parent / "scenario_registry.json"
MAX_TURNS_DEFAULT = int(os.getenv("AGENT_MAX_TURNS", 12))


class AgentRunner:
    def __init__(self):
        self.llm        = LLMClient()
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
        t.add_column("周节省", width=8)
        for sid, sc in self.registry["scenarios"].items():
            t.add_row(sid, sc["name"], sc["description"][:36]+"...",
                      f"~{sc['estimated_duration_min']}min",
                      f"~{sc['roi_metrics']['time_saved_hours_per_week']}h")
        console.print(t)

    def show_roi_summary(self):
        total = sum(sc["roi_metrics"]["time_saved_hours_per_week"]
                    for sc in self.registry["scenarios"].values())
        console.print(Panel(
            f"[bold]4 个场景全部启用，预计每周节省约 {total}h 人工工时[/bold]\n\n" +
            "\n".join(f"• {sc['name']}：省 {sc['roi_metrics']['time_saved_hours_per_week']}h/周"
                      for sc in self.registry["scenarios"].values()),
            title="💡 ROI 汇总", border_style="green",
        ))

    # ── 自动路由 ──────────────────────────────────────────────────────────────

    def _detect_scenario(self, task: str) -> str:
        task_lower = task.lower()
        for sid, sc in self.registry["scenarios"].items():
            if any(kw in task_lower for kw in sc["trigger_keywords"]):
                console.print(f"  [dim]场景识别：关键词 → [cyan]{sid}[/cyan][/dim]")
                return sid

        scenario_list = "\n".join(f"- {sid}: {sc['description']}"
                                   for sid, sc in self.registry["scenarios"].items())
        resp = self.llm.chat(
            messages=[
                {"role": "system", "content": f"从以下场景中选出最匹配的ID，只输出ID：\n{scenario_list}"},
                {"role": "user",   "content": task},
            ],
            temperature=0, max_tokens=30,
        )
        detected = resp.choices[0].message.content.strip()
        if detected in self.registry["scenarios"]:
            console.print(f"  [dim]场景识别：LLM → [cyan]{detected}[/cyan][/dim]")
            return detected

        console.print("  [dim]场景识别：默认 → competitive_analysis[/dim]")
        return "competitive_analysis"

    # ── 工具加载 ──────────────────────────────────────────────────────────────

    def _load_tools(self, scenario_id: str):
        from v3_agent.tools import TOOLS as base_tools, execute_tool as base_exec
        try:
            from scenarios.tools_extended import EXTENDED_TOOLS, execute_extended_tool
        except ImportError:
            EXTENDED_TOOLS, execute_extended_tool = [], None

        required = set(self.registry["scenarios"][scenario_id]["tools"])
        tools = [t for t in (base_tools + EXTENDED_TOOLS) if t["function"]["name"] in required]

        def execute(name, args):
            result = base_exec(name, args)
            if '"error"' in result and execute_extended_tool:
                result = execute_extended_tool(name, args)
            return result

        return tools, execute

    # ── ReAct 主循环 ──────────────────────────────────────────────────────────

    def run(self, scenario_id: str, task_description: str = "", **kwargs) -> str:
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
        system_content = sc["system_prompt"].format(brand=brand, our_brand=brand, **{
            k: v for k, v in kwargs.items() if k not in ("brand","our_brand")
        }) + extra_ctx

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": f"请执行：{task_description}\n参数：{kwargs}"},
        ]

        tools, execute_tool = self._load_tools(scenario_id)
        max_turns        = sc.get("max_turns", MAX_TURNS_DEFAULT)
        checkpoint_every = sc.get("checkpoint_every", 5)
        final_output     = ""

        for turn in range(1, max_turns + 1):
            with console.status(f"[cyan]第 {turn} 轮推理...[/cyan]"):
                response = self.llm.chat(messages=messages, tools=tools or None, temperature=0.2)

            msg = response.choices[0].message
            messages.append(msg)

            if response.choices[0].finish_reason == "stop":
                final_output = msg.content or "完成。"
                console.print(f"\n[green]✓ 完成（{turn}轮 / {ctx.tool_call_count}次工具调用）[/green]")
                break

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments)
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
