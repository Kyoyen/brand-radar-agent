# Brand Radar

Brand Radar 是一个面向营销企划人员的品类情报看板。输入品牌、品类、地区和关注关键词后，它把竞品动作、营销节点、地区活动和热点整理成一条可筛选的情报流，并给出日历、关键词和 Brief 角度。

当前正在开发第一版可运行 Demo，默认案例为“瑞幸咖啡 / 现制咖啡 / 全国 + 上海”。

## 第一版要展示什么

用户完成一次简单操作：

```text
确认品牌与竞品
  → 点击生成情报
  → 浏览去重后的营销情报卡片
  → 按品牌、类型或关键词筛选
  → 查看营销日历和热词
  → 获得 3 个带来源引用的 Brief 角度
```

页面只保留四个区域：

- 情报流：竞品 Campaign、新品联名、节日节点、地区活动和热点。
- 营销日历：近期值得准备或需要避开的日期。
- 热门关键词：当前数据中出现频率较高或新出现的词。
- Brief 建议：基于当前筛选结果生成的三个选题角度。

## Demo 数据

第一版使用仓库内置的 Replay 数据，保证无 API Key 也能稳定演示。页面必须明确显示 `REPLAY`，每张情报卡保留来源名称、日期和链接。

Replay 只用于演示产品流程，不代表实时监测结果。实时公开来源将在 Demo 跑通后再接入。

## 当前仓库状态

- 已有 Python CLI Agent 原型，包含模型适配、工具调用和结构化输出。
- Dashboard、瑞幸 Replay 数据和新的聚合流程正在开发，当前尚未完成。
- `v1_basic/`、`v2_structured/`、`v3_agent/`、`framework/` 和 `scenarios/` 属于早期探索代码，后续会整理到清晰的 legacy 区域。

## 文档

- [精简 PRD](docs/product/PRD.md)
- [Demo 开发计划](docs/product/ROADMAP.md)
- [当前状态](docs/PROJECT-STATE.md)

## 现有 CLI 基线

以下命令只用于验证早期 Python 原型，不代表 Dashboard 已完成：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 run.py --list
```

不要提交 `.env`、API Key、Cookie 或本地运行数据。

## 数据边界

- 第一版不绕过登录或平台限制抓取小红书、抖音等平台。
- 示例、Replay 和真实公开来源必须清楚区分。
- 模型生成的判断应能回到页面中真实存在的情报卡片。
- 来源不足时直接标记“待核”，不补写成确定事实。

## 暂不做

- 多 Agent 编排、自我进化框架和复杂评测系统。
- 用户系统、数据库、定时任务、自动发稿和自动投放。
- 全网实时监测或对小红书、抖音的登录态抓取。
- 为尚未验证的效果提供效率、覆盖率或业务结果承诺。
