# Marketing Agent OS — framework 包
# 对外暴露的核心类，业务代码从这里导入即可

from .agent_runner import AgentRunner
from .context_manager import ContextManager
from .session_summarizer import SessionSummarizer
from .llm_client import LLMClient
from .pain_point_intake import PainPointIntake

__all__ = [
    "AgentRunner",       # 场景路由 + ReAct 主循环
    "ContextManager",    # 上下文压缩 + 持久化记忆
    "SessionSummarizer", # 执行经验沉淀 + 召回
    "LLMClient",         # 大模型接口抽象（支持切换 OpenAI/Claude/国内模型）
    "PainPointIntake",   # 痛点录入工具
]
