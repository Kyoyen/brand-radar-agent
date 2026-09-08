# 在另一台机器继续 Brand Radar

当前主线是本地企划桌面。先读 README 和当前状态；实现细节见 Agent 打造说明。

## 带过去什么

使用已有仓库 `https://github.com/Kyoyen/brand-radar-agent.git` 中实际已推送的分支。对话同步不会传输本地未提交代码；本轮分支及是否推送以当前状态文件和 Git 为准。

源码、公开研究案例与前端锁文件属于项目。`.env`、`.venv`、`web/node_modules/`、`web/dist/`、`memory/`、`outputs/` 和本地日志不属于远端交付。

## 重建

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-studio.txt
cd web
npm ci
npm run build
cd ..
cp -n .env.example .env
# 在新机器本地配置真实 Key，不复制凭证
.venv/bin/python run.py --studio
```

打开 `http://127.0.0.1:8765`。从内置研究起点开始一次新企划，确认模型完成调查并能在选卡追问后修改作品。登录/配置成功不等于这条完整使用路径已完成。

本机任务与定制品牌档案不会自动跨机同步。如需携带私有工作，另行明确要传输的文件与目标，不复制全局 Agent 状态或凭证目录。

## 旧入口

`run.py --weekly --source-pack ... --require-api` 仍保留 Replay 回放。旧场景代码没有迁移；新桌面不调用旧的外发工具。
