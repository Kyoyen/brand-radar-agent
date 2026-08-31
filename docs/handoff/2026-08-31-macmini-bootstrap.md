# Brand Radar｜Mac Mini 执行 Handoff

更新日期：2026-08-31  
目标设备：`MacMini-Codex.local`  
目标路径：`/Users/kyoyen/Developer/brand-radar-agent`  
仓库：`https://github.com/Kyoyen/brand-radar-agent`

## 接手目标

在 Mac Mini 上从公开 GitHub 基线恢复项目、完成无外发安全 smoke、登记 Codex 远端项目，并进入 `docs/product/ROADMAP.md` 的 P0。不要在首次接手中安装额外前端框架、运行真实抓取或开始视觉扩张。

## 仓库基线

- 代码与规划基线 commit：`7294772d5b5402acebd1c0e7ffc23ac949c5c5c5`
- 该 commit 应包含 PRD、Roadmap、Agent 执行目标、作品集证据契约、项目状态和本 handoff。
- 后续只含 handoff 指针更新的 commit 可以高于此基线。
- 克隆后先核对 commit；不一致时停止，不猜测哪个目录更新。

## 默认读取顺序

1. `AGENTS.md`
2. `README.md`
3. `docs/PROJECT-STATE.md`
4. `docs/product/PRD.md`
5. `docs/product/ROADMAP.md`
6. `docs/AGENT-EXECUTION-GOAL.md`
7. `docs/PORTFOLIO-EVIDENCE.md`

不要从历史 presentation、旧 KFC 文案或 Mock sample 反推当前产品目标。

## 克隆与核对

如果目标目录不存在：

```bash
git clone https://github.com/Kyoyen/brand-radar-agent.git /Users/kyoyen/Developer/brand-radar-agent
cd /Users/kyoyen/Developer/brand-radar-agent
git switch main
git pull --ff-only
git rev-parse HEAD
git status --short --branch
```

如果目录已经存在，先确认它是同一仓库且工作树干净；有未知 WIP 时停止，不执行 pull、reset 或 checkout 覆盖。

## 环境恢复

当前项目是 Python CLI，不需要完整 Xcode。先检查：

```bash
command -v git
command -v python3
python3 --version
```

依赖安装属于长操作，使用有界 runner：

```bash
cd /Users/kyoyen/Developer/brand-radar-agent
python3 -m venv .venv
/Users/kyoyen/.codex/bin/longrun \
  --label "brand radar dependencies" \
  --timeout 300 \
  --max-retries 0 \
  -- .venv/bin/python -m pip install -r requirements.txt
```

单次超时或失败后停止，不切换多个包管理器继续尝试。

## 无外发安全 smoke

不要把自然语言任务作为首次 smoke。它可能访问网络、写运行状态，若本机存在 webhook 还可能外发。

```bash
cd /Users/kyoyen/Developer/brand-radar-agent

env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u DEEPSEEK_API_KEY \
  -u MOONSHOT_API_KEY -u ZHIPU_API_KEY \
  FEISHU_WEBHOOK_URL= PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python run.py --help

env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u DEEPSEEK_API_KEY \
  -u MOONSHOT_API_KEY -u ZHIPU_API_KEY \
  FEISHU_WEBHOOK_URL= PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python run.py --list

git status --short
```

验收：两个命令 exit 0；`--list` 明确显示无 Key / MockProvider；没有意外生成或修改文件。

## 本机配置

- 不从笔记本复制 `.env`、API Key、Cookie、Keychain、浏览器资料或 Codex 数据库。
- 需要 Live 模型或来源时，在 Mac Mini 上走对应服务的原生登录 / 密钥配置。
- 首次 P0 不要求真实模型 Key；Replay 和安全 smoke 必须无 Key 可运行。

## Codex 远端项目登记

Git clone 与 Codex 项目登记是两件事。完成 smoke 后：

1. 打开 Codex Settings → Coding → Environments。
2. 主机筛选切到 `MacMini-Codex.local`。
3. 添加 `/Users/kyoyen/Developer/brand-radar-agent`。
4. 确认项目显示为远端 Git 项目（`projectKind: remote` 或等价状态）。
5. 从该项目创建新任务，不复用无关历史任务目录。

## 新任务首条指令

> 阅读 AGENTS.md、README.md、docs/PROJECT-STATE.md、docs/product/PRD.md、docs/product/ROADMAP.md、docs/AGENT-EXECUTION-GOAL.md 和最新 handoff。只执行 P0：审计 V4.2 复用边界，提出最小前后端架构与开源壳候选，建立瑞幸 Replay 数据契约和 bad-case 计划。先输出执行计划和变更文件清单；不得运行 push_v4.sh、强推、接入灰色数据源、外发消息或把旧 Mock 当成产品完成证据。

## 接手完成证据

- Mac Mini 路径和 remote 正确。
- `git rev-parse HEAD` 与本 handoff / GitHub 记录一致。
- 依赖安装成功且只有一个 `.venv`。
- `--help`、`--list` smoke exit 0。
- 工作树没有意外变更或秘密。
- Codex 项目登记为 remote，P0 新任务在正确目录启动。

## 已知阻塞与风险

- 当前没有 Dashboard、Replay fixture、自动化测试或 CI。
- 注册表和 Prompt 存在工具声明漂移，P0 应先修或收敛。
- 项目暂无独立 LICENSE；复用开源壳前必须逐项核对依赖 License，仓库许可另行由用户决定。
- Live 小红书 / 抖音不属于首轮接手范围。
- 连接设备历史可见不等于项目已登记；必须验证真实目录和 remote project 状态。

## Suggested skills

- `continuity`：按仓库状态与 handoff 恢复上下文。
- `preflight`：检查 Git、Python、依赖、来源与现有架构。
- `goal-setting`：只在需要调整工程目标时使用，不重写已确认产品目标。
- `prototype`：P0 通过后实现 Replay-first Dashboard。
- `postflight`：独立验收提交、测试、页面和公开表述。

## 停止条件

- SHA、remote、目录或 WIP 无法确认。
- 依赖安装超时或同类失败两次。
- 需要修改网络 / Clash、安装系统级工具、购买数据源或配置外部发送。
- 需要登录绕过、内部数据、秘密迁移或默认分支强推。
