"""
Session Summarizer — 执行过程归纳 & 场景复用引擎
================================================
核心职责：
  1. 每次 Agent 运行结束后，将整个执行过程归纳为结构化「执行记录」
  2. 记录：解决了什么问题、用了哪些工具、发现了什么、输出是什么
  3. 存储为可复用的「场景菜谱」(Recipe)
  4. 下次同类任务到来时，自动加载相关菜谱作为上下文加速执行

Recipe 文件路径：memory/recipes/{scenario_id}/{YYYYMMDD}_{session_id}.json

Recipe 结构：
  {
    "scenario_id": ...,
    "run_date": ...,
    "task_description": ...,
    "execution": {
      "tool_sequence": [...],    # 实际调用工具的顺序
      "total_turns": ...,
      "total_tool_calls": ...
    },
    "summary": {
      "problem_solved": ...,     # 解决了什么问题（1句话）
      "approach": ...,           # 解决思路（2-3句话）
      "key_findings": [...],     # 关键发现（可直接复用的结论）
      "output_type": ...,        # 输出形态（飞书报告 / JSON / Brief等）
    },
    "reuse_guide": {
      "when_to_reuse": ...,      # 什么情况下复用本菜谱
      "effective_sequence": [...], # 经过验证有效的工具调用顺序
      "pitfalls": [...],         # 执行中发现的坑/注意事项
      "template_hints": ...      # 对 system prompt 的补充建议
    },
    "tags": [...]                # 用于相似任务匹配的关键词
  }
"""

import json
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

RECIPES_DIR = Path(__file__).parent.parent / "memory" / "recipes"
RECIPES_DIR.mkdir(parents=True, exist_ok=True)


class SessionSummarizer:
    """
    在 Agent 每次运行结束后，将执行过程凝练为可复用的「场景菜谱」。
    再次遇到相似任务时，自动召回相关菜谱注入到 system prompt。
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # ─── 保存菜谱 ──────────────────────────────────────────────────────────

    def save_recipe(
        self,
        scenario_id: str,
        task_description: str,
        final_output: str,
        messages: list[dict],
        metadata: Optional[dict] = None,
    ) -> Path:
        """
        执行结束后调用。归纳本次 session，生成结构化菜谱并持久化。

        Args:
            scenario_id:       场景标识（如 competitive_analysis）
            task_description:  本次任务的自然语言描述
            final_output:      Agent 最终输出文本
            messages:          完整消息历史（用于归纳执行过程）
            metadata:          附加信息（kwargs、tool_call_count 等）

        Returns:
            保存路径
        """
        execution_trace = self._extract_execution_trace(messages)
        recipe_content = self._generate_recipe(
            scenario_id, task_description, final_output, execution_trace, metadata
        )

        # 存储
        scenario_dir = RECIPES_DIR / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}.json"
        filepath = scenario_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(recipe_content, f, ensure_ascii=False, indent=2)

        return filepath

    # ─── 召回相关菜谱 ─────────────────────────────────────────────────────

    def find_relevant_recipes(
        self,
        scenario_id: str,
        task_description: str,
        limit: int = 2,
    ) -> str:
        """
        根据场景 + 任务描述，召回最相关的历史菜谱，返回可注入 system prompt 的文本。

        Returns:
            格式化的参考文本（空字符串表示无历史菜谱）
        """
        scenario_dir = RECIPES_DIR / scenario_id
        if not scenario_dir.exists():
            return ""

        recipe_files = sorted(scenario_dir.glob("*.json"), reverse=True)[:limit * 3]
        if not recipe_files:
            return ""

        candidates = []
        for fp in recipe_files:
            try:
                with open(fp, encoding="utf-8") as f:
                    recipe = json.load(f)
                candidates.append(recipe)
            except Exception:
                continue

        if not candidates:
            return ""

        # 按相关性排序（标签匹配 + 日期优先）
        task_lower = task_description.lower()
        scored = []
        for r in candidates:
            tags = r.get("tags", [])
            score = sum(1 for tag in tags if tag in task_lower)
            score += 0.1  # 日期越新加分（已按时间倒排）
            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_recipes = [r for _, r in scored[:limit]]

        # 格式化为可注入文本
        lines = ["【历史执行参考】以下为相似任务的已验证执行记录：\n"]
        for i, r in enumerate(top_recipes, 1):
            s = r.get("summary", {})
            rg = r.get("reuse_guide", {})
            lines.append(f"参考{i}（{r.get('run_date', '')}）：{r.get('task_description', '')}")
            lines.append(f"  解决思路：{s.get('approach', '')}")
            if s.get("key_findings"):
                lines.append(f"  关键发现：{'；'.join(s['key_findings'][:3])}")
            if rg.get("effective_sequence"):
                lines.append(f"  有效工具顺序：{' → '.join(rg['effective_sequence'])}")
            if rg.get("pitfalls"):
                lines.append(f"  注意事项：{rg['pitfalls'][0]}")
            lines.append("")

        return "\n".join(lines)

    # ─── 查看所有菜谱 ─────────────────────────────────────────────────────

    def list_recipes(self, scenario_id: Optional[str] = None) -> list[dict]:
        """列出所有（或指定场景的）菜谱摘要"""
        results = []
        search_dir = RECIPES_DIR / scenario_id if scenario_id else RECIPES_DIR
        if not search_dir.exists():
            return []

        pattern = "**/*.json" if not scenario_id else "*.json"
        for fp in sorted(search_dir.glob(pattern), reverse=True):
            try:
                with open(fp, encoding="utf-8") as f:
                    r = json.load(f)
                results.append({
                    "file": fp.name,
                    "scenario": r.get("scenario_id"),
                    "date": r.get("run_date"),
                    "task": r.get("task_description", "")[:40],
                    "problem_solved": r.get("summary", {}).get("problem_solved", ""),
                })
            except Exception:
                continue
        return results

    # ─── 内部方法 ─────────────────────────────────────────────────────────

    def _extract_execution_trace(self, messages: list[dict]) -> dict:
        """从消息历史中提取执行轨迹（工具序列、工具结果摘要）"""
        tool_sequence = []
        tool_results_sample = []

        for m in messages:
            role = m.get("role", "")
            if role == "assistant" and isinstance(m, dict):
                # OpenAI message 对象
                tool_calls = getattr(m, "tool_calls", None) or (
                    m.get("tool_calls") if isinstance(m, dict) else None
                )
                if tool_calls:
                    for tc in tool_calls:
                        name = (
                            tc.function.name
                            if hasattr(tc, "function")
                            else tc.get("function", {}).get("name", "")
                        )
                        if name:
                            tool_sequence.append(name)
            elif role == "tool":
                content = m.get("content", "")
                if len(content) > 200:
                    content = content[:200] + "..."
                tool_results_sample.append(content)

        return {
            "tool_sequence": tool_sequence,
            "tool_count": len(tool_sequence),
            "tool_results_sample": tool_results_sample[:3],
        }

    def _generate_recipe(
        self,
        scenario_id: str,
        task_description: str,
        final_output: str,
        execution_trace: dict,
        metadata: Optional[dict],
    ) -> dict:
        """调用 LLM，将执行过程归纳为结构化菜谱"""
        prompt = f"""你是一个营销 Agent 执行记录归纳专家。
