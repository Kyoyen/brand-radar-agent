"""
Pain Point Intake — 新营销场景录入工具
==========================================
作用：帮助营销人员结构化地记录一个新的业务痛点，
      并自动评估 Agent 化可行性、生成场景配置草稿。

设计理念：
  「场景挖掘」是 Agent 化最难的一步。
  很多人描述的是「症状」而非「可 Agent 化的工作流」。
  本工具通过一组结构化问题，帮助用户把模糊痛点转化为：
    1. 可执行的工作流描述
    2. Agent 化可行性评分
    3. 工具调用链设计草稿
    4. 可直接加入 scenario_registry.json 的 JSON 配置

使用方式：
  python -m framework.pain_point_intake
  → 交互式问答 → 生成场景配置文件
"""

import json
import os
from datetime import date
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

load_dotenv()
console = Console()
REGISTRY_PATH = Path(__file__).parent / "scenario_registry.json"

# ─── Agent 化可行性评估维度 ──────────────────────────────────────────────────
# 每个维度 0-10 分，总分越高越适合 Agent 化
EVALUATION_DIMENSIONS = [
    {
        "key": "frequency",
        "question": "这个任务多久做一次？",
        "options": ["每天", "每周2-3次", "每周1次", "每月几次", "偶尔"],
        "scores":  [10,    8,          6,        3,          1],
        "label": "执行频率",
    },
    {
        "key": "rule_clarity",
        "question": "这个任务的执行步骤是固定的/有规律的吗？",
        "options": ["完全固定，每次一样", "基本固定，偶有调整", "有框架但灵活性高", "完全依赖经验判断"],
        "scores":  [10,                  7,                    4,                  1],
        "label": "规则清晰度",
    },
    {
        "key": "decision_chain",
        "question": "完成这个任务需要多少人参与决策？",
        "options": ["只需要我一个人", "我 + 直属上级确认", "需要跨部门协作", "需要多方审批"],
        "scores":  [10,               7,                   3,                  1],
        "label": "决策链长度",
    },
    {
        "key": "data_availability",
        "question": "完成这个任务需要的数据/信息在哪里？",
        "options": ["可以通过 API 获取", "需要登录平台手动查看", "部分自动+部分手动", "主要依赖人工采集"],
        "scores":  [10,                  5,                       7,                    2],
        "label": "数据可获取性",
    },
    {
        "key": "output_standardization",
        "question": "这个任务的输出结果格式是固定的吗？",
        "options": ["完全标准化（固定模板）", "有框架可以标准化", "每次输出差异较大", "完全自由形式"],
        "scores":  [10,                      8,                   4,                   1],
        "label": "输出标准化程度",
    },
]


