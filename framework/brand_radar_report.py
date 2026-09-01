"""Render a validated Brand Radar weekly result as a meeting-ready HTML report.

The JSON result remains the traceable record.  This module only turns that same
data into a calmer, human-readable view; it never calls a model or changes the
marketing judgement.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .brand_radar_output import build_weekly_meeting_summary


PRIORITY_LABELS = {
    "follow_up_this_week": "本周跟进",
    "continue_observing": "继续观察",
    "actively_avoid": "主动避开",
    "needs_verification": "信息不完整",
}

PERSPECTIVE_LABELS = {
    "consumption_scenario": "消费场景",
    "competitor_gap": "竞品差异",
    "timing_window": "时间窗口",
    "risk_control": "风险控制",
}

OUTCOME_LABELS = {
    "needs_verification": "信息还不够",
    "latest_version_resolved": "已确认当前版本",
    "verified_competitor_evidence": "已有可用竞品材料",
    "no_pack_evidence": "观察包没有直接材料",
    "no_current_pack_evidence": "只有过期或被替换材料",
}

SKILL_LABELS = {
    "signal-triage": "信号筛选",
    "brand-fit": "品牌契合",
    "brief-distillation": "Brief 转译",
}

BRAND_PROFILE_LABELS = {
    "default": "通用默认",
    "custom": "已定制",
}

PRIORITY_ORDER = {
    "actively_avoid": 0,
    "needs_verification": 1,
    "follow_up_this_week": 2,
    "continue_observing": 3,
}


def _data(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("weekly report input must be a mapping or Pydantic model")


def _text(value: Any) -> str:
    text = str(value or "")
    for original, replacement in (
        ("人工待核便签", "来源不完整的人工便签"),
        ("保持待核", "先留在备选区"),
        ("待核快闪先补证", "信息不完整的快闪先补齐公开信息"),
        ("未核验快闪事件", "信息不完整的快闪事件"),
        ("待核区", "暂存区"),
        ("待核事件", "信息不完整的事件"),
        ("待核判断", "暂不采用的判断"),
        ("补证", "补齐公开信息"),
        ("未核验", "尚未确认"),
        ("待核", "信息不完整"),
    ):
        text = text.replace(original, replacement)
    return escape(text, quote=True)


def _safe_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return escape(value, quote=True)


def _list(items: list[Any], *, empty: str = "暂无") -> str:
    if not items:
        return f'<p class="empty">{_text(empty)}</p>'
    return "<ul>" + "".join(f"<li>{_text(item)}</li>" for item in items) + "</ul>"


def _source_links(card: Mapping[str, Any], source_by_id: dict[str, dict]) -> str:
    links: list[str] = []
    for source_id in card.get("source_ids", []):
        source = source_by_id.get(source_id, {})
        title = _text(source.get("title") or source_id)
        url = _safe_url(source.get("url"))
        status = "已确认" if source.get("verification_status") == "verified" else "来源未确认"
        label = f"{title} · {status}"
        links.append(
            f'<a href="{url}" target="_blank" rel="noreferrer">{label}</a>'
            if url
            else f"<span>{label}</span>"
        )
    for feedback_id in card.get("feedback_ids", []):
        links.append("<span>Agent 本次调查反馈</span>")
    return "".join(f"<li>{item}</li>" for item in links) or "<li>暂无可用依据</li>"


def _signal_cards(cards: list[dict], source_by_id: dict[str, dict]) -> str:
    cards = sorted(
        cards,
        key=lambda card: PRIORITY_ORDER.get(card.get("priority"), 9),
    )
    rendered: list[str] = []
    for card in cards:
        priority = card.get("priority", "continue_observing")
        rendered.append(
            f"""
            <article class="signal signal-{_text(priority)}">
              <div class="signal-head">
                <span class="status">{_text(PRIORITY_LABELS.get(priority, priority))}</span>
                <span class="meta">{_text(card.get('event_date') or '日期待定')} · {_text(' / '.join(card.get('regions', [])))}</span>
              </div>
              <h3>{_text(card.get('title'))}</h3>
              <p>{_text(card.get('fact_summary'))}</p>
              <div class="judgement"><strong>为什么值得讨论</strong><br>{_text(card.get('why_it_matters'))}</div>
              <div class="recommendation"><strong>建议</strong><br>{_text(card.get('recommendation'))}</div>
              <details>
                <summary>来源和还缺什么</summary>
                <ul class="sources">{_source_links(card, source_by_id)}</ul>
                {_list(card.get('pending_questions', []), empty='没有额外需要确认的问题')}
              </details>
            </article>
            """
        )
    return "".join(rendered)


def _calendar(items: list[dict], window: Mapping[str, Any]) -> str:
    rendered = "".join(
        f"""
        <li>
          <time>{_text(item.get('date'))}</time>
          <div><strong>{_text(item.get('title'))}</strong><span>{_text(item.get('kind'))}</span></div>
        </li>
        """
        for item in sorted(items, key=lambda item: item.get("date", ""))
    )
    return f"""
      <p class="section-note">{_text(window.get('start'))} — {_text(window.get('end'))}，只显示值得进入企划排期的节点。</p>
      <ol class="timeline">{rendered or '<li>这段时间暂未发现可用节点</li>'}</ol>
    """


def _briefs(items: list[dict], card_by_id: dict[str, dict]) -> str:
    rendered: list[str] = []
    for index, brief in enumerate(items, start=1):
        cited = [
            card_by_id[card_id].get("title", card_id)
            for card_id in brief.get("card_ids", [])
            if card_id in card_by_id
        ]
        rendered.append(
            f"""
            <article class="brief">
              <div class="brief-number">0{index}</div>
              <div>
                <span class="eyebrow">{_text(PERSPECTIVE_LABELS.get(brief.get('perspective'), brief.get('perspective')))}</span>
                <h3>{_text(brief.get('angle'))}</h3>
                <dl>
                  <dt>为什么现在</dt><dd>{_text(brief.get('why_now'))}</dd>
                  <dt>人群 / 场景</dt><dd>{_text(brief.get('audience_or_scenario'))}</dd>
                  <dt>下一步</dt><dd>{_text(brief.get('next_step'))}</dd>
                  <dt>可用依据</dt><dd>{_text('；'.join(cited) or '暂无，不能进入确认方案')}</dd>
                  <dt>缺什么</dt><dd>{_text('；'.join(brief.get('missing_evidence', [])) or '无')}</dd>
                  <dt>注意</dt><dd>{_text(brief.get('risk_note'))}</dd>
                </dl>
              </div>
            </article>
            """
        )
    return "".join(rendered)


def _brand_profile_summary(profile: Mapping[str, Any] | None) -> str:
    if not profile:
        return ""
    label = BRAND_PROFILE_LABELS.get(profile.get("mode"))
    return f"<span>品牌档案：{_text(label)}</span>" if label else ""


def _used_skill_summary(decision_log: list[Mapping[str, Any]]) -> str:
    used: list[str] = []
    for row in decision_log:
        label = SKILL_LABELS.get(row.get("skill_name"))
        if label and label not in used:
            used.append(label)
    if not used:
        return ""
    return f'<p class="used-skills">本轮使用：{_text("、".join(used))}</p>'


def _current_investigation(trace: Mapping[str, Any]) -> str:
    actions = {
        item.get("action_id"): item for item in trace.get("selected_actions", [])
    }
    steps = {item.get("step_id"): item for item in trace.get("plan_steps", [])}
    feedback_by_action = {
        item.get("action_id"): item for item in trace.get("tool_feedback", [])
    }
    feedback_by_id = {
        item.get("feedback_id"): item for item in trace.get("tool_feedback", [])
    }
    adjustments = {
        item.get("action_id"): item
        for item in trace.get("adjustment_reasons", [])
    }
    decision_log = trace.get("decision_log", [])
    rows: list[str] = []
    for row in decision_log:
        skill = SKILL_LABELS.get(row.get("skill_name"), "本轮判断")
        if row.get("decision") == "generate":
            prior_findings = [
                feedback_by_id.get(feedback_id, {}).get("summary")
                for feedback_id in row.get("based_on_feedback_ids", [])
            ]
            findings = "；".join(item for item in prior_findings if item)
            rows.append(
                f"""
                <li>
                  <div class="round-label">第 {_text(row.get('round'))} 轮</div>
                  <dl class="reasoning-grid">
                    <dt>先想确认什么</dt><dd>现有材料是否已经足够进入企划成稿</dd>
                    <dt>用了什么能力</dt><dd>{_text(skill)}</dd>
                    <dt>看到了什么</dt><dd>{_text(findings or '前面的调查反馈已经收齐')}</dd>
                    <dt>接着怎么决定</dt><dd><strong>停止调查，开始成稿。</strong> {_text(row.get('reason'))}</dd>
                  </dl>
                </li>
                """
            )
            continue

        action = actions.get(row.get("action_id"), {})
        step = steps.get(action.get("step_id"), {})
        item = feedback_by_action.get(action.get("action_id"), {})
        adjustment = adjustments.get(action.get("action_id"), {})
        next_decision = item.get("decision_hint") or adjustment.get("reason")
        outcome = OUTCOME_LABELS.get(item.get("outcome"), item.get("outcome"))
        rows.append(
            f"""
            <li>
              <div class="round-label">第 {_text(row.get('round'))} 轮</div>
              <dl class="reasoning-grid">
                <dt>先想确认什么</dt><dd><strong>{_text(step.get('objective'))}</strong><br>{_text(row.get('reason'))}</dd>
                <dt>用了什么能力</dt><dd><strong>{_text(skill)}</strong><br>{_text(action.get('reason'))}</dd>
                <dt>看到了什么</dt><dd><span class="outcome">{_text(outcome)}</span>{_text(item.get('summary'))}</dd>
                <dt>接着怎么决定</dt><dd>{_text(next_decision)}</dd>
              </dl>
            </li>
            """
        )
    question = trace.get("goal_snapshot", {}).get("business_question", "")
    return (
        _used_skill_summary(decision_log)
        + f'<p class="question">“{_text(question)}”</p>'
        + f'<ol class="investigation">{"".join(rows)}</ol>'
    )


def _legacy_investigation(trace: Mapping[str, Any]) -> str:
    if not trace:
        return '<p class="empty">这份旧结果没有保存 Agent 调查过程。</p>'
    actions = {item.get("action_id"): item for item in trace.get("selected_actions", [])}
    feedback = {item.get("action_id"): item for item in trace.get("tool_feedback", [])}
    adjustments = {item.get("action_id"): item for item in trace.get("adjustment_reasons", [])}
    rows: list[str] = []
    for step in trace.get("plan_steps", []):
        step_actions = [item for item in actions.values() if item.get("step_id") == step.get("step_id")]
        for action in step_actions:
            item = feedback.get(action.get("action_id"), {})
            adjustment = adjustments.get(action.get("action_id"), {})
            decision = item.get("decision_hint") or adjustment.get("reason")
            rows.append(
                f"""
                <li>
                  <div class="investigate-step"><span>想确认</span><strong>{_text(step.get('objective'))}</strong></div>
                  <p>{_text(action.get('reason'))}</p>
                  <div class="feedback"><span>{_text(OUTCOME_LABELS.get(item.get('outcome'), item.get('outcome')))}</span>{_text(item.get('summary'))}</div>
                  <p class="adjustment"><strong>因此：</strong>{_text(decision)}</p>
                </li>
                """
            )
    question = trace.get("goal_snapshot", {}).get("business_question", "")
    return f'<p class="question">“{_text(question)}”</p><ol class="investigation">{"".join(rows)}</ol>'


def _investigation(trace: Mapping[str, Any] | None) -> str:
    if not trace:
        return '<p class="empty">这份旧结果没有保存 Agent 调查过程。</p>'
    if trace.get("decision_log"):
        return _current_investigation(trace)
    return _legacy_investigation(trace)


def render_weekly_report(
    weekly_output: Any,
    *,
    json_path: Path,
    report_path: Path | None = None,
) -> Path:
    """Atomically write one standalone HTML report derived from ``weekly_output``."""

    data = _data(weekly_output)
    settings = data.get("observation_settings", {})
    run_info = data.get("run_info", {})
    cards = data.get("intelligence_cards", [])
    meeting_summary = build_weekly_meeting_summary(cards)
    source_by_id = {
        item.get("source_id"): item
        for item in data.get("source_catalog", [])
        if item.get("source_id")
    }
    card_by_id = {
        item.get("card_id"): item for item in cards if item.get("card_id")
    }
    focus_cards = sorted(
        (
            card
            for card in cards
            if card.get("priority")
            in {"actively_avoid", "follow_up_this_week", "needs_verification"}
        ),
        key=lambda card: PRIORITY_ORDER.get(card.get("priority"), 9),
    )[:4]
    if not focus_cards:
        focus_cards = cards[:3]
    focus_ids = {card.get("card_id") for card in focus_cards}
    background_cards = [card for card in cards if card.get("card_id") not in focus_ids]
    keywords = "".join(
        f'<span class="keyword">{_text(item.get("keyword"))}</span>'
        for item in data.get("keywords", [])
    )
    review_items = "".join(
        f'<li><span>请你确认</span>{_text(item.get("question"))}</li>'
        for item in data.get("human_review", {}).get("items", [])
    )
    mode = "真实模型" if run_info.get("mode") == "real" else "Mock 烟雾测试"
    model = " / ".join(
        part for part in [run_info.get("provider"), run_info.get("model")] if part
    )
    brand_profile_summary = _brand_profile_summary(run_info.get("brand_profile"))
    report_path = report_path or json_path.with_suffix(".html")
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Brand Radar · {_text(settings.get('brand'))}下周营销企划</title>
  <style>
    :root {{ --ink:#17211d; --muted:#68736d; --paper:#f4f0e8; --panel:#fffdf8; --line:#d9d2c5; --coffee:#5f3f2b; --mint:#cfe3d3; --amber:#efc77b; --red:#c66458; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif; line-height:1.65; }}
    main {{ width:min(1120px,calc(100% - 32px)); margin:0 auto; padding:44px 0 80px; }}
    header {{ border-bottom:1px solid var(--line); padding-bottom:30px; }}
    .brand {{ font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:var(--coffee); font-weight:700; }}
    h1 {{ font-size:clamp(32px,6vw,62px); line-height:1.05; margin:14px 0; letter-spacing:-.04em; max-width:900px; }}
    h2 {{ font-size:28px; margin:0 0 14px; letter-spacing:-.02em; }}
    h3 {{ font-size:20px; line-height:1.35; margin:10px 0; }}
    p {{ margin:8px 0; }}
    .meta-line {{ display:flex; flex-wrap:wrap; gap:8px 22px; color:var(--muted); font-size:14px; }}
    .summary {{ font-size:20px; max-width:900px; margin:26px 0 0; }}
    section {{ margin-top:54px; }}
    .section-note,.empty {{ color:var(--muted); }}
    .signals {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }}
    .signal,.brief {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:22px; }}
    .signal-head {{ display:flex; justify-content:space-between; gap:12px; align-items:center; }}
    .status,.eyebrow,.keyword,.review li span,.feedback span,.investigate-step span,.outcome {{ display:inline-flex; width:max-content; border-radius:999px; padding:3px 9px; font-size:12px; font-weight:700; background:var(--mint); }}
    .signal-needs_verification .status,.review li span {{ background:var(--amber); }}
    .signal-actively_avoid .status {{ background:#efd0ca; color:#7b271e; }}
    .meta {{ color:var(--muted); font-size:13px; text-align:right; }}
    .judgement,.recommendation {{ margin-top:14px; padding-top:12px; border-top:1px solid var(--line); }}
    details {{ margin-top:14px; }} summary {{ cursor:pointer; font-weight:700; }}
    ul {{ padding-left:20px; }} .sources a {{ color:var(--coffee); }}
    .timeline {{ list-style:none; padding:0; margin:24px 0 0; border-left:2px solid var(--coffee); }}
    .timeline li {{ display:grid; grid-template-columns:110px 1fr; gap:18px; padding:0 0 24px 22px; position:relative; }}
    .timeline li::before {{ content:""; position:absolute; width:10px; height:10px; border-radius:50%; background:var(--coffee); left:-6px; top:8px; }}
    .timeline time {{ font-weight:700; }} .timeline span {{ display:block; color:var(--muted); font-size:13px; }}
    .keyword-row {{ display:flex; flex-wrap:wrap; gap:8px; }} .keyword {{ background:var(--panel); border:1px solid var(--line); }}
    .briefs {{ display:grid; gap:14px; }}
    .brief {{ display:grid; grid-template-columns:52px 1fr; gap:12px; }} .brief-number {{ color:var(--coffee); font-size:28px; font-weight:700; }}
    dl {{ display:grid; grid-template-columns:100px 1fr; gap:8px 18px; margin:18px 0 0; }} dt {{ color:var(--muted); }} dd {{ margin:0; }}
    .question {{ font-size:22px; font-weight:700; max-width:900px; }}
    .used-skills {{ color:var(--muted); }}
    .investigation {{ list-style:none; padding:0; display:grid; gap:14px; }} .investigation>li {{ padding:18px 0; border-bottom:1px solid var(--line); }}
    .investigate-step {{ display:flex; gap:10px; align-items:center; }} .feedback {{ background:var(--panel); border-left:4px solid var(--coffee); padding:12px 14px; margin:12px 0; }} .feedback span {{ margin-right:9px; }} .adjustment {{ color:var(--coffee); }}
    .round-label {{ color:var(--coffee); font-size:13px; font-weight:700; }} .reasoning-grid {{ grid-template-columns:120px 1fr; background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; }} .reasoning-grid .outcome {{ margin-right:9px; }}
    .review {{ list-style:none; padding:0; display:grid; gap:10px; }} .review li {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px; }} .review li span {{ margin-right:10px; }}
    footer {{ margin-top:60px; padding-top:24px; border-top:1px solid var(--line); color:var(--muted); font-size:13px; }}
    @media (max-width:720px) {{ main {{ width:min(100% - 22px,1120px); padding-top:28px; }} .signals {{ grid-template-columns:1fr; }} .signal-head {{ align-items:flex-start; }} .brief {{ grid-template-columns:1fr; }} dl {{ grid-template-columns:1fr; gap:2px; }} dd {{ margin-bottom:9px; }} .timeline li {{ grid-template-columns:1fr; gap:2px; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div class="brand">Brand Radar · Weekly intelligence</div>
    <h1>{_text(settings.get('brand'))} · 下周营销企划雷达</h1>
    <div class="meta-line">
      <span>{_text(settings.get('category'))}</span><span>{_text(' / '.join(settings.get('regions', [])))}</span>
      <span>{_text(mode)} · {_text(model)}</span><span>生成于 {_text(run_info.get('completed_at'))}</span>
      {brand_profile_summary}
    </div>
    <p class="summary">{_text(meeting_summary)}</p>
  </header>

  <section><h2>这周先讨论什么</h2><div class="signals">{_signal_cards(focus_cards, source_by_id)}</div></section>
  <section><h2>三条企划 Brief</h2><div class="briefs">{_briefs(data.get('briefs', []), card_by_id)}</div></section>
  <section><h2>未来 30 天关键节点</h2>{_calendar(data.get('calendar', []), settings.get('calendar_window', {}))}</section>
  <section><h2>关键词</h2><div class="keyword-row">{keywords or '<span class="empty">暂无关键词</span>'}</div></section>
  <section><h2>Agent 逐轮怎么想</h2>{_investigation(data.get('investigation_trace'))}</section>
  {'<section><h2>继续观察的背景信号</h2><div class="signals">' + _signal_cards(background_cards, source_by_id) + '</div></section>' if background_cards else ''}
  <section><h2>交给你确认</h2><ul class="review">{review_items}</ul></section>

  <footer>
    <strong>当前状态：等你确认后再使用。</strong> 本次没有发送飞书、没有发布、没有投放、没有修改预算。<br>
    可追溯结果：{_text(json_path.name)} · schema {_text(data.get('schema_version'))}
  </footer>
</main>
</body>
</html>
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(report_path.suffix + ".tmp")
    try:
        temporary.write_text(html, encoding="utf-8")
        temporary.replace(report_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return report_path


__all__ = ["render_weekly_report"]
