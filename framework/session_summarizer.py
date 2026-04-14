"""
Session Summarizer — 执行经验沉淀
====================================
每次任务结束后，自动将执行过程提炼为结构化「执行经验」存入经验库。
下次遇到相似任务时，自动召回参考，Agent 越用越聪明。

经验文件路径：memory/experience/{场景}/{日期}_{ID}.json
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
    def __init__(self):
        self._llm = None

    def _get_llm(self):
        if not self._llm:
            from .llm_client import LLMClient
            self._llm = LLMClient()
        return self._llm

    def save_experience(self, scenario_id: str, task_description: str,
                        final_output: str, messages: list, metadata: Optional[dict] = None) -> Path:
        """任务结束后调用，提炼并存档执行经验。"""
        trace = self._extract_trace(messages)
        record = self._generate_record(scenario_id, task_description, final_output, trace)

        save_dir = EXPERIENCE_DIR / scenario_id
        save_dir.mkdir(parents=True, exist_ok=True)
        fp = save_dir / f"{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}.json"
        fp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return fp

    def recall_experience(self, scenario_id: str, task_description: str, limit: int = 2) -> str:
        """召回相关历史经验，返回可注入 system prompt 的文本。"""
        exp_dir = EXPERIENCE_DIR / scenario_id
        if not exp_dir.exists():
            return ""

        candidates = []
        for fp in sorted(exp_dir.glob("*.json"), reverse=True)[:limit * 3]:
            try:
                candidates.append(json.loads(fp.read_text(encoding="utf-8")))
            except Exception:
                continue
        if not candidates:
            return ""

        task_lower = task_description.lower()
        scored = sorted(candidates, key=lambda r: sum(1 for t in r.get("tags",[]) if t in task_lower), reverse=True)

        lines = ["【历史执行经验参考】\n"]
        for i, r in enumerate(scored[:limit], 1):
            s = r.get("summary", {})
            g = r.get("experience_guide", {})
            lines.append(f"经验{i}（{r.get('run_date','')}）：{r.get('task_description','')}")
            if s.get("approach"):         lines.append(f"  · 解决思路：{s['approach']}")
            if s.get("key_findings"):     lines.append(f"  · 关键结论：{'；'.join(s['key_findings'][:2])}")
            if g.get("effective_sequence"): lines.append(f"  · 工具顺序：{' → '.join(g['effective_sequence'])}")
            if g.get("pitfalls"):         lines.append(f"  · 注意：{g['pitfalls'][0]}")
            lines.append("")
        return "\n".join(lines)

    def list_experience(self, scenario_id: Optional[str] = None) -> list:
        root = EXPERIENCE_DIR / scenario_id if scenario_id else EXPERIENCE_DIR
        if not root.exists():
            return []
        results = []
        for fp in sorted(root.glob("**/*.json"), reverse=True):
            try:
                r = json.loads(fp.read_text(encoding="utf-8"))
                results.append({
                    "scenario": r.get("scenario_id",""),
                    "date":     r.get("run_date",""),
                    "task":     r.get("task_description","")[:45],
                    "problem_solved": r.get("summary",{}).get("problem_solved","")[:50],
                })
            except Exception:
                continue
        return results

    def _extract_trace(self, messages: list) -> dict:
        seq = []
        for m in messages:
            tcs = m.get("tool_calls") if isinstance(m, dict) else getattr(m, "tool_calls", None)
            if tcs:
                for tc in tcs:
                    name = (tc.get("function",{}).get("name") if isinstance(tc, dict)
                            else getattr(getattr(tc,"function",None),"name",""))
                    if name:
                        seq.append(name)
        return {"tool_sequence": seq, "total_tool_calls": len(seq)}

    def _generate_record(self, scenario_id, task_description, final_output, trace) -> dict:
        seq_str = " → ".join(trace["tool_sequence"]) or "无工具调用"
        prompt = f"""将以下 Agent 执行过程提炼为经验记录（全部中文，严格 JSON）：

场景：{scenario_id}
任务：{task_description}
工具顺序：{seq_str}
工具调用次数：{trace['total_tool_calls']}
输出摘要：{final_output[:400]}

输出格式：
{{
  "summary": {{
    "problem_solved": "一句话：解决了什么",
    "approach": "2-3句：怎么解决的",
    "key_findings": ["结论1","结论2"],
    "output_type": "输出形态"
  }},
  "experience_guide": {{
    "when_to_reuse": "何时参考本条",
    "effective_sequence": ["工具1","工具2"],
    "pitfalls": ["注意事项"],
    "next_time_hints": "下次改进建议"
  }},
  "tags": ["关键词1","关键词2","关键词3","关键词4","关键词5"]
}}"""
        try:
            resp = self._get_llm().chat(
                messages=[{"role":"user","content":prompt}],
                temperature=0.3,
                response_format={"type":"json_object"},
            )
            generated = json.loads(resp.choices[0].message.content)
        except Exception:
            generated = {
                "summary": {"problem_solved": f"{scenario_id}任务","approach":task_description,"key_findings":[],"output_type":"文本"},
                "experience_guide": {"when_to_reuse":f"{scenario_id}相关任务","effective_sequence":trace["tool_sequence"],"pitfalls":[],"next_time_hints":""},
                "tags": [scenario_id],
            }
        return {"schema_version":"1.0","scenario_id":scenario_id,"run_date":date.today().isoformat(),
                "task_description":task_description,"execution":trace,**generated}
