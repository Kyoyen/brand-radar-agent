"""
LLM Client — 大模型接口抽象层
================================
切换底层模型只需修改 .env 两行，业务代码零改动。

支持的模型平台（LLM_PROVIDER）：
  openai    — GPT-4o-mini / GPT-4o（默认）
  anthropic — Claude Haiku / Sonnet
  deepseek  — DeepSeek V4 Flash（国内可用，价格低）
  moonshot  — 月之暗面 Kimi
  zhipu     — 智谱 GLM（有免费额度）

切换示例（只改 .env）：
  LLM_PROVIDER=deepseek
  LLM_MODEL=deepseek-v4-flash
  DEEPSEEK_API_KEY=
"""

import os
import time
from types import SimpleNamespace
from dotenv import load_dotenv

load_dotenv()


PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "zhipu": "ZHIPUAI_API_KEY",
}

PROVIDER_KEY_ENV_FALLBACKS = {
    "zhipu": ("ZHIPU_API_KEY",),
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "zhipu": "glm-4.7-flash",
    "moonshot": "moonshot-v1-8k",
    "deepseek": "deepseek-v4-flash",
}


class LLMConfigurationError(EnvironmentError):
    """Provider selection or credentials are not configured safely."""


class LLMRequestError(RuntimeError):
    """Sanitized provider failure that never includes credentials or headers."""

    SAFE_MESSAGES = {
        "authentication": "API Key 无效、已过期或未获当前模型授权",
        "network": "无法连接模型服务，请检查网络与代理",
        "rate_limit": "模型服务触发账户速率限制",
        "quota": "账户额度、套餐权限或调用上限不足",
        "request_rejected": "模型服务拒绝了请求参数",
        "provider_unavailable": "模型当前访问量过大或服务暂时不可用",
        "request_failed": "模型请求失败",
    }

    def __init__(self, category: str, provider: str, model: str, business_code: str | None = None):
        self.category = category
        self.provider = provider
        self.model = model
        self.business_code = business_code
        code_suffix = f", error_code={business_code}" if business_code else ""
        super().__init__(
            f"{self.SAFE_MESSAGES.get(category, self.SAFE_MESSAGES['request_failed'])}"
            f"（provider={provider}, model={model}{code_suffix}）"
        )

    @classmethod
    def from_exception(cls, exc: Exception, provider: str, model: str) -> "LLMRequestError":
        name = type(exc).__name__.lower()
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)

        body = getattr(exc, "body", None)
        error_body = body.get("error", body) if isinstance(body, dict) else {}
        raw_business_code = error_body.get("code") if isinstance(error_body, dict) else None
        business_code = str(raw_business_code) if raw_business_code is not None else None

        if business_code in {"1000", "1001", "1002", "1003", "1004"}:
            category = "authentication"
        elif business_code in {"1113", "1304", "1308", "1309", "1310", "1311"}:
            category = "quota"
        elif business_code == "1302":
            category = "rate_limit"
        elif business_code == "1305":
            category = "provider_unavailable"
        elif status in (401, 403) or "authentication" in name or "permissiondenied" in name:
            category = "authentication"
        elif status == 429 or "ratelimit" in name:
            category = "rate_limit"
        elif (
            "connection" in name
            or "connect" in name
            or "timeout" in name
            or "network" in name
        ):
            category = "network"
        elif status == 400 or "badrequest" in name:
            category = "request_rejected"
        elif isinstance(status, int) and status >= 500:
            category = "provider_unavailable"
        else:
            category = "request_failed"
        return cls(category, provider, model, business_code=business_code)


