# Development Notes

开发前依次阅读：

1. `README.md`
2. `docs/product/PRD.md`
3. `docs/business/NEXT-WEEK-WORKFLOW.md`
4. `docs/product/AGENT-BUILD.md`
5. `docs/product/ROADMAP.md`
6. `docs/PROJECT-STATE.md`
7. `docs/handoff/MACMINI-HANDOFF.md`

## 当前优先级

先让真实模型 API Key 驱动下周营销企划的完整 Agent 流程，再把同一份结果接到 Dashboard。

- 第一条业务链只做“瑞幸咖啡 / 现制咖啡 / 全国 + 上海”。
- 输入先用可复查的 Replay 材料和用户提供的公开来源。
- 无 Key 的 Mock 只做程序烟雾测试，不能算业务验收通过。
- 证据不足时保留“待核”，不补写成确定事实。
- Brief 只引用页面中存在的情报卡片。
- 任何发送、发布、投放和预算变更都停在人工确认前。
- 不引入多 Agent、数据库、账户、定时任务或复杂框架。

## 表达规则

- PRD、README 和业务流程使用营销企划语言，先写业务触发、材料、判断、交付和人工控制点。
- 模型模式、工具调用、数据结构和代码迁移只写在 `docs/product/AGENT-BUILD.md`。
- RealReplicaBench 只能以官方原始任务文件为来源；历史对话和本项目旧稿只用于定位，不能代替源头事实。
- 清楚区分阿里原始任务、从中提炼的工作方法、Brand Radar 的业务转译。

## 仓库规则

- 不提交密钥、Cookie、`.env`、虚拟环境或本地运行数据。
- 不强推默认分支，不运行历史发布脚本。
- 不把 Replay、Mock 输出或早期静态页面描述为实时产品结果。
- 暂不移动 `run.py`、`framework/`、`v3_agent/tools.py` 和 `scenarios/tools_real.py`；先建立新入口和兼容验证，再整理物理目录。
- 每次变更只运行足以验证该变更的最小测试。
