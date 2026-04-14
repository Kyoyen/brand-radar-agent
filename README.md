# Brand Radar Agent — V3 ReAct Agent

> 这是 V3 版本快照分支，展示引入工具调用和飞书推送后的版本。

## 这个分支做了什么

解决 V2 遗留问题：**Agent 只能直线执行，无法自主决策工具调用顺序**。

- 接入 OpenAI Function Calling，Agent 自主选择工具和调用顺序
- 实现完整 ReAct 循环（Think → Tool Call → Observe → repeat）
- 结果以飞书卡片格式推送，颜色按威胁等级变化
- 4 个工具：搜索社媒内容、获取热点话题、发送飞书报告、保存历史

## 关键结论

工具调用显著提升了任务灵活性。Agent 可以根据观察结果动态决定下一步：比如发现某个热点后，主动再搜一次相关内容。

## 局限性（故意保留）

- 场景单一（只有竞品监控），扩展需要改代码
- 无跨任务记忆，每次从零开始
- LLM 平台锁定（只支持 OpenAI）

**→ 进化到 V4（main 分支）：多场景路由 + LLM 抽象 + 三层记忆**

---
联系：stevesky233@gmail.com | [查看 V4 完整框架](https://github.com/kyoyen/brand-radar-agent)
