# 当前状态

更新日期：2026-08-31

## 已有

- 一个可运行的 Python CLI Agent 原型。
- 多模型 Provider、工具调用、结构化输出和 Mock 回退代码。
- Google Trends、Hacker News、公开微博聚合和网页读取等早期工具尝试。

## 尚未完成

- 面向营销企划的 Dashboard。
- 瑞幸 / 咖啡品类 Replay 数据。
- 情报卡片去重、筛选、营销日历、关键词和 Brief 联动。
- 清晰的当前 Demo 与历史探索代码目录。

## 当前开发入口

以以下三份公开文档为准：

1. `README.md`
2. `docs/product/PRD.md`
3. `docs/product/ROADMAP.md`

下一步直接从开发计划第一步开始：先让默认 Replay 数据和单页 Dashboard 跑起来。

## 已知遗留

仓库中的 V1-V3、旧 CLI 场景、历史示例和工具代码来自早期探索。它们可以复用，但不应决定第一版 Demo 的结构。开发过程中应逐步移到 `legacy/`，保持默认入口清楚。
