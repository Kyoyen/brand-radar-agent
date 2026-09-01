# Brand-Driven Marketing Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 Brand Radar weekly 骨架上加入通用/可更新的 `BRAND.md`、六问品牌向导、产品运行时 `AGENTS.md`、三项营销技能和逐轮观察反馈循环。

**Architecture:** 提交一份通用 `BRAND.md`，本机定制档案写入已忽略的 `memory/brand/BRAND.md`；`AgentRunner` 读取实际档案、`agent/AGENTS.md` 和技能目录。真实 weekly 由“一次规划多个动作”改成“每轮一个动作，读反馈后再决定”，最多三次，然后沿用现有生成、专用校验、一次修正和人工复核。

**Tech Stack:** Python 3.12+、argparse、Pydantic、unittest、Markdown、现有 DeepSeek/Zhipu provider 适配。

---

### Task 1: 清理并行草稿，恢复可信基线

**Files:**
- Modify: `framework/agent_runner.py`
- Modify: `framework/session_summarizer.py`
- Modify: `tests/test_weekly_agent_loop.py`
- Modify: `README.md`
- Modify: `docs/PROJECT-STATE.md`
- Modify: `docs/product/AGENT-BUILD.md`
- Delete: `skills/brand_radar_weekly/brief-builder/SKILL.md`
- Delete: `skills/brand_radar_weekly/signal-triage/SKILL.md`

- [ ] **Step 1: 恢复失败路径断言**

把 `test_second_validation_failure_stops_without_artifact_or_third_generation` 中的断言恢复为：

```python
self.assertEqual(3, len(llm.calls))
self.assertEqual([], leftovers)
```

- [ ] **Step 2: 删除 weekly 成功后的隐藏经验总结调用**

删除 `run_weekly()` 结尾的 `save_experience()` 调用，并把 `SessionSummarizer` 恢复为不因本轮 weekly 测试改变默认目录或额外调用模型的版本。

- [ ] **Step 3: 删除尚未完成却已写成完成态的文档句子**

README 和项目状态只在真实新链路跑通后更新，不保留“技能/经验已经接入”的提前结论。

- [ ] **Step 4: 运行原有 weekly loop 测试**

Run: `.venv/bin/python -m unittest tests.test_weekly_agent_loop`

Expected: 原有测试通过；失败路径不产生文件，也不产生经验记录。

### Task 2: 建立品牌档案与六问状态机

**Files:**
- Create: `BRAND.md`
- Create: `agent/AGENTS.md`
- Create: `framework/brand_profile.py`
- Create: `tests/test_brand_profile.py`
- Modify: `run.py`
- Modify: `tests/test_weekly_cli.py`

- [ ] **Step 1: 写品牌状态机测试**

覆盖以下行为：

```python
interview = BrandInterview()
assert len(interview.questions) == 6
interview.answer("让日常咖啡更轻松")
assert "让日常咖啡更轻松" in interview.next_question().prompt
```

并覆盖全跳过不创建本机档案、部分回答补齐默认值、第二次更新空行保留旧值、原子写入不留 `.tmp`。

- [ ] **Step 2: 实现通用档案加载顺序**

在 `framework/brand_profile.py` 提供：

```python
@dataclass(frozen=True)
class BrandProfile:
    path: Path
    content: str
    mode: Literal["default", "custom"]
    answered_questions: int
    fingerprint: str

def load_brand_profile(
    explicit_path: str | Path | None = None,
    *,
    default_path: Path = DEFAULT_BRAND_PATH,
    local_path: Path = LOCAL_BRAND_PATH,
) -> BrandProfile:
    ...
```

加载顺序固定为：显式路径、存在的本机档案、仓库通用档案。

- [ ] **Step 3: 实现六问 `BrandInterview`**

每次 `answer()` 只推进一个问题；`""`、`skip`、`跳过` 使用现有值或通用默认。`render_brand_markdown()` 必须总能输出六个完整章节。

- [ ] **Step 4: 实现原子保存**

```python
temporary = destination.with_suffix(destination.suffix + ".tmp")
temporary.write_text(content, encoding="utf-8")
temporary.replace(destination)
```

只有完成全部问题并确认保存后才调用；中断时不得留下目标文件或临时文件。

- [ ] **Step 5: 增加 `--brand-setup`**

`run.py` 在 `check_env()` 之前处理该命令，因此品牌建档不依赖 API Key。它与 `--weekly` 等运行命令互斥。

- [ ] **Step 6: 运行品牌与 CLI 测试**

Run: `.venv/bin/python -m unittest tests.test_brand_profile tests.test_weekly_cli`

Expected: 六问、跳过、更新、无 Key 建档和参数互斥全部通过。

### Task 3: 建立三项营销技能与按需目录

**Files:**
- Create: `skills/brand-radar/signal-triage/SKILL.md`
- Create: `skills/brand-radar/brand-fit/SKILL.md`
- Create: `skills/brand-radar/brief-distillation/SKILL.md`
- Modify: `framework/agent_runner.py`
- Test: `tests/test_weekly_agent_loop.py`

- [ ] **Step 1: 写技能目录测试**

断言首轮决策提示只包含技能名和 description；完整技能正文只在该技能被选择后进入后续上下文和最终生成上下文。

- [ ] **Step 2: 实现技能加载**

保留一个很薄的内部结构：

```python
@dataclass(frozen=True)
class _MarketingSkill:
    name: str
    description: str
    content: str
```

只扫描 `skills/brand-radar/*/SKILL.md`，要求 YAML front matter 中有唯一 `name` 和非空 `description`，并限制单文件大小。

