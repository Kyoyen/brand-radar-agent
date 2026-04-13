"""
LLM Client — 大模型接口抽象层
================================
这个文件的作用：让整个项目可以随时切换底层大模型，
而不需要修改任何业务代码。

【切换方法】
只需在 .env 文件中修改以下两行：
  LLM_PROVIDER=openai          # 可选：openai / anthropic / zhipu / moonshot
  LLM_MODEL=gpt-4o-mini        # 填对应平台的模型名

【各平台模型推荐】
  OpenAI（默认）：
    LLM_PROVIDER=openai
    LLM_MODEL=gpt-4o-mini      # 便宜，够用
    LLM_MODEL=gpt-4o           # 更强，更贵

  Anthropic Claude：
    LLM_PROVIDER=anthropic
    LLM_MODEL=claude-haiku-4-5-20251001   # 便宜
    LLM_MODEL=claude-sonnet-4-6           # 更强

  智谱 AI（国内）：
    LLM_PROVIDER=zhipu
    LLM_MODEL=glm-4-flash      # 免费额度

  Moonshot（月之暗面，国内）：
    LLM_PROVIDER=moonshot
    LLM_MODEL=moonshot-v1-8k

【对接新模型】
在 LLMClient._build_client() 中按照注释格式添加新的 elif 分支即可。
"""

