# Brand Radar｜证据与查阅范围

评议日期：2026-09-18  
固定基线：`6a3737d21a2a9e6776d3ad51088d29710e902267`  
仓库：[Kyoyen/brand-radar-agent](https://github.com/Kyoyen/brand-radar-agent)

本轮通过 GitHub 连接读取目录、产品说明及关键源文件。下列范围指实际返回并查阅的源码段，不等于逐行审计整个仓库。未运行应用、构建、测试或真实模型；未成功取得仓库图片或当前页面截图。因此所有视觉与触感判断均为规格提案或待测风险。

## 源码与产品资料

### E01｜当前产品入口

[README.md](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/README.md)

已读主要完整正文。依据：原生移动端入口、画布与对话、Web 调查保留、本地保存和未上架状态。README 的图片链接存在，但本轮未见到图片内容。

### E02｜产品定位与视觉意图

[PRD.md](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/docs/product/PRD.md)  
[ROADMAP.md](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/docs/product/ROADMAP.md)

已读完整正文。依据：品牌企划人员、问题与材料驱动、局部改稿、暖白墨绿纸张层次、窄屏阅读、显式保存品牌记忆、App 主方向。路线图仍有“当前没有 App 安装包”等早期描述，需要与当前状态同步。

### E03｜项目状态与已有能力

[PROJECT-STATE.md](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/docs/PROJECT-STATE.md)

已读完整正文。依据：9 月 13 日状态、单 Agent、原生与 Web 分工、模型直连和 Mac 入口、缓存／剔除、历史验收与未完成真机验证。文件部分“当前”描述未明确限定平台，需避免与新移动端能力混淆。

### E04｜最新移动端使用方式

[docs/mobile/README.md](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/docs/mobile/README.md)

已读完整正文。依据：短按打字、长按听写、普通 Brief／实时 Beta、富内容、三幕剧本支持、尚未完成连续真人语音验证。文档中的实测数字属于特定历史测试，未在本轮复验。

### E05｜主工作区与工具入口

[BrandRadarApp.swift](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/BrandRadar/BrandRadarApp.swift)

查阅 1—220 行。依据：顶栏和底部 dock，Brief／Beta 并列，菜单中的撤销／重做，定义但未在该工作区主树调用的 `selectionBar`，底部可用高度传递。实际 UIKit 工具栏见 E12。

### E06｜听写结束与中断

同 [BrandRadarApp.swift](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/BrandRadar/BrandRadarApp.swift)，查阅 221 行至文件末尾。

依据：`endDockVoice` 普通听写直接发送，Beta 独立完成；短按进入聊天；普通听写中断时保留文字草稿。没有据此推定真人识别质量。

### E07｜画布库、编辑器和目标提示

[Sheets.swift](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/BrandRadar/Sheets.swift)

查阅 1—220 行。依据：`RadarPalette`、`TemplateSheet`、`BoardLibrary`、`CardEditor`、`ChatSheet` 前段；转节点先保存、取消只关闭、当前已放下出现在全局库下方、选中提示依赖 selectedCard，以及可选建议中的固定三个方向。

### E08｜聊天发送、滚动与重试

同 [Sheets.swift](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/BrandRadar/Sheets.swift)，查阅 221 行至文件末尾。

依据：发送后的 dismiss、多个状态变化都滚动到底部、草稿保存、失败后重新编辑、语音输入、关系编辑。失败重试已存在，不应作为完全缺失功能重做。

### E09｜数据写入、归档与文档状态

[BoardStore.swift](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/BrandRadar/BoardStore.swift)

查阅 1—410 行。依据：`selectedCard`、`visibleBoards`、恢复草稿、损坏文件保护、`persist`、`update`、`editCard` 的 archived 分支及局部字段合并。性能只被标记为容量测试对象，尚未证实存在实际卡顿。

### E10｜直接生成路径、Mac 返回与撤销

同 [BoardStore.swift](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/BrandRadar/BoardStore.swift)，查阅 450—635 行。

依据：普通 direct 路径通过会话处理，Mac 完成时请求 fit，脏字段保护和条件撤销。因此不能将 `DirectAgent.generate` 的非流式实现自动等同于当前普通 Brief 的实际运行路径。

### E11｜Agent 规则与修改校验

[DirectAgent.swift](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/BrandRadar/DirectAgent.swift)

读取前段及 200—235 行；较长响应在指令尾部有截断，未声称阅读了所有校验实现。依据：公开可见的整理／发散规则、sources 限制、已有内容保护、卡／组选中校验与工具结构。此文件与实际流式路径的关系按 E10 说明处理。

### E12｜画布绘制、实际工具栏与无障碍

[InfiniteCanvas.swift](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/BrandRadar/InfiniteCanvas.swift)

查阅 1—220、328—398、400 行至文件末尾；手势中间部分未完整阅读。

依据：整体 CGContext 缩放、字号、按屏幕卡宽显示内容、36×32 点按钮、newIDs 只记录新增、已有 Reduce Motion 与 VoiceOver 支持。触摸额外命中区域及遮挡仍需实测。

### E13｜历史验收与待测事项

[REALTIME-ACCEPTANCE.md](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/ios/docs/REALTIME-ACCEPTANCE.md)

已读完整返回正文，包括 9 月 13 日补充。依据：协议替身、系统组件、模拟器与真人真机分别记录；长段语音待验收；CPU 绘制探针不等于实机 FPS；Beta 待确认重开和条件放弃的已有检查。

### E14｜Web 已有工作流程

[web/src/App.jsx](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/web/src/App.jsx)

查阅 1—190 行。依据：最近修改排序、保存状态、任务选择与轮询、发送后打开对话、材料加入、品牌档案显式保存。不据该局部读取宣称 Web 的所有状态都已审查。

### E15｜Web 卡片信息层级

[web/src/Canvas.jsx](https://github.com/Kyoyen/brand-radar-agent/blob/6a3737d21a2a9e6776d3ad51088d29710e902267/web/src/Canvas.jsx)

查阅 1—165 行。依据：中文类型、英文 eyebrow、创意解释尾句、来源图与链接、卡片操作及局部键盘行为。未读取全部 CSS 与 Panels 实现，未判断最终像素级效果。

## E16｜官方设计参考

[Apple UI Design Dos and Don’ts](https://developer.apple.com/design/tips/)

用于原生点击区域 44×44 points、文字可读性及对象附近布置操作的设计参考。采用英文原文单位，避免本地化页面将 points 译为像素造成误用。本包建议的正文 17 点和辅助 12—13 点属于产品设计提案，并非这些具体字号是标准要求。

[W3C：Understanding SC 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)

用于 Web 普通文字至少 4.5:1、符合大字条件时至少 3:1 的对比度参考。原生采用相同目标属于本包设计选择，未做合规认证。

[W3C：WCAG 2.2](https://www.w3.org/TR/WCAG22/)

用于 Web 文本放大至 200% 的功能检查。原生另测 Dynamic Type，单位和验收方式不混用。

## 证据结论的分层

- 源码行为明确：提前提交后取消、归档删除关系而恢复仅改状态、发送关闭对话、无条件滚动触发、分组提示的数据不匹配。
- 从实现推导的体验风险：小字在缩放后的阅读成本、图标区域误触、反复打开对话的负担、整库保存的容量风险。
- 设计提案：阅读状态、底部输入分层、Beta 位置、暖白墨绿细化、文档库和结果条调整。
- 待真人验证：审美偏好、真实触感、连续语音、相机与键盘遮挡、辅助技术、设备性能。

未执行安全审计、商业可行性验证、竞品评估或用户研究；不能用本包推断这些结果。
