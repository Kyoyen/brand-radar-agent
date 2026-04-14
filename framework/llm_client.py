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
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        self.model    = model    or os.getenv("LLM_MODEL", self._default_model())
        self.api_key  = api_key  or self._load_api_key()
        self._client  = self._build_client()

    # ── 公开接口 ──────────────────────────────────────────────────────────────

    def chat(self, messages: list, tools: list = None, temperature: float = 0.2,
             max_tokens: int = 2000, response_format: dict = None):
        """统一对话接口，屏蔽底层平台差异。"""
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
        return f"LLMClient(provider={self.provider}, model={self.model})"

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

    def _default_model(self):
        return {"openai":"gpt-4o-mini","anthropic":"claude-haiku-4-5-20251001",
                "zhipu":"glm-4-flash","moonshot":"moonshot-v1-8k","deepseek":"deepseek-chat"}.get(self.provider,"gpt-4o-mini")

    def _load_api_key(self):
        key_map = {"openai":"OPENAI_API_KEY","anthropic":"ANTHROPIC_API_KEY",
                   "zhipu":"ZHIPU_API_KEY","moonshot":"MOONSHOT_API_KEY","deepseek":"DEEPSEEK_API_KEY"}
        key = os.getenv(key_map.get(self.provider, "OPENAI_API_KEY"))
        if not key:
            env_var = key_map.get(self.provider, "OPENAI_API_KEY")
            raise EnvironmentError(f"缺少 {env_var}，请在 .env 中添加。")
        return key
