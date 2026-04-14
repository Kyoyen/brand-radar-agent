"""
LLM Client — 大模型接口抽象层
================================
切换底层模型只需修改 .env 两行，业务代码零改动。

支持的模型平台（LLM_PROVIDER）：
  openai    — GPT-4o-mini / GPT-4o（默认）
  anthropic — Claude Haiku / Sonnet
  deepseek  — DeepSeek Chat（国内可用，价格低）
  moonshot  — 月之暗面 Kimi
  zhipu     — 智谱 GLM（有免费额度）

切换示例（只改 .env）：
  LLM_PROVIDER=deepseek
  LLM_MODEL=deepseek-chat
  DEEPSEEK_API_KEY=sk-...
"""

import os
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    def __init__(self, provider: str = None, model: str = None, api_key: str = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "deepseek")).lower()
        self.model    = model    or os.getenv("LLM_MODEL", self._default_model())
        # 缺 key 时降级 Mock，让框架在零配置下也能跑通
        try:
            self.api_key = api_key or self._load_api_key()
            self._client = self._build_client()
            self._mock   = False
        except EnvironmentError:
            print(f"  [⚠ MOCK 模式] 未配置 {self.provider} API Key，已启用 MockProvider")
            print(f"  [提示] 配置 .env 中的 API Key 即可切换到真实模型")
            self.api_key = None
            self._client = None
            self._mock   = True

    # ── 公开接口 ──────────────────────────────────────────────────────────────

    def chat(self, messages: list, tools: list = None, temperature: float = 0.2,
             max_tokens: int = 2000, response_format: dict = None):
        """统一对话接口，屏蔽底层平台差异。"""
        if self._mock:
            return self._chat_mock(messages, tools)
        if self.provider in ("openai", "zhipu", "moonshot", "deepseek"):
            return self._chat_openai_compat(messages, tools, temperature, max_tokens, response_format)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages, tools, temperature, max_tokens)
        else:
            raise ValueError(f"不支持的 LLM_PROVIDER: {self.provider}。可选：openai/anthropic/deepseek/moonshot/zhipu")

    def parse(self, messages: list, schema_class, temperature: float = 0.2):
        """结构化输出：让模型输出符合 Pydantic Schema 的 JSON。"""
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self.api_key).beta.chat.completions.parse(
                model=self.model, messages=messages,
                response_format=schema_class, temperature=temperature,
            )
        # 非 OpenAI 平台：JSON 模式 + 手动解析兜底
        import json
        resp = self.chat(messages, temperature=temperature, response_format={"type": "json_object"})
        content = resp.choices[0].message.content
        class _Msg:
            parsed = schema_class.model_validate_json(content)
        class _Choice:
            message = _Msg(); finish_reason = "stop"
        class _Resp:
            choices = [_Choice()]
        return _Resp()

    def __repr__(self):
        suffix = " [MOCK]" if self._mock else ""
        return f"LLMClient(provider={self.provider}, model={self.model}){suffix}"

    # ── 内部实现 ──────────────────────────────────────────────────────────────

    def _build_client(self):
        from openai import OpenAI
        base_urls = {
            "zhipu":    "https://open.bigmodel.cn/api/paas/v4/",
            "moonshot": "https://api.moonshot.cn/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }
        if self.provider == "anthropic":
            try:
                import anthropic
                return anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("pip install anthropic")
        return OpenAI(api_key=self.api_key, base_url=base_urls.get(self.provider))

    def _chat_openai_compat(self, messages, tools, temperature, max_tokens, response_format):
        kwargs = dict(model=self.model, messages=messages,
                      temperature=temperature, max_tokens=max_tokens)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if response_format:
            kwargs["response_format"] = response_format
        return self._client.chat.completions.create(**kwargs)

    def _chat_anthropic(self, messages, tools, temperature, max_tokens):
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs = [m for m in messages if m["role"] != "system"]
        kwargs = dict(model=self.model, max_tokens=max_tokens,
                      temperature=temperature, system=system, messages=user_msgs)
        if tools:
            kwargs["tools"] = [{"name": t["function"]["name"],
                                 "description": t["function"].get("description",""),
                                 "input_schema": t["function"].get("parameters",{})} for t in tools]
        raw = self._client.messages.create(**kwargs)
        return self._wrap_anthropic(raw)

    def _wrap_anthropic(self, raw):
        import json
        class _TC:
            def __init__(self, b):
                self.id = b.id; self.type = "function"
                class _F: name = b.name; arguments = json.dumps(b.input, ensure_ascii=False)
                self.function = _F()
        class _Msg:
            def __init__(self, r):
                self.content = " ".join(b.text for b in r.content if hasattr(b,"text")) or None
                self.tool_calls = [_TC(b) for b in r.content if b.type=="tool_use"] or None
                self.role = "assistant"
        class _Choice:
            def __init__(self, r):
                self.message = _Msg(r)
                self.finish_reason = "stop" if r.stop_reason=="end_turn" else "tool_calls"
        class _Resp:
            def __init__(self, r): self.choices = [_Choice(r)]
        return _Resp(raw)

    # ── Mock Provider — 零配置环境下驱动框架跑通 ─────────────────────────────

    def _chat_mock(self, messages, tools):
        """
        无 API Key 时的兜底实现。
        策略：
          1. 若有 tools 可调用 → 顺序触发每个未调用过的工具（避免死循环）
          2. 全部工具调过 → 返回符合 AgentOutput schema 的假 JSON，让流程正常结束
        """
        import json, uuid
        # 提取已调用过的工具名（防 ReAct 死循环）
        called = set()
        for m in messages:
            tcs = m.get("tool_calls") if isinstance(m, dict) else getattr(m, "tool_calls", None)
            if tcs:
                for tc in tcs:
                    name = (tc.get("function",{}).get("name") if isinstance(tc, dict)
                            else getattr(getattr(tc,"function",None),"name",""))
                    if name: called.add(name)

        # 还有未调用工具 → 返回 tool_calls
        if tools:
            for t in tools:
                tname = t["function"]["name"]
                if tname not in called:
                    schema = t["function"].get("parameters",{})
                    args   = self._stub_args(schema)
                    return self._wrap_tool_call(tname, args)

        # 工具都用过了 / 无工具 → 返回结构化最终答案
        return self._wrap_final(self._stub_agent_output(messages))

    def _stub_args(self, schema):
        """根据 JSON schema 生成最小合法参数"""
        props = schema.get("properties", {})
        required = schema.get("required", list(props.keys())[:1])
        out = {}
        for k in required:
            p = props.get(k, {})
            t = p.get("type", "string")
            out[k] = {"string":"测试","integer":1,"number":1.0,"boolean":True,
                      "array":["示例"],"object":{}}.get(t, "测试")
        return out

    def _stub_agent_output(self, messages):
        """生成符合 AgentOutput schema 的 mock JSON 字符串"""
        import json
        # 抽取 user 任务描述用于回填
        task = ""
        for m in messages:
            role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "")
            if role == "user":
                task = (m.get("content") if isinstance(m, dict) else getattr(m, "content", "")) or ""
                break
        return json.dumps({
            "scenario_id": "mock",
            "task_description": task[:80] or "mock 任务",
            "executive_summary": "[MOCK 输出] 当前未配置真实 LLM API Key，本结果为框架演示用。配置 .env 后即可获得真实分析。",
            "observations": [
                {"id":"O1","fact":"工具已被框架顺序调用，验证 ReAct 链路通畅","metric":None,"source":"mock"},
                {"id":"O2","fact":"记忆层、压缩层、经验归档已全部触发","metric":None,"source":"mock"},
                {"id":"O3","fact":"输出结构通过 Pydantic 校验","metric":None,"source":"mock"},
            ],
            "insights": [
                {"id":"I1","statement":"框架可在零依赖下完整运行","evidence_refs":["O1","O2","O3"],
                 "so_what":"用户可在不付费 API 的情况下先评估系统能力"},
            ],
            "decision_points": [],
            "actions": [
                {"id":"A1","what":"在 .env 中配置 DEEPSEEK_API_KEY 切换到真实 LLM",
                 "why":"获得真实数据驱动的洞察",
                 "priority":"p0","effort":"low","confidence":"high",
                 "owner_hint":None,"evidence_refs":["I1"]},
            ],
            "open_questions": [],
            "next_check": None,
        }, ensure_ascii=False)

    def _wrap_tool_call(self, name, args):
        import json, uuid
        class _F:
            def __init__(self, n, a): self.name = n; self.arguments = json.dumps(a, ensure_ascii=False)
        class _TC:
            def __init__(self, n, a):
                self.id = f"call_{uuid.uuid4().hex[:8]}"
                self.type = "function"
                self.function = _F(n, a)
        class _Msg:
            def __init__(self):
                self.content = None
                self.tool_calls = [_TC(name, args)]
                self.role = "assistant"
        class _Choice:
            def __init__(self):
                self.message = _Msg()
                self.finish_reason = "tool_calls"
        class _Resp:
            def __init__(self): self.choices = [_Choice()]
        return _Resp()

    def _wrap_final(self, content):
        class _Msg:
            def __init__(self, c):
                self.content = c
                self.tool_calls = None
                self.role = "assistant"
        class _Choice:
            def __init__(self, c):
                self.message = _Msg(c)
                self.finish_reason = "stop"
        class _Resp:
            def __init__(self, c): self.choices = [_Choice(c)]
        return _Resp(content)

    def _default_model(self):
        return {"openai":"gpt-4o-mini","anthropic":"claude-haiku-4-5-20251001",
                "zhipu":"glm-4-flash","moonshot":"moonshot-v1-8k","deepseek":"deepseek-chat"}.get(self.provider,"deepseek-chat")

    def _load_api_key(self):
        key_map = {"openai":"OPENAI_API_KEY","anthropic":"ANTHROPIC_API_KEY",
                   "zhipu":"ZHIPU_API_KEY","moonshot":"MOONSHOT_API_KEY","deepseek":"DEEPSEEK_API_KEY"}
        key = os.getenv(key_map.get(self.provider, "OPENAI_API_KEY"))
        if not key:
            env_var = key_map.get(self.provider, "OPENAI_API_KEY")
            raise EnvironmentError(f"缺少 {env_var}，请在 .env 中添加。")
        return key
