# Brand Radar Agent — V1 POC

> 这是 V1 版本快照分支，展示最初的可行性验证阶段。

## 这个分支做了什么

用最简单的方式验证一个核心假设：**AI 能做竞品社媒监控这件事吗？**

- 单文件脚本（`v1_basic/agent.py`），约 100 行
- 硬编码测试数据，无工具调用，直接提问 LLM
- 输出：纯文本分析报告，格式不固定

## 关键结论

ReAct 模式（Think → Act → Observe）适用于营销监控类任务，但自由文本输出难以程序化处理。
这是推动 V2 引入 Pydantic 结构化输出的直接原因。

## 局限性（故意保留）

- 无工具调用，无法真正调用外部数据
- 输出不可预期，每次结果格式不同
- 无记忆，每次从零开始

**→ 进化到 V2（v2-structured 分支）：引入 Pydantic Schema，结果变为结构化 JSON**

---
联系：stevesky233@gmail.com | [查看 V4 完整框架](https://github.com/kyoyen/brand-radar-agent)
