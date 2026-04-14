"""
Pain Point Intake — 新业务痛点录入工具
========================================
引导式问答，5 分钟将一个重复性营销工作录入为可执行的 Agent 场景。

运行：python run.py --intake
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

REGISTRY_PATH = Path(__file__).parent / "scenario_registry.json"

DIMENSIONS = [
    ("execution_frequency",       "执行频率",     "这个工作多久做一次？（每天/每周/每月）"),
    ("rule_clarity",              "规则清晰度",   "执行步骤是否固定？还是每次都要判断？（1-10分）"),
    ("decision_chain_length",     "决策链长度",   "完成这个工作需要经过多少人审批？（1=无需审批，10=多层审批）"),
    ("data_availability",         "数据可获取性", "所需数据是否容易获取？（1=很难，10=随时可取）"),
    ("output_standardization",    "输出标准化",   "输出结果是否格式固定？（1=每次不同，10=完全固定）"),
]


class PainPointIntake:
    def __init__(self):
        self._llm = None

    def _get_llm(self):
        if not self._llm:
            from .llm_client import LLMClient
            self._llm = LLMClient()
        return self._llm

    def run_interactive(self):
        print("\n" + "="*55)
        print("  营销痛点录入工具 — 5 分钟新增一个 Agent 场景")
        print("="*55)

        # 基本信息
        print("\n【第一步：描述痛点】")
        name        = input("场景名称（如：KOL 周报整理）：").strip()
        description = input("痛点描述（做什么事、现在怎么做的）：").strip()
        time_cost   = input("当前每次耗时（如：3小时）：").strip()
        output_desc = input("期望输出（如：飞书卡片报告）：").strip()

        # 可行性评分
        print("\n【第二步：可行性评分（每项 1-10 分）】")
        scores = {}
        for key, label, question in DIMENSIONS:
            while True:
                try:
                    val = int(input(f"  {label}（{question}）：").strip())
                    if 1 <= val <= 10:
                        scores[key] = val
                        break
                    print("  请输入 1-10 的整数")
                except ValueError:
                    print("  请输入数字")

        feasibility = round(sum(scores.values()) / (len(scores) * 10) * 100)
        print(f"\n  ✅ 可行性评分：{feasibility}%")
        if feasibility < 50:
            print("  ⚠️  可行性较低，建议先梳理清楚执行规则再尝试 Agent 化")

        # 执行步骤
        print("\n【第三步：拆解执行步骤（输入空行结束）】")
        steps = []
        i = 1
        while True:
            step = input(f"  步骤{i}：").strip()
            if not step:
                break
            steps.append(step)
            i += 1

        # 生成场景配置
        print("\n  正在生成场景配置...")
        config = self._generate_config(name, description, time_cost, output_desc, scores, steps)

        print(f"\n生成的场景配置：\n{json.dumps(config, ensure_ascii=False, indent=2)}")

        save = input("\n加入场景注册表？(y/n)：").strip().lower()
        if save == "y":
            self._save_to_registry(config)
            print(f"  ✅ 已添加场景：{config['id']}")
            print(f"  现在可以运行：python run.py \"{name}相关任务\"")
        else:
            print("  未保存。你可以手动复制上方配置到 scenario_registry.json")

    def _generate_config(self, name, description, time_cost, output_desc, scores, steps) -> dict:
        feasibility = round(sum(scores.values()) / (len(scores) * 10) * 100)
        steps_str   = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))

        prompt = f"""根据以下信息生成营销 Agent 场景配置（严格 JSON）：

场景名称：{name}
痛点描述：{description}
当前耗时：{time_cost}
期望输出：{output_desc}
可行性：{feasibility}%
执行步骤：
{steps_str}

输出格式：
{{
  "id": "snake_case场景ID",
  "name": "{name}",
  "description": "一句话描述",
  "trigger_keywords": ["关键词1","关键词2","关键词3"],
  "tools": ["search_social_content","send_feishu_report","save_to_history"],
  "system_prompt": "你是...Agent，服务于品牌：{{brand}}。\\n\\n执行步骤：\\n...",
  "max_turns": 10,
  "checkpoint_every": 5,
  "estimated_duration_min": 5,
  "roi_metrics": {{
    "time_saved_hours_per_week": 3,
    "manual_steps_replaced": ["步骤1","步骤2"]
  }}
}}"""

        try:
            resp = self._get_llm().chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            return {
                "id": name.lower().replace(" ", "_"),
                "name": name, "description": description,
                "trigger_keywords": [name],
                "tools": ["send_feishu_report", "save_to_history"],
                "system_prompt": f"你是{name} Agent，服务于品牌：{{brand}}。\n\n执行步骤：\n{steps_str}",
                "max_turns": 10, "checkpoint_every": 5, "estimated_duration_min": 5,
                "roi_metrics": {"time_saved_hours_per_week": 2, "manual_steps_replaced": steps},
            }

    def _save_to_registry(self, config: dict):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        sid = config.pop("id", config.get("name","new_scenario").lower().replace(" ","_"))
        registry["scenarios"][sid] = config
        REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    PainPointIntake().run_interactive()
