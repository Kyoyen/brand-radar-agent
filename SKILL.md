---
name: brand-radar
description: Use the current Brand Radar V4.2 CLI baseline and, after reading the product contract, evolve it into the approved Replay-first marketing-intelligence Dashboard.
---

# Brand Radar

## Read first

1. `AGENTS.md`
2. `README.md`
3. `docs/PROJECT-STATE.md`
4. `docs/product/PRD.md`
5. `docs/product/ROADMAP.md`
6. `docs/AGENT-EXECUTION-GOAL.md`
7. newest `docs/handoff/`

## Current truth

The repository currently contains a V4.2 Python CLI baseline with scenario routing, provider adapters, tool calling, structured output and Mock fallback. The focused Brand Radar Dashboard, unified MarketingSignal pipeline, calendar, keyword view, Brief panel, Replay fixtures and automated tests are not implemented yet.

Do not describe the historical presentation or synthetic sample as the current product.

## Safe baseline commands

After dependencies are installed:

```bash
env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u DEEPSEEK_API_KEY \
  -u MOONSHOT_API_KEY -u ZHIPU_API_KEY \
  FEISHU_WEBHOOK_URL= PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python run.py --help

env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u DEEPSEEK_API_KEY \
  -u MOONSHOT_API_KEY -u ZHIPU_API_KEY \
  FEISHU_WEBHOOK_URL= PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python run.py --list
```

A natural-language task may access the network, write local history or send through a configured webhook. It is not a safe first smoke.

## Product boundary

- Canonical case: 瑞幸咖啡 / 现制咖啡 / 全国 + 上海.
- MVP: unified intelligence feed, 30-day marketing calendar, emerging keywords and three evidence-linked Brief suggestions.
- Data modes: LIVE / REPLAY / MANUAL / SYNTHETIC.
- Agent role: marketing intelligence editor; filter, cluster, rank, explain and stop when evidence is insufficient.
- Xiaohongshu/Douyin: public pages, user-provided URLs or authorized data only.

## Guardrails

- Never run `push_v4.sh` or force-push.
- Never submit secrets, runtime state, estimates presented as results or unmarked synthetic data.
- Keep facts, inference and recommendations separate and evidence-linked.
- Update `docs/PROJECT-STATE.md` and the latest handoff after material work.
- Portfolio claims must pass `docs/PORTFOLIO-EVIDENCE.md`.
