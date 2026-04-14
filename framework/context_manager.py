"""
Context Manager — 双层上下文管理
==================================
Layer 1：执行中压缩 — 每 N 次工具调用，LLM 生成进度快照，压缩消息队列
Layer 2：任务后持久化 — 完成后存 JSON，下次自动加载历史，Agent 有记忆
"""

import json
import os
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MEMORY_DIR = Path(__file__).parent.parent / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
CHECKPOINT_EVERY = int(os.getenv("AGENT_CHECKPOINT_EVERY", 5))


class ContextManager:
    def __init__(self, scenario: str, task_description: str):
        self.scenario         = scenario
        self.task_description = task_description
        self.tool_call_count  = 0
        self.checkpoints      = []
        self.session_id       = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._llm             = None

    def _get_llm(self):
        if not self._llm:
            from .llm_client import LLMClient
            self._llm = LLMClient()
        return self._llm

    # ── Layer 1：执行中压缩 ───────────────────────────────────────────────────

    def record_tool_call(self):
        self.tool_call_count += 1

    def should_checkpoint(self) -> bool:
        return self.tool_call_count > 0 and self.tool_call_count % CHECKPOINT_EVERY == 0

    def compress(self, messages: list) -> list:
        """压缩消息队列，防止超出模型上下文限制。"""
        tool_results = [m["content"] for m in messages if m.get("role") == "tool"]
        if not tool_results:
            return messages

        summary = self._summarize(tool_results)
        self.checkpoints.append({"turn": self.tool_call_count, "summary": summary,
                                   "ts": datetime.now().isoformat()})

        system_msgs   = [m for m in messages if m.get("role") == "system"]
        user_msgs     = [m for m in messages if m.get("role") == "user"]
        recent_assist = [m for m in messages if m.get("role") == "assistant"][-2:]

        compressed = system_msgs + user_msgs + [{
            "role": "system",
            "content": f"[进度快照 第{self.tool_call_count}次工具调用后]\n{summary}\n\n请基于此继续完成任务。"
        }] + recent_assist

        print(f"  [压缩] {len(messages)} → {len(compressed)} 条消息")
        return compressed

    def _summarize(self, tool_results: list) -> str:
        combined = "\n---\n".join(tool_results[:10])
        try:
            resp = self._get_llm().chat(
                messages=[
                    {"role": "system", "content":
                     "将以下工具调用结果压缩为结构化摘要（200字内），保留关键数据和结论。"
                     "格式：已完成 / 关键发现 / 待完成"},
                    {"role": "user", "content": combined},
                ],
                temperature=0.1, max_tokens=400,
            )
            return resp.choices[0].message.content
        except Exception:
            return f"工具调用摘要（{len(tool_results)}条）：{combined[:300]}"

    # ── Layer 2：任务后持久化 ─────────────────────────────────────────────────

    def save_session(self, final_output: str, metadata: dict = None) -> str:
        scenario_dir = MEMORY_DIR / self.scenario
        scenario_dir.mkdir(exist_ok=True)

        data = {
            "session_id":       self.session_id,
            "scenario":         self.scenario,
            "task_description": self.task_description,
            "date":             date.today().isoformat(),
            "total_tool_calls": self.tool_call_count,
            "checkpoints":      self.checkpoints,
            "final_output":     final_output,
            "metadata":         metadata or {},
            "next_actions":     self._extract_next_actions(final_output),
        }

        fp = scenario_dir / f"{date.today().isoformat()}_{self.session_id}.json"
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  [记忆] 已存档：{fp.name}")
        return str(fp)

    def _extract_next_actions(self, text: str) -> list:
        try:
            resp = self._get_llm().chat(
                messages=[
                    {"role": "system", "content": "从以下报告提取2-3条「下次需要跟进的行动」，每条15字内，列表输出。"},
                    {"role": "user",   "content": text[:1500]},
                ],
                temperature=0.1, max_tokens=200,
            )
            lines = [l.lstrip("•-123456789. ").strip()
                     for l in resp.choices[0].message.content.split("\n")
                     if l.strip() and len(l.strip()) > 3]
            return lines[:3]
        except Exception:
            return []

    def load_relevant_history(self, limit: int = 3) -> str:
        scenario_dir = MEMORY_DIR / self.scenario
        if not scenario_dir.exists():
            return ""
        files = sorted(scenario_dir.glob("*.json"), reverse=True)[:limit]
        if not files:
            return ""
        parts = []
        for f in files:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                parts.append(
                    f"[{d['date']}] {d['task_description']}\n"
                    f"关键发现：{d['final_output'][:200]}...\n"
                    f"下次行动：{' / '.join(d.get('next_actions', []))}"
                )
            except Exception:
                continue
        return f"【历史记忆（最近{len(parts)}次）】\n" + "\n\n".join(parts) + "\n" if parts else ""
