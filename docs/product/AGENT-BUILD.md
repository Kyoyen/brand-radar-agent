# Agent 打造说明

## 当前结构

实操使用一个真实模型 Agent，在一份持久任务上调查和改稿。网页与 Mac 中间层共享同一任务文档；iPhone API 直连则在手机保存画布。手机另有明确标注的离线演示脚本，实操失败不会自动切换成脚本结果。

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
| `ios/BrandRadar/` | 原生无限画布、模板、语音对话、手机本地保存与 Mac 配对 |
| `data/cases/` | 有出处的研究起点，不含模型预制结论 |
| `agent/AGENTS.md`、`skills/brand-radar/` | 可继续打磨的专业工作方法 |

复用 `framework/llm_client.py` 的模型接入与 `framework/brand_profile.py` 的品牌读取。旧 Runner 和 `--weekly` 留作兼容，不参与新桌面运行。旧场景及其示例工具集中在 `scenarios/`，额外依赖按需安装：`pip install -r scenarios/requirements.txt`。默认 `requirements.txt` 只安装当前桌面必需的依赖；使用 Anthropic 时另装 `anthropic`。

## Agent 如何工作

调用真实模型，使用 search_web、open_url、read_source、update_board、finish 工具。模型按当前问题决定是否继续查、写或改；没有固定调查次数与 Brief 数量。按时间和最多轮数结束失控运行；预算耗尽是暂停，不伪装成完成。

公开搜索先提供线索，取得网页正文后才加入来源。免费搜索可遇到相关性或访问限制，会明确反馈；用户仍能添加公开链接和粘贴材料。网页中的指令一律当成不可信资料。

作品种类包括 observation、idea、source、question、note、calendar。观察需要来源；创意可以是明确假设。引用必须能回到已加入任务的来源。用户选中作品时，模型只修改选中对象，并保留其位置与人的取舍。`update_board` 可同批创建有显式 ID 的新卡和 `edges`（`from_id`、`to_id`、`label`），表达启发、支撑、待验证与行动顺序等关系；卡片和边一并校验、原子保存。只允许为新卡安排位置，已有位置仍由人掌握。

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

默认仅监听本机地址。iPhone MVP 使用显式 `python -m studio.server --phone` 入口，监听局域网并要求每个请求带 `Authorization: Bearer` 配对凭据；不接受浏览器跨站请求。配对信息在 `outputs/studio/phone-pairing.json`，权限为 0600。来源读取仍拒绝本机与内网，所有工具只读取外部资料。没有发送、发布、投放和预算工具；手机提供系统分享，由人选择目标并完成发送。

## iPhone API 直连与演示

`AgentConnection.swift` 保存非敏感地址与模型；`AgentAPIKeychain` 按完整端点隔离 Key，使用设备限定的 Keychain 条目。生产构建只允许 HTTPS，不允许地址内嵌账号、参数或片段；请求不跟随重定向，不向其他端点转送 Key。配置保存不联网，测试连接只由明确按钮触发。

`DirectAgent.swift` 使用原生 URLSession 调用 Chat Completions，强制返回一次 `update_board` 函数工具结果。测试连接也验证工具调用响应。对官方 DeepSeek 端点显式设置 `thinking: disabled`，与当前项目模型调用方式一致。工具同时支持可选 `groups` / `remove_group_ids`，旧响应仍可接受。一张卡至多属于一个组；选卡改稿不能挪走其他原有成员。整批校验卡片、分组、关系端点、选卡修改范围、来源 ID 与坐标后，`BoardStore` 才合并保存；已有位置、采用状态和历史保留。取消、超时、额度不足或格式错误均保留原画布与待重试 Brief，不使用模拟结果兜底。当前直连根据已有画布和 Brief 创作，没有搜索、读取网页、发送或发布工具；完整调查仍由 Mac 中间层提供。

`DemoCanvas.swift` 是无网络脚本，生成稳定 ID 的示例卡片、修改选中原卡并生成内容稿。它与实操通过画布模式字段隔离，导出含演示标识。旧版无模式字段的画布归入实操。UI 测试使用独立文件与 UserDefaults，不清除真实作品。

个人部署由 `ios/scripts/configure_personal_phone.py` 读取当前项目 DeepSeek 配置，通过已配对设备的 App 沙盒传入一次性文件。`PersonalConnection.swift` 校验固定官方端点，写入 Keychain 后删除文件，并仅记录无密钥的导入回执。不会把凭据编译进二进制或放入 URL/启动参数。

## 改进方式

先看一次真实作品与修改：判断资料是否不够、品牌条件是否缺失、工具是否取得新信息、修改是否改变了方案做法。根据具体失败调整短技能、品牌底稿或相应代码；不要先建立自动评分与自我改写系统。

已有测试保留。改动后优先检查改变的行为，再通过桌面走一轮真实工作。新桌面的验证重点是来源读取、真实模型生成、选卡改稿、保存重开和导出。

## 实时逻辑成图

手机口述和文字共用 `generateStream`，SSE工具调用按小批完整校验后提交。`CanvasUpdate` 的段ID、转写修订和序号屏蔽迟到结果；稳定语义片段合并排队，只有一个请求处理。模型上下文基准与最新人工文档分开，保护人工标题、正文、位置、采用状态和清单勾选。取消按段条件逆操作恢复，错误与后台中断保留已完成内容和待整理文字。

默认忠实整理，只有明确指令才扩展建议。图片与笔迹转为 JPEG 工作副本送给视觉模型，原件独立保留；文件仅提取文本/PDF文字；链接没有自动读取，音视频不自动转写。内容块更新按稳定ID合并，禁止模型凭空引用附件或覆盖本机路径。

画布 JSON 保存对象和附件引用；附件在 Application Support/CanvasAssets 独立保存，可编辑包包含原件与缩略图，排除连接配置和本机会话。旧Mac正文更新只更新对应文本块，保留其他内容块。
