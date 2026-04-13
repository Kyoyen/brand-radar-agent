"""
Session Summarizer — 执行经验沉淀模块
=======================================
每次 Agent 完成任务后，自动将本次执行过程提炼为「执行经验」，
存入经验库（memory/experience/）。下次遇到相似任务时，
自动从经验库中召回参考记录，注入执行上下文。

【为什么需要这个模块】
不加这个模块：每次执行都从零开始，相同的任务反复走弯路。
加了这个模块：Agent 会自动记住"上次怎么做的、发现了什么、哪里踩坑了"，
              越用越聪明，同类任务越跑越快、越跑越准。

【经验文件保存路径】
  memory/experience/{场景ID}/{日期}_{随机ID}.json

【每条经验记录的结构】
  {
    "scenario_id":      "competitive_analysis",   # 属于哪个场景
    "run_date":         "2025-01-15",              # 执行日期
    "task_description": "分析麦当劳小红书动态",     # 本次任务描述
    "execution": {
      "tool_sequence":  ["search_social_content", "send_feishu_report"],  # 实际调用了哪些工具、顺序
      "total_tool_calls": 4                        # 总调用次数
    },
    "summary": {
      "problem_solved": "分析了麦当劳在小红书的内容策略...",  # 解决了什么问题（1句话）
      "approach":       "先搜索内容，再对比热点...",           # 解决思路（2-3句）
      "key_findings":   ["发现1", "发现2"],                    # 本次关键结论（可直接复用）
      "output_type":    "飞书竞品威胁报告"                     # 输出形态
    },
    "experience_guide": {
      "when_to_reuse":      "下次分析同类竞品时参考",          # 什么情况下调用本条记录
      "effective_sequence": ["search_social_content", ...],   # 验证有效的工具顺序
      "pitfalls":           ["麦当劳抖音数据较多，注意去重"],   # 踩过的坑
      "next_time_hints":    "建议同时查小红书+抖音再综合"      # 下次执行的改进建议
    },
    "tags": ["麦当劳", "小红书", "竞品分析", "内容策略"]       # 用于相似任务匹配
  }
"""

import json
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Optional


EXPERIENCE_DIR = Path(__file__).parent.parent / "memory" / "experience"
EXPERIENCE_DIR.mkdir(parents=True, exist_ok=True)


