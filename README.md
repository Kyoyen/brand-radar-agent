<h1 align="center">Brand Radar</h1>

<p align="center"><strong>把散落的市场信号，变成下周真正值得聊的那几件事。</strong></p>

<p align="center">为品牌与营销企划人员准备的 AI 调查搭档</p>

![Brand Radar 企划桌面概念](docs/assets/brand-radar-canvas-concept.svg)

<p align="center"><sub>企划桌面概念：信号、素材、竞品、日历和 Brief，在一张桌面上慢慢长成想法。</sub></p>

<p align="center">
  <a href="#先看一份真的">看真实周会稿</a>
  ·
  <a href="#在本地跑一次">在本地跑一次</a>
</p>

## 周五下午，桌面上有点乱

邮箱里躺着十几篇行业简报，三个群在转同一条消息，竞品似乎又有新动作。翻了半天，最难回答的还是：**这和我们的品牌有什么关系？**

Brand Radar 想坐在你旁边，做一个不吵不闹的调查搭档。

你告诉它这周想解决的问题，它从品牌档案出发读材料、理线索，把值得带进会议室的内容摆上桌面：几张情报便利贴、需要留意的日期、可以继续找的素材，还有三条不太一样的企划方向。

最后那一步依然属于你——拿走一个想法、改一改，或者让它再找找。

## 一张桌面，装下调查和灵感

| | |
|---|---|
| 🟨 **情报便利贴**<br>发生了什么，为什么现在值得聊 | 🖼️ **素材与来源**<br>图片、视频线索和原始出处放在一起 |
| 🗓️ **30 天节点**<br>什么时候该关注，什么时候该准备 | 💡 **企划 Brief**<br>从不同人群、场景和时机打开想法 |

同一个事件被转发了五遍，只留一张卡；消息已经过期，就别让它挤占桌面；两份材料互相打架，先摆进“再看看”，不急着写成结论。

这不是为了做一份更长的报告，而是为了让企划会更快进入真正值得讨论的部分。

## 它不从空白聊天框开始

- **先认识品牌。** <code>BRAND.md</code> 记住品牌想被怎样看见、在意谁、说什么话，以及哪些热闹不必去凑。
- **会整理，也会查一查。** 信号筛选、品牌契合和 Brief 转译是它随手可用的营销技能。
- **不只给一个答案。** 同一批材料会被整理成情报卡、时间节点和不同方向的 Brief。
- **知道什么时候把笔交回来。** 采用、修改、发布和投放，都由企划人员决定。

## 先看一份真的

![Brand Radar 咖啡品类周会稿](docs/assets/brand-radar-weekly-demo.png)

<p align="center"><sub>咖啡品类 Replay 材料生成的本地周会稿节选。</sub></p>

这次 Radar 观察“瑞幸咖啡 / 现制咖啡 / 全国 + 上海”，整理出 7 张情报卡、未来 30 天值得留意的节点，以及 3 条不同方向的 Brief。

它也把重复、过期、互相冲突和仍需确认的材料分开处理。每条建议都能回到对应来源，方便在会议前再看一眼。

Replay 是一套可以反复使用的演示材料，方便稳定体验完整过程；它不是实时市场数据流。

## 你的品牌，不必每次重新介绍

第一次使用时，可以简单补充品牌情况，也可以直接跳过。跳过后使用通用 <code>BRAND.md</code>，不会挡住你先跑一次 Radar；以后想补，再回来更新就好。

## 现在可以怎么玩

当前版本已经可以用真实模型生成咖啡品类周会稿。先从命令行开始，下一阶段会把同一套内容带进上面的企划桌面。

### 在本地跑一次

~~~bash
python3 -m venv .venv

.venv/bin/python -m pip install \
  "openai>=1.30.0" "httpx>=0.27.0" "pydantic>=2.0.0" \
  "python-dotenv>=1.0.0" "rich>=13.0.0"

cp .env.example .env
~~~

在本机 <code>.env</code> 中选择模型服务并填写 API Key，然后运行：

~~~bash
.venv/bin/python run.py --weekly \
  --source-pack data/replay/coffee-week-2026-09-07/manifest.json \
  --require-api
~~~

完成后会得到同一次 Radar 生成的 JSON 与 HTML 周会稿。

如果想先补充品牌档案：

~~~bash
.venv/bin/python run.py --brand-setup
~~~

所有问题都可以跳过。

## 它不会替你按下发送键

- API Key、<code>.env</code>、本机品牌档案和运行结果不会进入 Git。
- 默认不会发消息、发布内容、启动投放或修改预算。
- 公开演示图不包含 Key、本机路径或原始运行文件。
- 图片、视频和公开材料进入企划前，需要保留出处与使用状态。

## 项目里有什么

~~~text
BRAND.md                    通用品牌档案
agent/AGENTS.md             Agent 的工作方式
skills/brand-radar/         营销 Skills
data/replay/                咖啡品类演示材料
scenarios/brand_radar_weekly.py
                             周企划场景
framework/                  模型接入、调查过程与报告
run.py                      运行入口
tests/                      自动化测试
~~~

## 继续了解

- [产品需求](docs/product/PRD.md)
- [产品路线图](docs/product/ROADMAP.md)
- [下周营销企划工作流](docs/business/NEXT-WEEK-WORKFLOW.md)
- [Agent 打造说明](docs/product/AGENT-BUILD.md)
- [当前项目状态](docs/PROJECT-STATE.md)
