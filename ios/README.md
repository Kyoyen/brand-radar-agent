# Brandar · iPhone 画布

2026-09-30 的 **1.0 (6)** 已从 GitHub main 提交 [`aab8454`](https://github.com/Kyoyen/brand-radar-agent/commit/aab84548538214392af4459d93bed85a41c7c801) 归档，App Store Connect 读回内部 TestFlight 状态 `IN_BETA_TESTING`；见 [GitHub Release](https://github.com/Kyoyen/brand-radar-agent/releases/tag/ios-1.0-build-6)。当前画布 Agent 会按实际接受结果继续生成，在流式多批之间保护人工修改；过大的工具批次会被拒绝并限次要求模型拆小，可明确删除卡片段落或清单项，遇到“几张画布”会先澄清独立画布与当前画布的卡片数量。模拟器自检 181/181、直连协议 70/70、流式协议 71/71 与后端检查 26/26 通过；37 个不同本地 UI 用例有通过证据，另有 2 项独立真实 API UI 通过。当前构建的真机安装、真人长段口述与锁屏中断尚未验收，见[本轮验收](docs/REALTIME-ACCEPTANCE.md)。

原生 SwiftUI iPhone / iPad 应用，核心是“实时逻辑成图”：把口述逐步整理成可编辑的节点、分组和连线，素材保存在相关节点里。工程不依赖第三方 Swift 包，最低 iOS 17；使用 Xcode 26 的目录同步组，新增 Swift 文件可直接放入 `BrandRadar/`。

当前个人 iPhone 已预配置 DeepSeek，直接在底部输入或按住“说出你的想法”。没有登录。AI 会创建卡片、分组和连线，并继续修改选中的原卡。主界面不再放演示/实操切换；预设作品收进设置中的“示例画布”，与“我的画布”分别保存。

聊天使用左右气泡区分你和 AI，自动显示最新回复。卡片直接展示标题与内容，模型、地址和 Key 仅在连接设置中出现。

## 填写自己的 Agent API

右上角设置 → “连接设置” → “API 直连”：

1. 填 HTTPS API 根地址（如 `https://你的服务/v1`）或完整 `/chat/completions` 地址。
2. 填服务商提供的模型名称和 API Key，点“保存配置”。地址和模型进入本机设置，Key 单独进入设备 Keychain；保存不会发请求。
3. 点“测试已保存的连接”，验证服务与函数工具调用，再回画布发送自己的 Brief。测试可能产生服务商调用费用。

接入要求是 **OpenAI 兼容 Chat Completions + 函数工具调用**，不是任意 Chatbot 分享链接或 Responses API。Key 按端点隔离；更换服务地址需为新端点配置 Key，不会把旧 Key 自动发给新服务。App 不内置真实 Key。

直连根据当前 Brief、画布与已有材料创作，没有外部搜索工具。需要现有 Brandar 网页端的公开资料调查时选择“Mac 中间层”，其模型 Key 留在 Mac。实操失败会解释错误并保留 Brief，不返回演示内容。

## 从手机开始

- 画布空白处拖动，双指缩放；左下角查看全貌。拖动卡片改变位置，双击展开正文。分组框表达包含关系，拖动组标题移动整组，双击组标题聚焦；选中卡片会突出相邻连线。
- 左下方模板按钮提供营销企划、灵感发散、用户旅程、内容排期、实验设计、空白画布。每次创建独立画布，模板内容明确为示例与待解问题。
- 单击节点、组或线出现工具栏；节点双击编辑，组标题双击聚焦。选中后拖右下角调整尺寸；拖右侧连接点到目标建立连接，拖到空白处可新建节点。也可选“连接”后点目标。左上多选支持点选、框选、分组、复制和删除；解散组保留内部内容。
- 底部短按打开文字对话；按住口述时，稳定的转写片段自动交给已连接的 AI 小批成图。松手补完并保留，上滑撤回本段。右上菜单撤销／重做整段口述。系统识别可能联网，不保存原始录音；识别任务每 50 秒续接。中断保留已完成更新及文字，可点“继续整理刚才的话”。示例画布不伪装联网生成。
- 节点可混排文字、图片、手绘、清单、表格、链接、文件及音视频。图片可批注，手绘使用 PencilKit；选择素材后口述“整理成逻辑图”，原件保留。AI 可读取图片、笔迹和文本／PDF文字；不自动抓网页或分析整段音视频。
- 右上菜单导出 PNG、PDF 或带附件的 `.radarcanvas` 可编辑包，并支持导入。连接凭据与本机撤销会话不进入包。系统分享由人选择目标完成发送；不自动发布到营销平台。

## 启动 Mac 中间层

沿用项目现有 `.env` 和 Python 环境。不要在 8765 已有服务时重复启动；可停止原服务后使用手机模式，或用 `--port` 指定另一端口。

```bash
.venv/bin/python -m studio.server --phone --port 8765
```

另开终端，在仓库根目录生成本地配对页：

```bash
swift ios/scripts/pairing.swift
open outputs/studio/phone-pairing.html
```

安装 App 后用 iPhone 系统相机扫描，或在“设置 → 连接设置 → Mac 中间层”手动填写 `outputs/studio/phone-pairing.json` 中的地址和配对码。配对页、图片与 JSON 均不进 Git。仅用于可信局域网；此 Demo 的局域网传输为 HTTP。网页桌面继续使用原来的本机服务入口；手机模式要求 bearer，不直接面向浏览器。

## 在 Xcode 打开

从仓库根目录运行：

```bash
open ios/BrandRadar.xcodeproj
```

选择 `BrandRadar` scheme 和目标 iPhone，默认 Run 已使用精简的 **Release** 构建，使用当前已登录的开发团队 `Z364722GNH` 自动签名。工程使用 bundle ID `com.keyuanshi.brandradar`。首次真机运行可能需要在 iPhone 开启开发者模式、信任电脑，并允许局域网访问；语音输入首次使用时会请求麦克风和语音识别权限。签名证书属于旧团队并不代表该团队在 Xcode 仍可用，应以 Accounts 中的当前团队为准。

配对链接使用 `brandradar://pair` URL scheme。连接地址与配对凭据由运行中的 Mac 中间层提供，不应写入仓库或文档。iPhone 可通过系统相机打开配对二维码；应用本身不申请相机权限。局域网 HTTP 通过 `NSAllowsLocalNetworking` 放行，互联网连接仍保留系统的 HTTPS 安全要求。

## 安装容量

2026-09-12 的 iPhone arm64 Release 构建，签名 `.app` 文件合计 **1,709,611 字节（约 1.71 MB）**。使用 `-Osize`、整模块优化、死代码消除与符号剥离；不打包本地模型、第三方 Swift 包、网页运行库或大图。最终签名、系统安装占用与日后保存的画布数据以真机为准。

普通 Xcode Run 已默认 Release；需要源码调试时可以改为 Debug，测试仍使用 Debug。符号文件保留在 Mac 的 DerivedData，不进入 App 包。

## 构建与界面检查

以下命令均从仓库根目录运行。模拟器名称以 `xcrun simctl list devices available` 的本机输出为准：

```bash
xcodebuild -project ios/BrandRadar.xcodeproj -scheme BrandRadar \
  -configuration Debug -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath outputs/ios-derived build

xcodebuild -project ios/BrandRadar.xcodeproj -scheme BrandRadar \
  -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath outputs/ios-derived -parallel-testing-enabled NO test
```

UI tests 使用 `--uitesting` / `--uitesting-restore` 启动参数，独立于真实作品文件，检查画布交互、模板编辑、重开保存、演示改稿、模式隔离和 Key 配置入口，不发送模型请求。API 协议检查使用 URLProtocol 模拟响应验证整批更新、选卡范围、来源、错误与取消。它们不代替真实服务商兼容性、真机语音或手机网络验证。

```bash
xcrun swiftc -D DEBUG -D DIRECT_AGENT_CHECKS \
  ios/BrandRadar/{CanvasContent,AgentConnection,DirectAgent,AgentPatchContent,TaskBlueprint}.swift \
  ios/tests/DirectAgentChecks.swift -o outputs/direct-agent-checks
outputs/direct-agent-checks

xcrun swiftc -D DEBUG -D DIRECT_AGENT_STREAM_CHECKS \
  ios/BrandRadar/{CanvasContent,AgentConnection,DirectAgent,AgentPatchContent,TaskBlueprint,AgentStreamProtocol,AgentStreamGeneration}.swift \
  ios/tests/{DirectAgentChecks,AgentStreamChecks}.swift -o outputs/agent-stream-checks
outputs/agent-stream-checks
```

早期记录（当前结果见文末验收链接）：8 项相关 UI 用例全部通过（4 项原交互 + 3 项模式流程 + 1 项 Keychain 保存/重开/删除，分次运行）；48 项 API 协议检查通过。精简的 Release 版本也已安装到模拟器，实际完成离线画布生成、选卡生成内容稿，并打开带演示标识的系统分享面板。随后已在这台 iPhone 上用真实 DeepSeek 完成生成与选卡改稿，验证记录见下方。

需要测试配对时，保留 Xcode 默认的模拟器本地签名。`CODE_SIGNING_ALLOWED=NO` 可用于构建未签名的真机体积样本，不能用于需要 Keychain 的交互验证；模拟器测试应保留默认签名。

真机的构建、安装与连接结果以本次实际验证记录为准。此工程不包含 App Store 发布配置，也不自动发送消息、发布、投放或变更预算。

2026-09-11 已在 iPhone 17 Pro 模拟器用正常本地签名配对 Mac，从 App 对话框实际发出生成请求，收到 8 张卡与 6 条连线（包含 Agent 自主读取的公开来源）；系统分享面板已实际打开。2026-09-12 已完成 iPhone 15 Pro（iOS 27）的配对、开发者模式准备、签名安装与启动。随后拔掉数据线，CoreDevice 显示 `transportType=localNetwork`、`tunnelState=connected`，并已通过无线连接成功启动 App；后续可在同一局域网无线部署。DeepSeek 后续真机验证见下文；麦克风实际中文听写仍待验证。

交互参考：[Apple Freeform](https://support.apple.com/en-ie/guide/iphone/iphb86e84e2b/ios) 的自由画布、[mymind](https://mymind.com/mobile) 的移动卡片、[Heuristica](https://www.heuristi.ca/) 的对话与概念图。Swift 源码与视觉元素为本项目实现，不包含这些产品的私有代码或素材。

## 个人 DeepSeek 接入记录

2026-09-12，通过已配对的设备通道将当前项目 DeepSeek 配置送入 App 沙盒，App 随即写入端点隔离的 Keychain 并删除临时文件。凭据不进入源码、应用包、二维码或启动参数，后续 App 更新仍沿用手机 Keychain。

授权配置其他本人设备时可在仓库根目录执行：

```bash
.venv/bin/python ios/scripts/configure_personal_phone.py --device <已配对设备ID>
```

配置导入成功后切入实操；该脚本只读取本项目 `.env` 的 DeepSeek 配置。没有登录系统。不要将含凭据的配置文件手动复制进工程。

实际 iPhone 15 Pro（iOS 27）运行 Release 界面测试，发送自由 Brief 得到 3 张卡、2 条语义边，再将选中原卡改为雨天周末表达；退出重开后仍为 3 卡、2 边、4 条对话和 1 份旧稿。真实原生 Swift 协议另已在 Mac 跑过同类两轮，50 项模拟协议检查通过。

最新分组协议已通过 70 项检查；Mac 原生 Swift 真实 DeepSeek 两轮生成 6 卡、2 组、6 条分支/汇合连线，选卡修改后分组保持不变。当前 Agent 能新增和修改卡片、建立分组与关系、归档作品，并保存结果；直连不具备跨 App 操作或外部搜索。飞书 Hermes 尚未接入，本轮没有发送、发布或投放操作。

本轮界面验收：10 项不同 UI 用例通过（设置行点击修复后补跑；分组拖动与普通卡片手势另做回归）。分组成员等距移动、其他卡片不动、重开后位置保留，双击分组聚焦已验证。底部短按输入与按住前上滑取消已验证；真实语音识别与这一版完整真机交互仍待手机解锁。最新 Release 已通过无线设备通道更新，既有 Keychain 与作品保留。

## 实时编辑实现

`CanvasDocument` 定义内容与结构，`CanvasUpdate` 携带口述段、转写修订和批序号，`CanvasEditSession` 记录条件字段差异。人工编辑和模型更新共用保存机制；撤销只对仍符合预期的字段生效，不用整板快照覆盖期间的编辑。新内容局部放置，不自动全局重排，离屏新增通过“查看新增”定位。

`AgentStreamProtocol` 解析 SSE / 工具参数分片，每个完整有效的小工具调用立即提交；模型通过连续小调用完成本段。较早转写被修正时取消过期请求，按最新全文重整。DeepSeek 使用当前 `deepseek-flash`；旧官方 Flash 配置保留原端点 Keychain 凭据并更新模型别名。

本轮测试结果见 `docs/REALTIME-ACCEPTANCE.md`。模拟器手势、自检、真实模型请求、手机安装与真人连续口述分别记录，不能相互代替。