class PainPointIntake:

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def run(self):
        """交互式痛点录入主流程"""
        console.print(Panel(
            "本工具帮你将营销工作中的痛点结构化为可 Agent 化的场景配置。\n"
            "大约需要 3-5 分钟，回答几个问题即可。",
            title="🔍 营销 Agent 场景录入",
            border_style="cyan",
        ))

        # Step 1：基本信息
        console.print("\n[bold cyan]Step 1/4  基本信息[/bold cyan]")
        scenario_name = Prompt.ask("这个工作场景叫什么名字（自己起一个）")
        pain_description = Prompt.ask("用一两句话描述这个痛点（你现在怎么做，哪里让你头疼）")
        current_time_cost = Prompt.ask("目前每周花多少时间在这上面（如：3小时）")
        desired_output = Prompt.ask("理想中，Agent 完成后应该输出什么（如：一份竞情简报推送到飞书）")

        # Step 2：可行性评估
        console.print("\n[bold cyan]Step 2/4  Agent 化可行性评估[/bold cyan]")
        scores = {}
        for dim in EVALUATION_DIMENSIONS:
            console.print(f"\n[yellow]{dim['question']}[/yellow]")
            for i, opt in enumerate(dim["options"], 1):
                console.print(f"  {i}. {opt}")
            choice = Prompt.ask("请选择", choices=[str(i) for i in range(1, len(dim["options"]) + 1)])
            idx = int(choice) - 1
            scores[dim["key"]] = {
                "label": dim["label"],
                "answer": dim["options"][idx],
                "score": dim["scores"][idx],
            }

        total_score = sum(v["score"] for v in scores.values())
        max_score = len(EVALUATION_DIMENSIONS) * 10
        feasibility_pct = round(total_score / max_score * 100)

        console.print(f"\n[bold]Agent 化可行性评分：{total_score}/{max_score}（{feasibility_pct}%）[/bold]")
        if feasibility_pct >= 70:
            console.print("[green]✅ 高度适合 Agent 化，建议优先落地[/green]")
        elif feasibility_pct >= 50:
            console.print("[yellow]⚠️ 适合 Agent 化，但有部分人工环节无法自动化[/yellow]")
        else:
            console.print("[red]❌ 暂不适合完全 Agent 化，建议先梳理工作流、提升规则化程度[/red]")

        # Step 3：工作流拆解
        console.print("\n[bold cyan]Step 3/4  工作流拆解[/bold cyan]")
        console.print("请按顺序描述这个任务的执行步骤（每步一行，输入空行结束）：")
        steps = []
        step_num = 1
        while True:
            step = Prompt.ask(f"第{step_num}步", default="")
            if not step:
                break
            steps.append(step)
            step_num += 1

        # Step 4：触发词与工具猜测
        console.print("\n[bold cyan]Step 4/4  触发词（用于自动路由识别）[/bold cyan]")
        keywords_raw = Prompt.ask("当你想启动这个任务时，通常会说什么关键词（用逗号分隔，如：选题,内容方向,brief）")
        trigger_keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

        # 用 LLM 生成场景配置草稿
        console.print("\n[cyan]正在生成场景配置...[/cyan]")
        config = self._generate_scenario_config(
            scenario_name=scenario_name,
            pain_description=pain_description,
            current_time_cost=current_time_cost,
            desired_output=desired_output,
            steps=steps,
            feasibility_score=feasibility_pct,
            trigger_keywords=trigger_keywords,
        )

        # 展示生成结果
        console.print(Panel(
            json.dumps(config, ensure_ascii=False, indent=2),
            title="📋 生成的场景配置草稿",
            border_style="green",
        ))

        # 询问是否写入注册表
        if Confirm.ask("\n是否将此场景加入 scenario_registry.json？"):
            self._add_to_registry(config)
            console.print(f"[green]✅ 已加入注册表，场景ID：{config['_id']}[/green]")
            console.print("现在可以通过 AgentRunner().run_auto('...') 使用这个场景了。")

        return config

    def _generate_scenario_config(self, **kwargs) -> dict:
        """用 LLM 基于用户输入生成完整场景配置"""
        prompt = f"""
基于以下营销工作痛点，生成一个 Agent 场景配置 JSON：

场景名称：{kwargs['scenario_name']}
痛点描述：{kwargs['pain_description']}
当前耗时：{kwargs['current_time_cost']}
期望输出：{kwargs['desired_output']}
执行步骤：{json.dumps(kwargs['steps'], ensure_ascii=False)}
可行性评分：{kwargs['feasibility_score']}%
触发关键词：{kwargs['trigger_keywords']}

请生成包含以下字段的 JSON（仅输出 JSON，无其他文字）：
{{
  "_id": "snake_case场景ID",
  "name": "中文名称",
  "description": "一句话描述（30字以内）",
  "trigger_keywords": [...],
  "system_prompt": "详细的 Agent 工作流提示词，包含步骤说明",
  "tools": ["需要的工具函数名列表"],
  "estimated_duration_min": 数字,
  "roi_metrics": {{
    "time_saved_hours_per_week": 数字,
    "before": "现状描述",
    "after": "自动化后描述"
  }},
  "implementation_notes": "落地注意事项"
}}
"""
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个 Agent 产品设计师，专门帮助营销团队设计 Agent 化方案。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    def _add_to_registry(self, config: dict):
        """将新场景写入 scenario_registry.json"""
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            registry = json.load(f)

        scenario_id = config.pop("_id", config.get("name", "new_scenario").replace(" ", "_"))
        registry["scenarios"][scenario_id] = config
        registry["_meta"]["last_updated"] = date.today().isoformat()

        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    intake = PainPointIntake()
    intake.run()
