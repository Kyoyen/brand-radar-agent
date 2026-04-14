# Brand Radar Agent — V2 结构化输出

> 这是 V2 版本快照分支，展示引入 Pydantic 结构化输出后的版本。

## 这个分支做了什么

解决 V1 遗留问题：**输出不稳定，结果难以程序化处理**。

- 引入 Pydantic v2 Schema 约束 LLM 输出格式
- 竞品报告输出为结构化 JSON，含威胁等级分级（high/medium/low）
- 可直接接入下游系统（飞书、数据库、看板）

```python
class CompetitorReport(BaseModel):
    brand: str
    platform: str
    post_count: int
    threat_level: Literal['high', 'medium', 'low']
    key_findings: list[str]
    recommended_actions: list[str]
```

## 关键结论

结构化输出是 Agent 结果「可信赖」的前提。LLM 能力再强，如果输出格式不可控，下游系统就无法消费。

## 局限性（故意保留）

- 执行路径仍然固定，Agent 无法自主决策工具调用顺序
- 数据仍为 Mock，无真实平台 API

**→ 进化到 V3（v3-agent 分支）：OpenAI Function Calling + 真正的工具调用**

---
联系：stevesky233@gmail.com | [查看 V4 完整框架](https://github.com/kyoyen/brand-radar-agent)