请将以下 Agent 执行过程归纳为结构化菜谱，用于未来相似任务的复用。

【任务描述】{task_description}
【场景ID】{scenario_id}
【工具调用顺序】{' → '.join(execution_trace['tool_sequence']) if execution_trace['tool_sequence'] else '无工具调用'}
【工具调用次数】{execution_trace['tool_count']}
【最终输出摘要】{final_output[:500] if final_output else '（无）'}

请输出严格 JSON，结构如下（所有字段均为中文）：
{{
  "summary": {{
    "problem_solved": "一句话描述解决了什么问题",
    "approach": "2-3句话描述解决思路",
    "key_findings": ["发现1", "发现2", "发现3"],
    "output_type": "输出形态，如：飞书竞品威胁报告"
  }},
  "reuse_guide": {{
    "when_to_reuse": "描述什么情况下应该参考本菜谱",
    "effective_sequence": ["工具1", "工具2"],
    "pitfalls": ["注意事项1"],
    "template_hints": "对下次执行的补充建议"
  }},
  "tags": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"]
}}"""

        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            generated = json.loads(resp.choices[0].message.content)
        except Exception as e:
            # 归纳失败时用基础结构
            generated = {
                "summary": {
                    "problem_solved": f"执行了 {scenario_id} 场景任务",
                    "approach": task_description,
                    "key_findings": [],
                    "output_type": "文本输出",
                },
                "reuse_guide": {
                    "when_to_reuse": f"执行 {scenario_id} 相关任务时",
                    "effective_sequence": execution_trace["tool_sequence"],
                    "pitfalls": [],
                    "template_hints": "",
                },
                "tags": [scenario_id],
            }

        recipe = {
            "scenario_id": scenario_id,
            "run_date": date.today().isoformat(),
            "task_description": task_description,
            "execution": {
                "tool_sequence": execution_trace["tool_sequence"],
                "total_tool_calls": execution_trace["tool_count"],
            },
            **generated,
        }
        return recipe