- [ ] **Step 3: 写三份技能正文**

三项技能分别只回答：信号值不值得查、信号适不适合本品牌、已有判断怎样转成三条不同 Brief。

- [ ] **Step 4: 运行技能加载测试**

Run: `.venv/bin/python -m unittest tests.test_weekly_agent_loop`

Expected: 技能目录稳定、未知技能失败、已选技能正文按需进入上下文。

### Task 4: 把 weekly 改成逐轮决策

**Files:**
- Modify: `framework/agent_runner.py`
- Modify: `framework/brand_radar_output.py`
- Modify: `tests/test_weekly_agent_loop.py`
- Modify: `tests/test_investigation_trace.py`
- Modify: `tests/test_brand_radar_output.py`

- [ ] **Step 1: 写失败测试描述目标循环**

脚本模型响应顺序改为：

```python
decision_1 = {"decision": "investigate", "skill_name": "signal-triage", ...}
decision_2 = {"decision": "investigate", "skill_name": "brand-fit", ...}
decision_3 = {"decision": "generate", "skill_name": "brief-distillation", ...}
generation = {"adjustment_reasons": [...], "result": {...}}
```

断言第二轮提示包含第一轮 feedback，第三轮包含前两轮 feedback，且程序生成的 action/feedback ID 唯一。

- [ ] **Step 2: 增加严格决策模型**

```python
class _InvestigationDecision(_StrictResponse):
    decision: Literal["investigate", "generate"]
    skill_name: Literal["signal-triage", "brand-fit", "brief-distillation"]
    objective: str
    reason: str
    action_type: InvestigationAction | None = None
    arguments: dict[str, str] = Field(default_factory=dict)
```

`investigate` 必须包含一个白名单动作；`generate` 不得包含动作参数。程序按轮次生成 `step-1/action-1` 等 ID。

- [ ] **Step 3: 实现最多三动作的循环**

每轮只执行一个动作，将累积的 `selected_actions` 和 `tool_feedback` 放进下一轮用户消息。至少一个动作后才允许 `generate`；三次动作后仍不结束则明确失败，不自动编造停止理由。

- [ ] **Step 4: 记录 `decision_log` 并升级新结果到 1.2**

每轮记录：轮次、所选技能、继续调查或开始企划、基于哪些已有 feedback、业务理由、关联 action。旧 1.0/1.1 仍可读取；1.2 必须以 `generate` 决策结束。

- [ ] **Step 5: 注入品牌与运行规则**

每个决策轮和最终生成都包含实际生效的 `BRAND.md` 与 `agent/AGENTS.md`。`run_info` 记录品牌档案的 mode、文件、回答数和 fingerprint，模型不得覆盖。

- [ ] **Step 6: 保留一次修正与失败不落盘**

生成后的专用校验逻辑不扩大循环；修正仍最多一次，失败时 JSON、HTML、`.tmp` 均为空。

- [ ] **Step 7: 运行 loop 与输出测试**

Run: `.venv/bin/python -m unittest tests.test_weekly_agent_loop tests.test_investigation_trace tests.test_brand_radar_output`

Expected: 逐轮反馈、技能选择、1.2 轨迹、旧结果兼容和失败路径全部通过。

### Task 5: 让周会稿展示品牌起点与 Agent 思路

**Files:**
- Modify: `framework/brand_radar_report.py`
- Modify: `tests/test_brand_radar_report.py`

- [ ] **Step 1: 写报告测试**

断言 HTML 出现：

```text
品牌档案：通用默认 / 已定制
本轮使用：信号筛选、品牌契合、Brief 转译
看完第一项后，Agent 为什么继续或停止
```

- [ ] **Step 2: 用业务语言渲染决策日志**

不显示 JSON 字段名；按轮次展示“先想确认什么 → 用了什么能力 → 看到了什么 → 接着怎么决定”。移除当前重复出现的“Agent 为什么查这些”区块。

- [ ] **Step 3: 运行报告测试**

Run: `.venv/bin/python -m unittest tests.test_brand_radar_report`

Expected: 新信息可见，旧 1.1 报告仍可渲染，HTML 转义仍通过。

### Task 6: 同步业务说明并完成真实运行

**Files:**
- Modify: `README.md`
- Modify: `docs/product/AGENT-BUILD.md`
- Modify: `docs/product/ROADMAP.md`
- Modify: `docs/PROJECT-STATE.md`
- Modify: `docs/handoff/MACMINI-HANDOFF.md`

- [ ] **Step 1: 运行全量本地测试**

Run: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`

Expected: 全部通过，无网络调用和本机记忆污染。

- [ ] **Step 2: 跑 Mock 冒烟**

Run: `.venv/bin/python run.py --weekly`

Expected: 明确标记 Mock 或使用当前配置的真实 provider；无 Key 时不把结果说成业务成功。

- [ ] **Step 3: 跑真实 Key 完整链路**

Run: `.venv/bin/python run.py --weekly --require-api`

Expected: 逐轮决策、品牌档案、技能选择、JSON、HTML、`awaiting_human_review` 全部出现。

- [ ] **Step 4: 跑错误 Key**

使用临时错误 Key 环境执行同一命令；Expected: 非零退出，明确鉴权失败，不降级 Mock，不增加 JSON/HTML/tmp。

- [ ] **Step 5: 用业务语言更新文档**

只写真实运行中已经看到的体验、产物路径和剩余薄弱点，不把终端向导描述成已完成 GUI。

- [ ] **Step 6: 使用 `postflight` 收尾**

核对分支、diff、测试、真实产物、错误 Key、仓库状态和启动命令；随后提交并推送当前目标分支。