import os
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """
    统一大模型调用接口。
    对外只暴露 chat() 和 parse() 两个方法，屏蔽底层差异。
    """

    def __init__(
        self,
        provider: str = None,
        model: str = None,
        api_key: str = None,
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        self.model = model or os.getenv("LLM_MODEL", self._default_model())
        self.api_key = api_key or self._load_api_key()
        self._client = self._build_client()

    # ─── 公开接口（业务代码只用这两个）──────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        response_format: dict = None,
    ):
        """
        发送对话请求，返回原始 response 对象。

        参数：
          messages        消息列表，格式同 OpenAI：[{"role": "user", "content": "..."}]
          tools           Function Calling 工具定义列表（不需要时传 None）
          temperature     随机性，0=最稳定，1=最随机
          response_format 强制 JSON 输出：{"type": "json_object"}
        """
        if self.provider == "openai":
            return self._chat_openai(messages, tools, temperature, max_tokens, response_format)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages, tools, temperature, max_tokens)
        elif self.provider in ("zhipu", "moonshot", "deepseek"):
            # 这三家都兼容 OpenAI 接口格式，直接复用
            return self._chat_openai(messages, tools, temperature, max_tokens, response_format)
        else:
            raise ValueError(
                f"不支持的 LLM_PROVIDER: {self.provider}\n"
                f"支持的选项：openai / anthropic / zhipu / moonshot / deepseek"
            )

    def parse(self, messages: list[dict], schema_class, temperature: float = 0.2):
        """
        结构化输出接口：让 LLM 输出符合 Pydantic Schema 的 JSON，自动解析为对象。
        目前仅 OpenAI 支持，其他 provider 退回 JSON 模式并手动解析。
        """
        if self.provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            return client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=schema_class,
                temperature=temperature,
            )
        else:
            # 非 OpenAI 平台：用 JSON 模式 + 手动 parse 兜底
            import json
            resp = self.chat(
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            # 包装成类似 OpenAI parse 的返回结构
            class _FakeMessage:
                def __init__(self, obj):
                    self.parsed = obj
                    self.content = content
            class _FakeChoice:
                def __init__(self, obj):
                    self.message = _FakeMessage(obj)
                    self.finish_reason = "stop"
            class _FakeResp:
                def __init__(self, obj):
                    self.choices = [_FakeChoice(obj)]
            try:
                obj = schema_class.model_validate_json(content)
            except Exception:
                obj = schema_class(**json.loads(content))
            return _FakeResp(obj)

    def chat_raw(self, messages, **kwargs):
        """兼容原生 OpenAI client.chat.completions.create 调用方式"""
        return self.chat(messages, **kwargs)

    # ─── 内部实现 ─────────────────────────────────────────────────────────────

    def _build_client(self):
        """根据 provider 初始化底层 SDK 客户端"""
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self.api_key)

        elif self.provider == "anthropic":
            try:
                import anthropic
                return anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("使用 Anthropic 需要先安装：pip install anthropic")

        elif self.provider == "zhipu":
            # 智谱 AI 兼容 OpenAI 接口
            from openai import OpenAI
            return OpenAI(
                api_key=self.api_key,
                base_url="https://open.bigmodel.cn/api/paas/v4/"
            )

        elif self.provider == "moonshot":
            from openai import OpenAI
            return OpenAI(
                api_key=self.api_key,
                base_url="https://api.moonshot.cn/v1"
            )

        elif self.provider == "deepseek":
            from openai import OpenAI
            return OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1"
            )

        else:
            # 未知 provider：尝试用 OpenAI 客户端 + 自定义 base_url
            base_url = os.getenv("LLM_BASE_URL")
            if base_url:
                from openai import OpenAI
                return OpenAI(api_key=self.api_key, base_url=base_url)
            raise ValueError(f"未知的 LLM_PROVIDER: {self.provider}")

    def _chat_openai(self, messages, tools, temperature, max_tokens, response_format):
        """OpenAI / 兼容 OpenAI 接口的统一调用"""
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if response_format:
            kwargs["response_format"] = response_format
        return self._client.chat.completions.create(**kwargs)

    def _chat_anthropic(self, messages, tools, temperature, max_tokens):
        """Anthropic Claude 接口调用，转换消息格式"""
        # 提取 system 消息
        system_msg = next(
            (m["content"] for m in messages if m["role"] == "system"), ""
        )
        user_messages = [m for m in messages if m["role"] != "system"]

        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_msg,
            messages=user_messages,
        )
        if tools:
            # 转换工具格式：OpenAI → Anthropic
            kwargs["tools"] = self._convert_tools_to_anthropic(tools)

        raw = self._client.messages.create(**kwargs)

        # 将 Anthropic 响应包装成 OpenAI 格式（让业务代码无感知）
        return self._wrap_anthropic_response(raw)

    def _convert_tools_to_anthropic(self, openai_tools: list) -> list:
        """将 OpenAI 工具定义格式转换为 Anthropic 格式"""
        result = []
        for t in openai_tools:
            fn = t.get("function", {})
            result.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {}),
            })
        return result

    def _wrap_anthropic_response(self, raw):
        """将 Anthropic 响应包装为 OpenAI 格式，让业务代码零改动"""
        import json

        class _ToolCall:
            def __init__(self, block):
                self.id = block.id
                self.type = "function"
                class _Fn:
                    name = block.name
                    arguments = json.dumps(block.input, ensure_ascii=False)
                self.function = _Fn()

        class _Message:
            def __init__(self, raw):
                text_parts = [b.text for b in raw.content if hasattr(b, "text")]
                tool_parts = [b for b in raw.content if b.type == "tool_use"]
                self.content = " ".join(text_parts) if text_parts else None
                self.tool_calls = [_ToolCall(b) for b in tool_parts] or None
                self.role = "assistant"

        class _Choice:
            def __init__(self, raw):
                self.message = _Message(raw)
                stop_reason = raw.stop_reason
                self.finish_reason = "stop" if stop_reason == "end_turn" else "tool_calls"

        class _Response:
            def __init__(self, raw):
                self.choices = [_Choice(raw)]

        return _Response(raw)

    def _default_model(self) -> str:
        defaults = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-haiku-4-5-20251001",
            "zhipu": "glm-4-flash",
            "moonshot": "moonshot-v1-8k",
            "deepseek": "deepseek-chat",
        }
        return defaults.get(self.provider, "gpt-4o-mini")

    def _load_api_key(self) -> str:
        key_map = {
            "openai":    "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "zhipu":     "ZHIPU_API_KEY",
            "moonshot":  "MOONSHOT_API_KEY",
            "deepseek":  "DEEPSEEK_API_KEY",
        }
        env_var = key_map.get(self.provider, "OPENAI_API_KEY")
        key = os.getenv(env_var)
        if not key:
            raise EnvironmentError(
                f"缺少环境变量 {env_var}。\n"
                f"请在 .env 文件中添加：{env_var}=你的密钥"
            )
        return key

    def __repr__(self):
        return f"LLMClient(provider={self.provider}, model={self.model})"