class SessionSummarizer:
    """
    Agent 执行经验的「记录员」和「查询员」。

    记录员职责：任务结束后，把这次怎么做的、发现了什么提炼成结构化记录，存档。
    查询员职责：下次来了相似任务，从档案里找到最相关的记录，提供给 Agent 参考。
    """

    def __init__(self):
        # 延迟导入 OpenAI，避免未安装时报错
        self._client = None

    def _get_client(self):
        """获取 LLM 客户端（懒加载）"""
        if self._client is None:
            try:
                from framework.llm_client import LLMClient
                self._client = LLMClient()
            except Exception:
                # 兜底：直接用 OpenAI
                from openai import OpenAI
                from dotenv import load_dotenv
                load_dotenv()
                self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    # ─── 记录执行经验（任务结束后调用）────────────────────────────────────────

    def save_experience(
        self,
        scenario_id: str,
        task_description: str,
        final_output: str,
        messages: list,
        metadata: Optional[dict] = None,
    ) -> Path:
        """
        将本次执行过程归纳为经验记录并存档。

        参数：
          scenario_id       场景标识（如 competitive_analysis）
          task_description  本次任务的自然语言描述
          final_output      Agent 最终输出的文字结果
          messages          完整消息历史（用于提炼工具调用轨迹）
          metadata          附加信息（如工具调用次数）

        返回：存档文件路径
        """
        # 1. 从消息历史中提取工具调用轨迹
        trace = self._extract_tool_trace(messages)

        # 2. 让 LLM 将执行过程提炼为结构化经验
        experience = self._generate_experience(
            scenario_id, task_description, final_output, trace, metadata
        )

        # 3. 存档
        scenario_dir = EXPERIENCE_DIR / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}.json"
        filepath = scenario_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(experience, f, ensure_ascii=False, indent=2)

        return filepath

    # ─── 召回相关经验（任务开始前调用）────────────────────────────────────────

    def recall_experience(
        self,
        scenario_id: str,
        task_description: str,
        limit: int = 2,
    ) -> str:
        """
        根据场景和任务描述，找出最相关的历史经验，
        返回可直接注入 system prompt 的参考文本。

        返回空字符串表示暂无相关历史经验。
        """
        scenario_dir = EXPERIENCE_DIR / scenario_id
        if not scenario_dir.exists():
            return ""

        # 读取最近的经验文件（最多取 limit*3 个候选）
        candidates = []
        for fp in sorted(scenario_dir.glob("*.json"), reverse=True)[: limit * 3]:
            try:
                with open(fp, encoding="utf-8") as f:
                    record = json.load(f)
                candidates.append(record)
            except Exception:
                continue

        if not candidates:
            return ""

        # 按标签匹配度排序，选出最相关的
        task_lower = task_description.lower()
        scored = []
        for record in candidates:
            tags = record.get("tags", [])
            match_score = sum(1 for tag in tags if tag in task_lower)
            scored.append((match_score, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_records = [r for _, r in scored[:limit]]

        # 格式化为易读的参考文本
        lines = ["【历史执行经验参考】以下记录来自相似任务的真实执行，供本次参考：\n"]
        for i, rec in enumerate(top_records, 1):
            s = rec.get("summary", {})
            g = rec.get("experience_guide", {})
            lines.append(f"经验{i}（{rec.get('run_date', '')}）：{rec.get('task_description', '')}")
            lines.append(f"  · 解决思路：{s.get('approach', '')}")
            if s.get("key_findings"):
                lines.append(f"  · 关键结论：{'；'.join(s['key_findings'][:3])}")
            if g.get("effective_sequence"):
                lines.append(f"  · 有效工具顺序：{' → '.join(g['effective_sequence'])}")
            if g.get("pitfalls"):
                lines.append(f"  · 注意事项：{g['pitfalls'][0]}")
            if g.get("next_time_hints"):
                lines.append(f"  · 改进建议：{g['next_time_hints']}")
            lines.append("")

        return "\n".join(lines)

    # ─── 列出所有经验记录（供 run.py --experience 查看）──────────────────────

    def list_experience(self, scenario_id: Optional[str] = None) -> list[dict]:
        """列出所有已积累的执行经验摘要"""
        results = []
        root = EXPERIENCE_DIR / scenario_id if scenario_id else EXPERIENCE_DIR
        if not root.exists():
            return []

        pattern = "**/*.json" if not scenario_id else "*.json"
        for fp in sorted(root.glob(pattern), reverse=True):
            try:
                with open(fp, encoding="utf-8") as f:
                    rec = json.load(f)
                results.append({
                    "scenario":       rec.get("scenario_id", ""),
                    "date":           rec.get("run_date", ""),
                    "task":           rec.get("task_description", "")[:45],
                    "problem_solved": rec.get("summary", {}).get("problem_solved", "")[:50],
                })
            except Exception:
                continue
        return results

    # ─── 内部方法 ─────────────────────────────────────────────────────────────

    def _extract_tool_trace(self, messages: list) -> dict:
        """从消息历史中提取工具调用轨迹"""
        tool_sequence = []
        for m in messages:
            # 兼容 dict 格式和 OpenAI Message 对象
            if isinstance(m, dict):
                tool_calls = m.get("tool_calls")
            else:
                tool_calls = getattr(m, "tool_calls", None)

            if tool_calls:
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        name = tc.get("function", {}).get("name", "")
                    else:
                        name = getattr(getattr(tc, "function", None), "name", "")
                    if name:
                        tool_sequence.append(name)

        return {
            "tool_sequence": tool_sequence,
            "total_tool_calls": len(tool_sequence),
        }

    def _generate_experience(
        self,
        scenario_id: str,
        task_description: str,
        final_output: str,
        trace: dict,
        metadata: Optional[dict],
    ) -> dict:
        """让 LLM 将执行过程提炼为结构化经验记录"""

        tool_seq_str = " → ".join(trace["tool_sequence"]) if trace["tool_sequence"] else "无工具调用"
        output_preview = final_output[:400] if final_output else "（无输出）"

        prompt = f"""你是一个 AI Agent 执行经验提炼专家。
请将以下执行过程提炼为结构化的经验记录，帮助未来遇到相似任务时更好地执行。

【本次执行信息】
- 场景：{scenario_id}
- 任务：{task_description}
- 工具调用顺序：{tool_seq_str}
- 工具调用次数：{trace['total_tool_calls']}
- 输出摘要：{output_preview}

请输出严格的 JSON，结构如下（全部中文）：
{{
  "summary": {{
    "problem_solved": "一句话：解决了什么问题",
    "approach": "2-3句话：怎么解决的",
    "key_findings": ["关键结论1", "关键结论2"],
    "output_type": "输出形态，如：飞书竞品威胁报告"
  }},
  "experience_guide": {{
    "when_to_reuse": "什么情况下参考本条经验",
    "effective_sequence": ["工具1", "工具2"],
    "pitfalls": ["注意事项1"],
    "next_time_hints": "下次执行的改进建议"
  }},
  "tags": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"]
}}"""

        try:
            client = self._get_client()
            # 兼容 LLMClient 和原生 OpenAI 客户端
            if hasattr(client, "chat_raw"):
                resp = client.chat_raw(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
            else:
                resp = client.chat.completions.create(
                    model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
            generated = json.loads(resp.choices[0].message.content)
        except Exception:
            generated = {
                "summary": {
                    "problem_solved": f"执行了 {scenario_id} 场景任务",
                    "approach": task_description,
                    "key_findings": [],
                    "output_type": "文本输出",
                },
                "experience_guide": {
                    "when_to_reuse": f"执行 {scenario_id} 相关任务时",
                    "effective_sequence": trace["tool_sequence"],
                    "pitfalls": [],
                    "next_time_hints": "",
                },
                "tags": [scenario_id],
            }

        return {
            "schema_version":  "1.0",
            "scenario_id":     scenario_id,
            "run_date":        date.today().isoformat(),
            "task_description": task_description,
            "execution":       trace,
            **generated,
        }
