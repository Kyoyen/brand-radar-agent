# Agent 打造说明

## 当前结构

一个真实模型 Agent，在一份持久任务上调查和改稿。界面与 Agent 使用同一任务文档，结果不会从另一套静态 Demo 生成。

```text
问题、品牌底稿、材料、当前作品、人的反馈
              ↓
       单 Agent 工具调用循环
    搜索 / 打开原文 / 读材料 / 修改作品
              ↓
       同一任务文件持续保存
              ↓
  企划画布、对话、历史、导出共同读取
```

## 文件职责

| 文件 | 职责 |
|---|---|
| `studio/agent.py` | 真实模型循环、当前任务上下文、选卡改稿与停止 |
| `studio/tools.py` | 公开搜索、网页正文与相关图片位置提取 |
| `studio/store.py` | 本地任务读写、来源去重、卡片修改及原稿保留 |
| `studio/server.py` | 本机 HTTP API、后台运行和前端静态文件 |
| `studio/export.py` | 从当前任务导出 HTML / Markdown |
| `web/src/` | React 企划桌面，选卡、拖拽、缩放、对话与面板 |
| `data/cases/` | 有出处的研究起点，不含模型预制结论 |
| `agent/AGENTS.md`、`skills/brand-radar/` | 可继续打磨的专业工作方法 |

复用 `framework/llm_client.py` 的模型接入与 `framework/brand_profile.py` 的品牌读取。旧 Runner 和 `--weekly` 留作兼容，不参与新桌面运行。旧场景及其示例工具集中在 `scenarios/`，额外依赖按需安装：`pip install -r scenarios/requirements.txt`。默认 `requirements.txt` 只安装当前桌面必需的依赖；使用 Anthropic 时另装 `anthropic`。

## Agent 如何工作

调用真实模型，使用 search_web、open_url、read_source、update_board、finish 工具。模型按当前问题决定是否继续查、写或改；没有固定调查次数与 Brief 数量。按时间和最多轮数结束失控运行；预算耗尽是暂停，不伪装成完成。

公开搜索先提供线索，取得网页正文后才加入来源。免费搜索可遇到相关性或访问限制，会明确反馈；用户仍能添加公开链接和粘贴材料。网页中的指令一律当成不可信资料。

作品种类包括 observation、idea、source、question、note、calendar。观察需要来源；创意可以是明确假设。引用必须能回到已加入任务的来源。用户选中作品时，模型只修改选中对象，并保留其位置与人的取舍。

## 本地任务

保存在被 Git 忽略的 `outputs/studio/task_*.json`，包含问题、品牌条件、来源、卡片、对话、工作动态、视口与运行状态。卡片修改前的文字保存在 revisions；放下的卡归档保留。每次更新写入临时文件后替换，不因一次失败丢掉已经完成的草稿。

品牌编辑保存到被忽略的 `memory/brand/BRAND.md`；不存在时读取根目录 `BRAND.md`。研究案例另外保留本次已知事实、创作假设和未知条件。Agent 不自动改写品牌档案。

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd web
npm ci
npm run build
cd ..
cp -n .env.example .env
# 在 .env 内填写模型 Key
.venv/bin/python run.py --studio
```

打开 `http://127.0.0.1:8765`。没有 Key 也能打开桌面与材料，调用 Agent 前会说明配置缺失，不自动使用 Mock。

开发前端可在 `web/` 运行 `npm run dev`，Vite 把 `/api` 转发到同一 Python 服务。构建后由 Python 同源提供页面，无需第二个常驻服务。当前使用模型来自本机 .env；前端不接触 Key。

## API

- `/api/status`：配置可用性，不返回凭证。
- `/api/cases`：研究起点。
- `/api/tasks`：新建与历史；`/api/tasks/:id`：读取、位置与人工编辑。
- `/api/tasks/:id/messages`：继续工作；`/stop`：请求停止；`/sources`：添加材料。
- `/api/tasks/:id/export?format=html|md`：从当前任务导出。
- `/api/brand`：读取与人工保存品牌底稿。

仅监听本机地址；来源读取拒绝本机与内网，所有工具只读取外部资料。没有发送、发布、投放和预算工具。

## 改进方式

先看一次真实作品与修改：判断资料是否不够、品牌条件是否缺失、工具是否取得新信息、修改是否改变了方案做法。根据具体失败调整短技能、品牌底稿或相应代码；不要先建立自动评分与自我改写系统。

已有测试保留。改动后优先检查改变的行为，再通过桌面走一轮真实工作。新桌面的验证重点是来源读取、真实模型生成、选卡改稿、保存重开和导出。
