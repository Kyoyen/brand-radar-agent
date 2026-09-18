# 评议首轮执行记录

来源：`BrandRadar_Codex_Review_20260918.zip`；六份文档及 manifest 原样保存在 [原始任务包](BrandRadar_Codex_Review_20260918/00_START_HERE.md)，六份 SHA-256 均与 manifest 一致。

范围：B00、B01、B02。B03 之后未纳入本轮。

## B00：基线

- 源码：`6a3737d21a2a9e6776d3ad51088d29710e902267`，与评议基线一致。开始时源码无未提交修改。
- 环境：Xcode 26.6；iPhone 17 Pro 模拟器，iOS 26.5；测试均使用 `--uitesting` / `--uitesting-restore` 隔离文档与配置，不读取个人 Keychain。
- 真实复现一：编辑标题后拆为节点，编辑器仍有“取消”；点击取消后，标题修改与新增节点仍已保存。UI 测试 1/1 通过，表示旧缺陷已复现。
- 真实复现二：放下示例节点，重启后恢复，相关连线没有恢复、原组成员数从 2 变成 1。隔离基线源码 UI 测试 1/1 通过，表示旧缺陷已复现。
- 两次基线构建与 UI 测试结果分别位于 `outputs/ios-derived/Logs/Test/Test-BrandRadar-2026.09.18_15-56-59-+0800.xcresult` 与 `outputs/review-20260918/b00/derived/Logs/Test/Test-BrandRadar-2026.09.18_16-01-33-+0800.xcresult`。
- 调用：`xcodebuild -project ios/BrandRadar.xcodeproj -scheme BrandRadar -configuration Debug -destination 'platform=iOS Simulator,id=6A56C70C-1A1E-4FF6-9CCD-B78E260FDAE7' -parallel-testing-enabled NO -only-testing:BrandRadarUITests/EditorCommitUITests test`；归档复现使用同配置的隔离基线副本及 `ArchiveBaselineUITests`。
- 修正文档：Roadmap 的“没有 App 安装包”已更新为原生 iPhone 可构建安装、未公开分发。
- 未执行：真人真机交互、帧率、语音、模型调用与 Web 浏览器操作；不以旧版本测试替代。

### 基线截图

![转节点后编辑器仍有取消](20260918-screens/b00-split-editor.png)
![取消后改动已保存](20260918-screens/b00-cancel-committed.png)
![放下前](20260918-screens/b00-before-archive.png)
![重开并恢复后关系缺失](20260918-screens/b00-restored-without-relations.png)

## B01：编辑与撤销

- 普通编辑保留本地草稿；取消与下滑退出显示“保存 / 放弃更改 / 继续编辑”。干净编辑器可直接关闭；“查看原素材”也遵循相同退出处理。
- “保存并转为节点”明确提示会保存草稿；保存与拆分一次提交，完成后关闭编辑器，画布提供本次撤销入口。
- 保存按字段及内容块合并，保留其他操作的修改；同字段、同块或顺序冲突拒绝整次保存并保留草稿。
- 修复拆分后的条件撤销：另一块被 Agent 修改时，仍能恢复拆出内容；被人修改过的目标节点、或原节点已删除时的目标内容，不被撤销抹掉。派生正文随块更新，独立旧正文仍保留。
- 沿用原有历史结构和稳定块 ID；新记录显式保留旧文字块，兼容已保存的旧历史。没有引入整板快照回滚或通用事务框架。

验证：A01—A04 的 5 项 UI 用例通过；模板编辑保存、混合内容保存重开、Beta 保留／放弃与重启的 4 项相关 UI 回归通过。真实 Store 层新增 26 个检查通过，含并发块编辑、源节点删除、单次撤销／重做与旧正文兼容。

运行采用 B00 的同一设备与隔离方式，`xcodebuild ... test` 选择 `EditorCommitUITests`、`BrandRadarUITests/testTemplateEditingAndPersistence`、`RichContentUITests`、`LiveDrawingUITests`。7/8 首轮中唯一剩余失败为测试同时匹配浮条与菜单的“撤销”；定点使用 `undoSplitButton` 后，拆分用例与上述 4 项回归最终 5/5 通过。最终构建产物及其检查为 B01+B02 联合工作树。

证据：`outputs/ios-derived/Logs/Test/Test-BrandRadar-2026.09.18_16-09-58-+0800.xcresult`（其余 7 项通过）；`Test-BrandRadar-2026.09.18_16-13-31-+0800.xcresult`（最终 5/5）。原生检查使用 `xcrun simctl launch --terminate-running-process 6A56C70C-1A1E-4FF6-9CCD-B78E260FDAE7 com.keyuanshi.brandradar --uitesting --canvas-selfcheck`；结果在 `outputs/review-20260918/final/canvas-checks.json`。

未执行：实体 iPhone 手势与 VoiceOver；模拟器通过不能替代这些验证。

![脏草稿退出的三个选择](20260918-screens/b01-dirty-exit.png)
![保存并转节点后结束编辑](20260918-screens/b01-split-committed.png)
![一次撤销恢复原稿](20260918-screens/b01-single-undo.png)
