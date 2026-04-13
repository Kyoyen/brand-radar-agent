"""
Context Manager — 双层上下文管理机制
======================================

Layer 1：执行中实时压缩（防止 context overflow）
  - 每 N 次工具调用后，让 LLM 生成一次「进度快照」
  - 将过去的详细 tool 结果压缩成摘要，注入为 system 消息
  - 旧的 tool 消息可安全裁剪，不影响后续推理

Layer 2：任务结束后持久化（跨会话记忆）
  - 任务完成后存储「本次做了什么 / 发现了什么 / 下次该做什么」
  - 下次启动时加载相关历史，Agent 有「记忆」
  - 支持按场景、品牌、日期检索

设计原则：
  - 压缩不丢失关键信息，只压缩细节
  - 持久化文件用 JSON，便于调试和手动查看
  - 开销最小：只在必要时调用 LLM 做摘要
"""

import json
import os
from datetime import datetime, date
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MEMORY_DIR = Path(__file__).parent.parent / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
CHECKPOINT_EVERY = 5   # 每 5 轮工具调用压缩一次


class ContextManager:
    def __init__(self, scenario: str, task_description: str):
        self.scenario = scenario
        self.task_description = task_description
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.tool_call_count = 0
        self.checkpoints: list[dict] = []   # 每次压缩生成的快照
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ─── Layer 1：执行中压缩 ────────────────────────────────────────────────

    def should_checkpoint(self) -> bool:
        """判断是否需要生成快照（每 CHECKPOINT_EVERY 次工具调用触发一次）"""
        return self.tool_call_count > 0 and self.tool_call_count % CHECKPOINT_EVERY == 0

    def record_tool_call(self):
        """每次工具调用后调用此方法，累计计数"""
        self.tool_call_count += 1

    def compress(self, messages: list[dict]) -> list[dict]:
        """
        压缩消息队列：
        1. 让 LLM 总结当前进度
        2. 移除旧的 tool 消息（保留 system + user + 最近 2 轮）
        3. 将摘要注入为新的 system 消息

        返回：压缩后的消息列表（token 更小，关键信息不丢失）
        """
        # 提取所有 tool 结果用于摘要
        tool_results = [
            m["content"] for m in messages
            if m.get("role") == "tool"
        ]
        if not tool_results:
            return messages

        # 让 LLM 生成进度摘要
        summary = self._generate_progress_summary(tool_results)
        self.checkpoints.append({
            "turn": self.tool_call_count,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        })

        # 重建消息队列：system + user + 摘要 + 最近 2 条 assistant 消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        user_msgs = [m for m in messages if m.get("role") == "user"]
        recent_assistant = [m for m in messages if m.get("role") == "assistant"][-2:]

        compressed = system_msgs + user_msgs + [
            {
                "role": "system",
                "content": f"[进度快照 - 第{self.tool_call_count}次工具调用后]\n{summary}\n\n请基于以上进度继续完成任务。",
            }
        ] + recent_assistant

        print(f"\n  [ContextManager] 已压缩（{len(messages)} → {len(compressed)} 条消息）")
        return compressed

    def _generate_progress_summary(self, tool_results: list[str]) -> str:
        """调用 LLM 对当前所有工具结果生成结构化摘要"""
        combined = "\n---\n".join(tool_results[:10])  # 最多取前10条
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个 Agent 进度追踪助手。"
                        "请将以下工具调用结果压缩为一段结构化摘要（200字以内），"
                        "保留：已发现的关键数据、重要结论、尚未完成的步骤。"
                        "格式：已完成 / 关键发现 / 待完成"
                    ),
                },
                {"role": "user", "content": f"工具调用结果：\n{combined}"},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        return resp.choices[0].message.content

    # ─── Layer 2：任务结束后持久化 ──────────────────────────────────────────

    def save_session(self, final_output: str, metadata: dict = None):
        """
        任务完成后存储完整会话摘要
        文件路径：memory/{scenario}/{date}_{session_id}.json
        """
        scenario_dir = MEMORY_DIR / self.scenario
        scenario_dir.mkdir(exist_ok=True)

        session_data = {
            "session_id": self.session_id,
            "scenario": self.scenario,
            "task_description": self.task_description,
            "date": date.today().isoformat(),
            "total_tool_calls": self.tool_call_count,
            "checkpoints": self.checkpoints,
            "final_output": final_output,
            "metadata": metadata or {},
            # Agent 自动生成的「下次行动建议」
            "next_actions": self._extract_next_actions(final_output),
        }

        file_path = scenario_dir / f"{date.today().isoformat()}_{self.session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        print(f"\n  [ContextManager] 会话已存档：{file_path.name}")
        return str(file_path)

    def _extract_next_actions(self, final_output: str) -> list[str]:
        """从最终输出中提取下次应关注的行动点"""
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "从以下分析报告中提取2-3条「下次需要重点跟进的行动」，以列表形式输出，每条15字以内。",
                },
                {"role": "user", "content": final_output[:1500]},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content
        # 简单解析：按行分割，去掉序号
        lines = [
            l.lstrip("•-123456789. ").strip()
            for l in raw.split("\n")
            if l.strip() and len(l.strip()) > 3
        ]
        return lines[:3]

    def load_relevant_history(self, limit: int = 3) -> str:
        """
        加载本场景最近 N 次会话摘要
        用于在新任务开始时注入历史上下文（让 Agent 有记忆）
        """
        scenario_dir = MEMORY_DIR / self.scenario
        if not scenario_dir.exists():
            return ""

        files = sorted(scenario_dir.glob("*.json"), reverse=True)[:limit]
        if not files:
            return ""

        summaries = []
        for f in files:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            summaries.append(
                f"[{data['date']}] {data['task_description']}\n"
                f"关键发现：{data['final_output'][:200]}...\n"
                f"下次行动：{' / '.join(data.get('next_actions', []))}"
            )

        history_text = "\n\n".join(summaries)
        return f"【历史会话记忆（最近{len(summaries)}次）】\n{history_text}\n"

    @staticmethod
    def list_sessions(scenario: str = None) -> list[dict]:
        """列出所有存档的会话（用于调试和回顾）"""
        sessions = []
        search_dir = MEMORY_DIR / scenario if scenario else MEMORY_DIR
        for f in sorted(search_dir.rglob("*.json"), reverse=True):
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            sessions.append({
                "date": data["date"],
                "scenario": data["scenario"],
                "task": data["task_description"][:50],
                "tool_calls": data["total_tool_calls"],
                "file": f.name,
            })
        return sessions
