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
