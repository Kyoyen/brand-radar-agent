# Brand Radar｜当前项目状态

更新日期：2026-08-31  
状态：产品方向已确认；GitHub 文档发布与 Mac Mini handoff 准备中

## 当前基线

- GitHub：`https://github.com/Kyoyen/brand-radar-agent`
- 公开默认分支：`main`
- 发布前云端基线：`1e26929ee874336df31321b6f63d2af0303c3263`（V4.2）
- 当前工作分支：`docs/brand-radar-mvp-handoff-20260831`
- 本轮目标：发布产品、执行、作品集和 Mac Mini handoff 文档；不实施 Dashboard。
- 本轮发布 commit：`BASELINE_COMMIT_PENDING`

## 已核实的代码能力

- 唯一运行入口为 Python CLI `run.py`；当前没有 Web server 或 Dashboard。
- 支持自然语言场景路由、有限 ReAct 工具调用和重复调用保护。
- 支持 OpenAI、Anthropic、DeepSeek、Moonshot、智谱 Provider；无 Key 时使用 MockProvider。
- `framework/output_schema.py` 定义观察、洞察、决策点和建议的结构化输出及 evidence references。
- `scenarios/tools_real.py` 包含 Google Trends、Hacker News、公开微博聚合源和通用 URL 读取。
- 现有 `docs/presentation.html` 是历史静态展示页，不是新 MVP 页面。

## 尚未实现

- BrandProfile 与竞品自动发现 / 人工确认。
- SourceDocument、MarketingSignal、SignalCluster、BriefSuggestion 的聚焦数据链。
- 跨来源去重、Campaign 聚类、营销相关性和新颖性排序。
- 瑞幸 Replay fixtures、bad-case 集和自动化测试。
- 统一 Feed、营销日历、关键词词云、Brief Dashboard 和反馈状态。
- Live 来源健康状态、部分失败界面和真实定时运行。

## 已知技术缺口

- 仓库没有 `tests/`、CI、lockfile 或明确 Python 版本范围。
- `content_brief` Prompt 要求 `get_brand_calendar`，但注册工具列表未包含它。
- `trend_alert` Prompt 要求 `assess_brand_fit` / `draft_content_hook`，但注册工具列表未包含它们。
- API 文档使用 `FEISHU_WEBHOOK`，代码实际读取 `FEISHU_WEBHOOK_URL`。
- 自然语言任务可能访问网络、写入 `memory/` / history，若配置 webhook 还可能外发；不能作为首个安全 smoke。
- 旧示例含虚构品牌数据，现已标记 `SYNTHETIC_LEGACY`，不能作为事实证据。
- 仓库当前无独立 `LICENSE` 文件；许可需用户单独确认。

## 本轮安全修正

- README 区分现有 V4.2 基线和规划中的聚焦 MVP。
- 删除无证据的效率倍数、时间节省和零值守公开表述。
- 历史 sample 标记为 Synthetic，外发状态改为未发送模拟。
- 高风险 `push_v4.sh` 停用，禁止删除锁文件和强推分支。
- `.longrun/`、`memory/` 和日志加入忽略范围。
- 新增项目级 `AGENTS.md`，让 Mac Mini 执行者默认遵守证据和 Git 边界。

## 安全 smoke

依赖恢复后，首轮只运行：

```bash
env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u DEEPSEEK_API_KEY \
  -u MOONSHOT_API_KEY -u ZHIPU_API_KEY \
  FEISHU_WEBHOOK_URL= PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python run.py --help

env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u DEEPSEEK_API_KEY \
  -u MOONSHOT_API_KEY -u ZHIPU_API_KEY \
  FEISHU_WEBHOOK_URL= PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python run.py --list
```

这只证明 CLI / import 基线，不证明产品闭环。自然语言任务必须在来源、写盘和外发边界确认后运行。

## 下一步

1. 发布本轮文档与安全修正到 GitHub `main`，记录 commit 并远端回读。
2. Mac Mini 克隆到稳定路径，恢复依赖并运行安全 smoke。
3. 在 Codex Environments 登记 Brand Radar 远端项目并确认 `projectKind: remote`。
4. 新任务先执行 P0：代码架构盘点、瑞幸 Replay 数据和最小 Dashboard 技术决策。

## 停止条件

- Mac Mini SHA 与 handoff 不一致。
- 安装超时、远端项目无法登记或连接状态不明。
- 发现秘密、内部数据、未确认 WIP 或需要绕过平台限制。
- 新实现试图把 Mock / Replay 包装成 Live，或以展示优先于证据链。
