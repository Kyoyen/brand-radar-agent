# Mac Mini 交接说明

更新日期：2026-09-01

## 交接结论

本仓库已经形成可运行的品牌驱动单 Agent 演示骨架。首次使用可以补充品牌情况，也可以直接使用通用 `BRAND.md`；Agent 随后逐轮选择要查的信号和所需营销能力，把品牌起点、反馈过程、企划结果一起写入 JSON 与同源 HTML 周会稿，最后停在人工复核前。

这可以称为品牌驱动的可运行单 Agent 演示骨架，但不能称为完整成熟或自治营销产品。当前入口仍是终端建档向导与 CLI，不是 GUI，也不是 Dify；亮点是品牌取舍进入每轮判断、按需选择营销能力、读取反馈后继续或停止，以及最后交给人确认。

第一版目标只做一件事：使用真实模型 API Key 读取咖啡品类 Replay / 人工补充材料，输出下周企划会需要的情报流、30 天日历、重点关键词和 3 条 Brief，并停在人工复核前。

## 交付定位与本机重建

- 公开远端：`https://github.com/Kyoyen/brand-radar-agent.git`
- 公开稳定分支：`main`
- 本轮开发分支：`docs/lean-demo-cleanup-20260831`；通过普通快进同步到 `main`，不得强推。
- 功能与文档基线以远端 `main` 的最新提交为准。
- `.env`、`.venv`、`memory/brand/BRAND.md`、`outputs/` 和 `.longrun/` 不属于远端交付，也不会跨机迁移。新机器使用仓库通用 `BRAND.md` 起步，若需要定制档案则重新完成六问。

新机器不要复制 `.venv` 或 Key。当前 weekly 只需要核心依赖；默认源卡住时可切清华源，不必为了旧实时工具先硬装 `lxml`：

```bash
python3 -m venv .venv
$HOME/.codex/bin/longrun --label "Brand Radar weekly core dependencies" \
  --timeout 120 --stall-timeout 30 --max-retries 0 -- \
  .venv/bin/python -m pip install \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  "openai>=1.30.0" "httpx>=0.27.0" "pydantic>=2.0.0" \
  "python-dotenv>=1.0.0" "rich>=13.0.0"
cp .env.example .env
```

在本机编辑 `.env`，只填 Provider、模型和 Key；不要把 Key 放进命令参数或 `longrun` 日志。然后验证：

```bash
$HOME/.codex/bin/longrun --label "Brand Radar regression" \
  --timeout 120 --stall-timeout 30 --max-retries 0 -- \
  .venv/bin/python -m unittest discover -s tests -p 'test_*.py'

.venv/bin/python run.py --brand-setup

$HOME/.codex/bin/longrun --label "Brand Radar real weekly" \
  --timeout 120 --stall-timeout 30 --max-retries 0 -- \
  .venv/bin/python run.py --weekly \
  --source-pack data/replay/coffee-week-2026-09-07/manifest.json \
  --require-api
```

## 开始前先读

按顺序阅读：

1. `README.md`
2. `docs/product/PRD.md`
3. `docs/business/NEXT-WEEK-WORKFLOW.md`
4. `docs/product/AGENT-BUILD.md`
5. `docs/product/ROADMAP.md`
6. `docs/PROJECT-STATE.md`
7. `docs/handoff/MACMINI-HANDOFF.md`（当前文件，用于核对交接边界）

这些文件是当前事实源。历史对话、旧根目录规划稿、V1-V3 示例和 Mock 输出不能覆盖这条主线。

## 已完成与当前状态

- README 已改成公开产品主页，使用真实周会稿截图，说明当前能力、快速开始、数据边界和企划无限画布方向。
- PRD 已改成营销企划业务流程语言，包含材料、判断、交付和验收。
- 新增 `docs/business/NEXT-WEEK-WORKFLOW.md`，用 `fusion` 从 Accio / RealReplicaBench 原始任务提炼可迁移工作方法，并转译成 Brand Radar 自有流程。
- 新增 `docs/product/AGENT-BUILD.md`，保留“怎么打造 Agent”的工程说明。
- Roadmap 和 Project State 已改成可以直接接续的产品阶段与缺口清单。
- `.env.example` 已明确 Mock 只用于烟雾测试；`.gitignore` 已忽略 `.env`、`outputs/`、`memory/` 和本地日志。
- 已准备咖啡 Replay 包及人工期望结果，包含重复、版本替换、过期、待核和风险节点。
- 已实现 `brand_radar_weekly`、专用证据链校验和 `--weekly / --source-pack / --require-api`。
- 已提供通用 `BRAND.md` 与 `python3 run.py --brand-setup`；六问可逐题跳过，首次建档全部跳过时不生成本机定制档案。
- 已提供信号筛选、品牌契合和 Brief 转译三个营销技能；Agent 每轮按当前目标选择一项。
- weekly 只读取本次观察包，最终等待人工复核，不发送、发布、投放或改预算。
- 当前真实主演示成功：`outputs/brand_radar_weekly-real-20260901-115850-982265.json` 与同名 HTML，真实 `deepseek-v4-flash`，约 29.5 秒，通用品牌档案、四轮决策、三个调查动作、7 张情报卡、3 条不同 Brief，最终停在人工复核且无外部动作。
- 真实路径依次核对待核的上海咖啡快闪、上海旅游节版本组和当前来源，第四轮停止调查并开始成稿；本轮实际使用信号筛选和 Brief 转译。
- 显式 Mock 冒烟清楚标记为程序测试，产物为 `outputs/brand_radar_weekly-mock-20260901-115812-076795.{json,html}`。
- 错误 Key 已验证：约 0.9 秒退出码 3，明确失败，产物总数保持 28，无新增 JSON / HTML / tmp，无 Mock。
- 当前全量测试数为 100。
- HTML 结构检查已通过；真实周会稿已使用 Microsoft Edge 渲染 1440 × 1100 首屏并完成视觉检查，公开截图为 `docs/assets/brand-radar-weekly-demo.png`。完整长页和窄窗口仍需后续检查。
- 17:50 左右程序合成 `adjustment_reasons` 的文件不得作为真实 Agent 证据或 Dashboard 输入。
- 上述 `outputs/` 文件均为本机忽略证据，不随 Git 交付；新机器必须使用目标命令重新生成。

