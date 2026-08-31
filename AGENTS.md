# Brand Radar Agent Instructions

## Default read route

Before changing code or claims, read in this order:

1. `README.md`
2. `docs/PROJECT-STATE.md`
3. `docs/product/PRD.md`
4. `docs/product/ROADMAP.md`
5. `docs/AGENT-EXECUTION-GOAL.md`
6. newest file under `docs/handoff/`

Use `docs/PORTFOLIO-EVIDENCE.md` whenever work affects public screenshots, README claims, case studies or resume language.

## Product boundary

- Canonical MVP: 瑞幸咖啡 / 现制咖啡 / 全国 + 上海.
- Primary product: one unified marketing-intelligence feed, supported by a calendar, emerging-keyword view and three Brief suggestions.
- MVP is P0–P2. P3 Agent-shell refinement and P4 broader Live sources must not delay the first usable Replay loop.
- The current V4.2 CLI is a baseline, not proof that the focused Dashboard exists.

## Evidence boundary

- Every external datum must declare `LIVE`, `REPLAY`, `MANUAL` or `SYNTHETIC`.
- Never substitute Replay/Mock for a failed Live source.
- Facts, inference and recommendations remain separate and cite existing source or signal IDs.
- Xiaohongshu/Douyin inputs are limited to publicly accessible pages, user-provided URLs or authorized data. Do not bypass login or platform restrictions.
- Sensitive-date or high-risk Briefs require human review; do not make final legal conclusions.
- Do not publish unverified efficiency multipliers, adoption, production use or external-send claims.

## Engineering guardrails

- Never run `push_v4.sh`; it is intentionally disabled.
- Never force-push the default branch or historical branches.
- Preserve existing work and use explicit paths/files when staging.
- Do not commit `.env`, credentials, cookies, browser profiles, `.venv`, caches, runtime databases, `memory/` or `.longrun/`.
- Dependency installs and builds must use the Codex `longrun` wrapper with a bounded timeout and no more than one retry.
- The first smoke test is `run.py --help` and `run.py --list` with model keys unset and `FEISHU_WEBHOOK_URL` empty. A natural-language task may access the network, write runtime state or send externally and is not a safe first smoke.

## Completion rule

Code completion requires the smallest real test that can falsify the change, change-relevant regression tests and an updated `docs/PROJECT-STATE.md`. A public capability claim additionally requires the evidence listed in `docs/PORTFOLIO-EVIDENCE.md`.

For Mac Mini work, update the latest repository handoff with exact branch, commit, dirty state, start/test commands and blockers before declaring the transfer ready.
