# Development Notes

开发前依次阅读：

1. `README.md`
2. `docs/product/PRD.md`
3. `docs/product/ROADMAP.md`
4. `docs/PROJECT-STATE.md`

## 当前优先级

先交付可以操作的 Replay Dashboard，再考虑实时来源和 Agent 基础设施。

- 默认使用静态 HTML/CSS/JavaScript 与本地 JSON。
- 先完成一条三分钟用户路径。
- 保持 `REPLAY`、推断和真实来源的区别清楚。
- Brief 只引用页面中存在的情报卡片。
- 不引入多 Agent、数据库、账户、定时任务或复杂框架。

## 仓库规则

- 不提交密钥、Cookie、`.env`、虚拟环境或本地运行数据。
- 不强推默认分支，不运行历史发布脚本。
- 不把旧静态页面或 Mock 输出描述为当前产品。
- 整理旧代码时保留 Git 可追溯性，并让根目录优先呈现当前 Demo。
- 每次变更只运行足以验证该变更的最小测试。