## 已知事实

- `run.py` 是当前 CLI 入口，现有命令 `python3 run.py --help` 和 `python3 run.py --list` 可作为基线检查。
- `framework/llm_client.py` 支持 OpenAI、Anthropic、DeepSeek、Moonshot 和 Zhipu；weekly 的 `--require-api` 会禁止缺 Key 或请求失败时进入 Mock。
- 品牌档案、六问状态机、营销技能和逐轮决策的实现细节统一见 `docs/product/AGENT-BUILD.md`。
- `framework/scenario_registry.json` 仍保留早期多场景配置，但 `brand_radar_weekly` 只注册四个本地只读阶段，不注册飞书或其他外部写入工具。
- 咖啡 Replay 包、`brand_radar_weekly`、专用结果校验、真实 Key 合格产物和本地 HTML 周会稿均已具备；交互 Dashboard / chat 尚未实现，下一阶段按用户使用价值决定是否做。

当前唯一 canonical 交付物是通过专用校验后原子保存的 JSON。HTML 周会稿、未来 GUI / chat 和未来报告都必须读取同一份结果；当前 CLI 没有 GUI chat、交互 Dashboard、自动刷新或实时抓取。首页稳定生成“本周优先讨论 / 信息不够先别拿进方案 / 明确不采用 / 继续观察”的人话结论，并优先露出待核卡。

## Mac Mini 下一项任务

GitHub `main` 与主页刷新后，下一项最小产品工作是补齐任务历史、人的采用 / 退回记录和图文 / 视频预览内容结构，再用真实定制品牌档案复跑默认观察包。主链稳定后再开发左侧导航 + 右侧企划无限画布；六问只是可跳过的首次使用弹窗。

## 目标命令

当前命令可用于基线检查：

```bash
python3 run.py --help
python3 run.py --list
```

当前已支持：

```bash
python3 run.py --brand-setup

python3 run.py --weekly \
  --source-pack data/replay/coffee-week-2026-09-07/manifest.json \
  --require-api
```

`--brand-setup` 不调用模型；跳过建档后继续使用通用 `BRAND.md`。周企划验收通过时应显示真实 Provider、模型、材料包、JSON 输出位置、HTML 周会稿位置和人工复核提示。主动去掉 `--require-api` 且缺 Key 时，才允许进入清楚标记的 Mock 烟雾测试。

## 原始案例参考边界

只把 RealReplicaBench 当成工作方法来源，不复制任务文案、数据、代码、业务对象或交付物。参考固定版本：

- `https://github.com/Accio-Lab/RealReplicaBench/tree/4041872837eb960a16bbe3d73b459f20680b8ad6`

重点吸收的方法是：从问题到可信洞察、让来源与结论相连、从信号到行动建议、面向周会组织简报、先读完整材料、还原最新有效版本、排除旧通知和无关项、草稿不是事实源、对外动作前停在人审。不要复制外部产品，也不要堆平台。

## Suggested Skills

- `fusion`：需要继续从多个原始业务案例中抽象可迁移机制时使用。
- `prototype`：开始落地最小可跑 Agent 和 Dashboard 时使用。
- `postflight`：真实 Key 跑通后做收尾验收、证据整理和交付核对时使用。

## 不要做

- 不提交 `.env`、API Key、Cookie、Keychain、`.venv`、缓存、Codex 状态库或运行输出。
- 不把 Mock 输出、Replay 样例或早期静态页面描述成真实业务结果。
- 不强推默认分支。
- 不为了“更像 Agent”迁移 Dify 或增加多 Agent。
- 不移动 `run.py`、`framework/`、`v3_agent/tools.py`、`scenarios/tools_real.py`，直到新入口跑通且回归命令更新。
- 不自动发送飞书、发稿、投放、改预算或调用任何外部写入动作。