class LLMClient:
    def __init__(self, provider: str = None, model: str = None, api_key: str = None,
                 require_api: bool = False):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "deepseek")).lower()
        if self.provider not in PROVIDER_KEY_ENV:
            allowed = "/".join(PROVIDER_KEY_ENV)
            raise LLMConfigurationError(f"不支持的 LLM_PROVIDER: {self.provider}。可选：{allowed}")
        self.model    = model    or os.getenv("LLM_MODEL", self._default_model())
        # 只有“未配置 Key”允许进入 Mock；依赖或客户端配置错误必须明确失败。
        try:
            self.api_key = api_key or self._load_api_key()
        except LLMConfigurationError:
            if require_api:
                raise
            print(f"  [⚠ MOCK 模式] 未配置 {self.provider} API Key，已启用 MockProvider")
            print(f"  [提示] 配置 .env 中的 API Key 即可切换到真实模型")
            self.api_key = None
            self._client = None
            self._mock   = True
            return

        self._client = self._build_client()
        self._mock   = False

    # ── 公开接口 ──────────────────────────────────────────────────────────────

    def chat(self, messages: list, tools: list = None, temperature: float = 0.2,
             max_tokens: int = 2000, response_format: dict = None,
             stream_progress: bool = False):
        """统一对话接口，屏蔽底层平台差异。"""
        if self._mock:
            return self._chat_mock(messages, tools)
        try:
            if self.provider in ("openai", "zhipu", "moonshot", "deepseek"):
                return self._chat_openai_compat(
                    messages,
                    tools,
                    temperature,
                    max_tokens,
                    response_format,
                    stream_progress=stream_progress,
                )
            return self._chat_anthropic(messages, tools, temperature, max_tokens)
        except LLMRequestError:
            raise
        except Exception as exc:
            raise LLMRequestError.from_exception(exc, self.provider, self.model) from exc

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

    @property
    def is_mock(self) -> bool:
        return self._mock

    # ── 内部实现 ──────────────────────────────────────────────────────────────

    def _build_client(self):
        base_urls = {
            "zhipu":    "https://open.bigmodel.cn/api/paas/v4/",
            "moonshot": "https://api.moonshot.cn/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }
        if self.provider == "anthropic":
            try:
                import anthropic
                return anthropic.Anthropic(api_key=self.api_key, timeout=60.0, max_retries=0)
            except ImportError as exc:
                raise LLMConfigurationError(
                    "缺少 anthropic 依赖，无法调用 Anthropic Provider；请先安装 requirements.txt"
                ) from exc
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMConfigurationError(
                "缺少 openai 依赖，无法调用当前 OpenAI-compatible Provider；请先安装 requirements.txt"
            ) from exc
        return OpenAI(
            api_key=self.api_key,
            base_url=base_urls.get(self.provider),
            timeout=60.0,
            max_retries=0,
        )

    def _chat_openai_compat(
        self,
        messages,
        tools,
        temperature,
        max_tokens,
        response_format,
        stream_progress=False,
    ):
        kwargs = dict(model=self.model, messages=messages,
                      temperature=temperature, max_tokens=max_tokens)
        # DeepSeek V4 defaults to high-effort thinking. This client historically
        # used the non-thinking ``deepseek-chat`` path, and weekly JSON generation
        # needs the final answer rather than a reasoning-only response.
        if self.provider == "deepseek":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if response_format:
            kwargs["response_format"] = response_format
        if not stream_progress:
            return self._client.chat.completions.create(**kwargs)
        if tools:
            raise LLMConfigurationError("stream_progress 目前只用于无工具的结构化模型请求")

        kwargs["stream"] = True
        chunks = self._client.chat.completions.create(**kwargs)
        content_parts: list[str] = []
        finish_reason = None
        received_chunks = 0
        last_progress_at: float | None = None
        for chunk in chunks:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            received_chunks += 1
            if received_chunks == 1:
                print("  [模型响应] 已开始接收", flush=True)
                last_progress_at = time.monotonic()
            elif (
                last_progress_at is not None
                and time.monotonic() - last_progress_at >= 5.0
            ):
                print("  [模型响应] 持续接收中", flush=True)
                last_progress_at = time.monotonic()
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", None)
            if content:
                content_parts.append(content)
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="".join(content_parts),
                        role="assistant",
                        tool_calls=None,
                    ),
                    finish_reason=finish_reason or "stop",
                )
            ]
        )

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
        return DEFAULT_MODELS[self.provider]

    def _load_api_key(self):
        primary = PROVIDER_KEY_ENV[self.provider]
        candidates = (primary, *PROVIDER_KEY_ENV_FALLBACKS.get(self.provider, ()))
        for env_var in candidates:
            key = os.getenv(env_var)
            if key:
                return key
        accepted = " 或 ".join(candidates)
        raise LLMConfigurationError(f"缺少 {accepted}，请在本机 .env 或系统环境中配置。")
