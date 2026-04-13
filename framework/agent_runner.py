"""
Agent Runner — 通用多场景路由引擎
====================================
核心职责：
  1. 加载 scenario_registry.json，动态路由到正确的场景配置
  2. 统一管理 Agent 主循环（ReAct 模式）
  3. 与 ContextManager 集成：执行中压缩 + 结束后持久化
  4. 支持自然语言任务描述 → 自动识别场景（无需手动指定）

使用方式：
  # 指定场景
  runner = AgentRunner()
  runner.run("competitive_analysis", brand="肯德基", competitors=["麦当劳"])

  # 自然语言自动路由
  runner.run_auto("帮我看看今天有哪些热点可以借势")
  runner.run_auto("生成下周小红书的5个内容选题")
"""

import json
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .context_manager import ContextManager
from .session_summarizer import SessionSummarizer

load_dotenv()
console = Console()

REGISTRY_PATH = Path(__file__).parent / "scenario_registry.json"
MAX_TURNS_DEFAULT = 12


class AgentRunner:

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.registry = self._load_registry()
        self._tools_cache: dict = {}   # 按场景缓存工具定义
        self.summarizer = SessionSummarizer()

    # ─── 注册表操作 ──────────────────────────────────────────────────────────

    def _load_registry(self) -> dict:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)

    def list_scenarios(self):
        """打印所有可用场景"""
        table = Table(title="营销 Agent OS — 可用场景", show_lines=True)
        table.add_column("场景ID", style="cyan", width=22)
        table.add_column("名称", width=16)
        table.add_column("描述", width=36)
        table.add_column("预计耗时", width=10)
        table.add_column("周节省工时", width=10)

        for sid, sc in self.registry["scenarios"].items():
            table.add_row(
                sid,
                sc["name"],
                sc["description"][:35] + "...",
                f"~{sc['estimated_duration_min']}min",
                f"~{sc['roi_metrics']['time_saved_hours_per_week']}h",
            )
        console.print(table)

    # ─── 自动路由（自然语言 → 场景）────────────────────────────────────────

    def _auto_detect_scenario(self, task_description: str) -> str:
        """
        用 LLM + 关键词匹配识别任务对应的场景
        先尝试关键词快速匹配，匹配失败再用 LLM 判断
        """
        # 关键词快速匹配
        task_lower = task_description.lower()
        for sid, sc in self.registry["scenarios"].items():
            if any(kw in task_lower for kw in sc["trigger_keywords"]):
                console.print(f"  [dim]场景识别：关键词匹配 → [cyan]{sid}[/cyan][/dim]")
                return sid

        # LLM 兜底识别
        scenario_list = "\n".join(
            f"- {sid}: {sc['description']}"
            for sid, sc in self.registry["scenarios"].items()
        )
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"从以下营销 Agent 场景中，选出最匹配用户任务的场景ID，只输出场景ID，不输出其他内容：\n{scenario_list}"
                    ),
                },
                {"role": "user", "content": f"用户任务：{task_description}"},
            ],
            temperature=0,
            max_tokens=30,
        )
        detected = resp.choices[0].message.content.strip()
        if detected in self.registry["scenarios"]:
            console.print(f"  [dim]场景识别：LLM → [cyan]{detected}[/cyan][/dim]")
            return detected

        # 默认回退到竞品分析
        console.print("  [dim]场景识别：未匹配，默认 → competitive_analysis[/dim]")
        return "competitive_analysis"

    # ─── 工具加载 ─────────────────────────────────────────────────────────────

    def _load_tools_for_scenario(self, scenario_id: str) -> list[dict]:
        """动态加载场景所需工具（从 v3_agent/tools.py + scenarios/tools_extended.py）"""
        from v3_agent.tools import TOOLS as base_tools

        try:
            from scenarios.tools_extended import EXTENDED_TOOLS
        except ImportError:
            EXTENDED_TOOLS = []

        # 场景需要的工具名称
        required = set(self.registry["scenarios"][scenario_id]["tools"])

        all_tools = base_tools + EXTENDED_TOOLS
        return [t for t in all_tools if t["function"]["name"] in required]

    def _get_tool_executor(self):
        """返回统一工具执行函数（合并基础工具 + 扩展工具）"""
        from v3_agent.tools import execute_tool as base_execute

        try:
            from scenarios.tools_extended import execute_extended_tool
            def execute(name, args):
                result = base_execute(name, args)
                if '"error": "Unknown tool' not in result:
                    return result
                return execute_extended_tool(name, args)
        except ImportError:
            execute = base_execute

        return execute

    # ─── Agent 主循环 ─────────────────────────────────────────────────────────

    def run(
        self,
        scenario_id: str,
        task_description: str = "",
        **kwargs,
    ) -> str:
        """
        执行指定场景的 Agent 任务
        kwargs 会被注入到 system_prompt 的格式化参数中
        """
        sc = self.registry["scenarios"][scenario_id]
        if not task_description:
            task_description = f"{sc['name']} 任务"

        console.print(Panel(
            f"[bold]{sc['name']}[/bold]\n[dim]{task_description}[/dim]",
            title=f"🤖 Agent Runner — {scenario_id}",
            border_style="cyan",
        ))

        # 初始化 ContextManager
        ctx = ContextManager(scenario=scenario_id, task_description=task_description)

        # 加载历史记忆（跨会话上下文）
        history = ctx.load_relevant_history(limit=2)
        history_note = f"\n\n{history}" if history else ""

        # 加载同场景历史菜谱（复用经验）
        recipes = self.summarizer.find_relevant_recipes(scenario_id, task_description, limit=2)
        if recipes:
            history_note += f"\n\n{recipes}"

        # 构建 system prompt
        system_content = sc["system_prompt"].format(**{
            "our_brand": kwargs.get("our_brand", os.getenv("TARGET_BRAND", "品牌方")),
            "brand": kwargs.get("brand", os.getenv("TARGET_BRAND", "品牌方")),
            **kwargs,
        }) + history_note

        # 构建初始消息
        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": self._build_user_message(scenario_id, task_description, kwargs),
            },
        ]

        # 加载工具
        tools = self._load_tools_for_scenario(scenario_id)
        execute_tool = self._get_tool_executor()
        max_turns = sc.get("max_turns", MAX_TURNS_DEFAULT)
        checkpoint_every = sc.get("checkpoint_every", 5)

        final_output = ""
        turn = 0

        # ── ReAct 主循环 ───────────────────────────────────────────────────
        while turn < max_turns:
            turn += 1

            with console.status(f"[cyan]推理中（第 {turn} 轮）...[/cyan]"):
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    temperature=0.2,
                )

            msg = response.choices[0].message
            messages.append(msg)

            # 任务完成
            if response.choices[0].finish_reason == "stop":
                final_output = msg.content or "任务完成。"
                console.print(f"\n[green]✓ 完成（{turn}轮 / {ctx.tool_call_count}次工具调用）[/green]")
                break

            # 处理工具调用
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)
                    console.print(f"  [yellow]→[/yellow] [bold]{fn_name}[/bold]  {fn_args}")

                    result = execute_tool(fn_name, fn_args)
                    ctx.record_tool_call()

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                # Layer 1：执行中压缩（每 checkpoint_every 次工具调用触发）
                if ctx.should_checkpoint():
                    messages = ctx.compress(messages)

        # Layer 2：任务结束后持久化
        ctx.save_session(
            final_output=final_output,
            metadata={"scenario_id": scenario_id, "kwargs": kwargs},
        )

        # Layer 3：生成场景菜谱（执行过程归纳，供下次复用）
        try:
            recipe_path = self.summarizer.save_recipe(
                scenario_id=scenario_id,
                task_description=task_description,
                final_output=final_output,
                messages=messages,
                metadata={"kwargs": kwargs, "tool_calls": ctx.tool_call_count},
            )
            console.print(f"  [dim]菜谱已归档：{recipe_path.name}[/dim]")
        except Exception as e:
            console.print(f"  [dim yellow]菜谱归档跳过：{e}[/dim yellow]")

        return final_output

    def run_auto(self, task_description: str, **kwargs) -> str:
        """自然语言任务 → 自动识别场景 → 执行"""
        scenario_id = self._auto_detect_scenario(task_description)
        return self.run(scenario_id, task_description=task_description, **kwargs)

    # ─── 辅助方法 ──────────────────────────────────────────────────────────────

    def _build_user_message(self, scenario_id: str, task: str, kwargs: dict) -> str:
        """根据场景和参数构建用户消息"""
        sc = self.registry["scenarios"][scenario_id]
        param_str = "\n".join(f"- {k}: {v}" for k, v in kwargs.items() if v)
        return (
            f"请执行：{task}\n\n"
            f"参数：\n{param_str}\n\n"
            f"场景：{sc['name']} — {sc['description']}\n"
            f"完成后推送飞书报告并存档。"
        )

    def show_roi_summary(self):
        """展示所有场景的 ROI 汇总"""
        total_saved = sum(
            sc["roi_metrics"]["time_saved_hours_per_week"]
            for sc in self.registry["scenarios"].values()
        )
        console.print(Panel(
            f"[bold]4 个场景全部运行后，预计每周节省约 {total_saved}h 人工工时[/bold]\n\n"
            + "\n".join(
                f"• {sc['name']}：-{sc['roi_metrics']['time_saved_hours_per_week']}h/周"
                for sc in self.registry["scenarios"].values()
            ),
            title="💡 ROI 汇总",
            border_style="green",
        ))


# ─── CLI 入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    runner = AgentRunner()

    if len(sys.argv) < 2:
        runner.list_scenarios()
        runner.show_roi_summary()
        print("\n用法：python -m framework.agent_runner <任务描述>")
        print("示例：python -m framework.agent_runner '帮我分析麦当劳今天在小红书的内容动态'")
    else:
        task = " ".join(sys.argv[1:])
        result = runner.run_auto(task, brand=os.getenv("TARGET_BRAND", "肯德基"))
        console.print(f"\n[bold]输出：[/bold]\n{result}")
