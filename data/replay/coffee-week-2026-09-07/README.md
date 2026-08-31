# 咖啡品类周观察 Replay 包（2026-09-07）

这是一份供 Brand Radar 单场景回放使用的人工整理观察包。它帮助企划人员在 2026 年 9 月 4 日复核日前，为 9 月 7 日至 13 日的瑞幸咖啡周企划会检查材料读取、版本取舍、重复合并、待核和风险判断。

`pack_mode` 为 `REPLAY`。包内材料是冻结快照和简洁转述，不是实时抓取结果，也不是可直接外发的市场结论。

## 本次观察设置

| 项目 | 设置 |
|---|---|
| 品牌 | 瑞幸咖啡 |
| 品类 | 现制咖啡 |
| 地区 | 全国 + 上海 |
| 竞品 | 星巴克中国、库迪咖啡、Manner、麦咖啡 |
| 观察窗 | 2026-09-07 至 2026-09-13 |
| 30 天日历窗 | 2026-09-07 至 2026-10-06 |
| 人工复核截止 | 2026-09-04 |
| 业务问题 | 下周有哪些值得跟进、继续观察或主动避开的营销信号？ |

竞品被列入观察范围，不代表本包已经拥有每个竞品的有效材料。当前只有星巴克中国的明确公开材料；不能把库迪、Manner 或麦咖啡“没有材料”改写成“没有动作”。

## 包内文件

- `manifest.json`：唯一材料清单和观察设置。程序只应读取其中列出的 `sources/*.md`。
- `sources/*.md`：10 份简洁转述，逐份保留来源类型、日期、链接或文件位置和关系线索。
- `expected-result.json`：人工期望线，用于检查合并边界、优先级和 Brief 引用；它不是材料、不是模型输入，也不在 `manifest.json` 的 `sources` 中。

## 来源边界

- `PUBLIC`：有明确公开来源。本包只转述可安全确认的最小事实，不复制外部原文。
- `REPLAY`：为测试版本、过期或历史材料而保留的冻结摘要，不代表当前有效信息。
- `MANUAL`：人工便签。缺少原始凭证时必须保持 `unverified` 和“待核”，不能补写成事实。

`verification_status=verified` 只表示清单所写的最小事实在整理时有明确依据，不代表由 Brand Radar 实时重新打开链接验证。链接失效、页面更新或材料未覆盖的细节仍需人工复核。

## 人工判断线

本包故意包含以下关系：

1. 上海旅游节夏季旧预告被完整当前版取代；旧版截至 8 月 31 日，不进入观察窗。
2. 上海旅游节另一官方摘要与完整当前版属于同一事件，应该合并，不能按两次声量计数。
3. “9 月 12 日上海咖啡快闪”为 `MANUAL + unverified`，只能进入待核区，不能进入已确认 Brief。
4. 2025 上海咖啡节材料已过期且不在本轮时间窗，只保留在排除记录。
5. 教师节处于观察周内，是需要人工判断表达边界的风险节点。
6. 中秋节和国庆节进入 30 天日历；国庆假期延续到 10 月 7 日，但本包日历止于 10 月 6 日，结果应说明截断边界。

`expected-result.json` 是人工可讨论的期望，不是要求模型逐字复述的标准答案。只要事实边界、关系、引用和人工控制点一致，措辞可以不同。

## 不可外发

本包和其输出默认停在人工复核前。不得自动发送飞书、发布内容、创建投放、调整预算或触发任何外部写入。任何 Brief 只是候选草稿；采用、退回和补证都由企划人员决定。

## 本地自检

以下命令只检查 JSON 和清单文件是否完整，不访问网络：

```bash
python3 -m json.tool data/replay/coffee-week-2026-09-07/manifest.json >/dev/null
python3 -m json.tool data/replay/coffee-week-2026-09-07/expected-result.json >/dev/null
python3 - <<'PY'
import json
from pathlib import Path

root = Path("data/replay/coffee-week-2026-09-07")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
missing = [item["file"] for item in manifest["materials"] if not (root / item["file"]).is_file()]
assert len(manifest["materials"]) >= 10
assert not missing, missing
print(f"OK: {len(manifest['materials'])} materials")
PY
```
