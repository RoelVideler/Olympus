# Code Review Report — Olympus Phase 1 Hermes Plugins

**Run ID:** `20260524-165538-53bf1476`
**Scope:** `git diff 57abed0..HEAD` — 44 files changed, +4407/-286 lines
**Base:** `57abed0` (fix: chip-in streaming)
**Intent:** Complete Phase 1 implementation of Hermes plugins architecture — Olympus extends Hermes with 5 plugins (zeus, supervisor, revolt, dashboard, share_knowledge) and 10 agent profiles.

## Review Team

| Reviewer | Trigger |
|----------|---------|
| correctness | always-on |
| testing | always-on |
| maintainability | always-on |
| project-standards | always-on |
| agent-native-reviewer | always-on |
| learnings-researcher | always-on |
| security | auth, WebSocket, bot tokens, session cookies |
| reliability | health monitoring, idle TTL, subprocess lifecycle, WebSocket reconnection |
| api-contract | REST endpoints, GraphQL, tool schemas, WebSocket protocol |
| adversarial | 4400+ lines executable, external API, process management |
| kieran-python | Python code quality |

---

## P0 — Critical (6 findings)

| # | File | Issue | Reviewer(s) | Confidence | Route |
|---|------|-------|-------------|------------|-------|
| 1 | `revolt/client.py:55` | RevoltClient.authenticate() closes aiohttp session before returning — all subsequent API calls fail | correctness, reliability, adversarial, kieran-python | 0.95 | safe_auto → review-fixer |
| 2 | `share_knowledge/__init__.py:1` | Imports non-existent SPEC — ImportError crashes plugin at load | correctness, agent-native | 0.99 | safe_auto → review-fixer |
| 3 | `zeus/skills/chip_in.py:120` | asyncio.run() crashes with RuntimeError when called from async context | correctness, reliability, adversarial | 0.90 | gated_auto → review-fixer |
| 4 | `revolt/adapter.py:213` | Reconnect loop spins at 100% CPU after max retries — asyncio.sleep(-1) returns immediately | correctness, reliability, adversarial | 0.95 | safe_auto → review-fixer |
| 5 | `dashboard/websocket.py:72` | WebSocket /ws has no authentication — any unauthenticated client can connect | security, adversarial | 0.95 | safe_auto → review-fixer |
| 6 | `revolt/adapter.py:226` | Revolt user allowlist documented but never enforced — any user can message the bot | security, adversarial | 0.90 | gated_auto → downstream-resolver |

## P1 — High (9 findings)

| # | File | Issue | Reviewer(s) | Confidence | Route |
|---|------|-------|-------------|------------|-------|
| 7 | `dashboard/graphql.py:23` | GRAPHENE_AVAILABLE always True — except block sets True instead of False | maintainability, kieran-python | 0.99 | safe_auto → review-fixer |
| 8 | `dashboard/graphql.py:158` | GraphQL GET endpoint always returns 400 — query parameter support not implemented | correctness, api-contract | 0.90 | safe_auto → review-fixer |
| 9 | `dashboard/auth.py:119` | handle_login crashes with AttributeError when JSON body is not a dict | correctness | 0.85 | safe_auto → review-fixer |
| 10 | `supervisor/health.py:36` | Health monitor creates infinite restart loop for always-on profiles that crash on startup | reliability, adversarial | 0.85 | gated_auto → downstream-resolver |
| 11 | `dashboard/websocket.py:62` | WebSocketHub get_hub() TOCTOU race — concurrent calls can create duplicate hubs | correctness | 0.80 | safe_auto → review-fixer |
| 12 | `dashboard/auth.py:133` | Unsalted SHA-256 password hashing — trivially crackable | security | 0.95 | gated_auto → downstream-resolver |
| 13 | `supervisor/lifecycle.py:42` | Path traversal in PID files — unsanitized profile names allow writing outside directory | security | 0.85 | safe_auto → review-fixer |
| 14 | `share_knowledge/__init__.py:1` | No register() function — tool never registered with Hermes even after import fix | agent-native | 0.95 | gated_auto → downstream-resolver |
| 15 | `tests/test_share_knowledge.py:12` | Tests duplicated inline wrapper, not actual production code | testing | 0.95 | manual → downstream-resolver |

## P2 — Moderate (5 findings)

| # | File | Issue | Reviewer(s) | Confidence | Route |
|---|------|-------|-------------|------------|-------|
| 16 | `revolt/adapter.py:27` | RevoltMessageRouter imported but never used — 131 lines dead code | maintainability | 0.95 | safe_auto → review-fixer |
| 17 | `dashboard/api.py:80` | Inconsistent error response shapes — 5 different error formats | api-contract | 0.90 | manual → downstream-resolver |
| 18 | `dashboard/auth.py:113` | No login rate limiting — unlimited brute-force attempts | security | 0.90 | gated_auto → downstream-resolver |
| 19 | `dashboard/auth.py:133` | First-login password race — whoever hits /api/login first sets admin password | adversarial | 0.80 | gated_auto → downstream-resolver |
| 20 | `profiles/zeus/config.yaml:14` | Supervisor tools not in any profile's toolsets — Zeus cannot call them | agent-native | 0.85 | safe_auto → review-fixer |

---

## Applied Fixes

No fixes applied (report-only mode).

## Residual Actionable Work

The following findings require manual resolution:

- **#6** Revolt user allowlist enforcement (gated_auto → downstream-resolver)
- **#10** Supervisor infinite restart loop prevention (gated_auto → downstream-resolver)
- **#12** Password hashing upgrade to bcrypt/pbkdf2 (gated_auto → downstream-resolver)
- **#14** share_knowledge register() function (gated_auto → downstream-resolver)
- **#15** Rewrite test_share_knowledge.py to test actual code (manual → downstream-resolver)
- **#17** Standardize API error response format (manual → downstream-resolver)
- **#18** Add login rate limiting (gated_auto → downstream-resolver)
- **#19** Fix first-login password race (gated_auto → downstream-resolver)

## Learnings & Past Solutions

No `docs/solutions/` directory exists. Relevant planning documents found:
- Architecture design document confirms Supervisor must be standalone (not gateway extension)
- FTS5 trigger sync, scope enforcement, and plugin API matching were identified as high-priority during planning
- Phase 1 success criteria include: all 5 plugins load, all 10 profiles boot, share_knowledge round-trip works

## Agent-Native Gaps

- **share_knowledge plugin** has two critical bugs (import error + missing register()) that prevent any agent from using knowledge sharing
- **Supervisor tools** registered but not added to any profile's toolsets — Zeus cannot manage profiles
- **Dashboard** is human-only web UI with no agent-accessible equivalent
- **Tool schema formats** inconsistent (share_knowledge uses wrapped format, others use bare)
- **Tool return types** inconsistent (share_knowledge returns JSON strings, others return dicts)

## Coverage

- **11 reviewers dispatched**, 11 returned results
- **0 findings suppressed** (all above 0.60 confidence threshold)
- **6 P0, 9 P1, 5 P2** findings identified
- **6 residual risks** identified
- **10 testing gaps** identified

## Verdict: **Not ready**

This PR has 6 critical (P0) findings that must be fixed before merge:

1. **Revolt plugin is non-functional** — the session closes immediately after authentication (P0, agreed by 4 reviewers)
2. **share_knowledge plugin crashes at load** — import error for non-existent SPEC (P0)
3. **chip_in tool crashes in async context** — asyncio.run() from running event loop (P0, agreed by 3 reviewers)
4. **Reconnect loop burns CPU** — negative sleep delay after max retries (P0, agreed by 3 reviewers)
5. **WebSocket has no auth** — unauthenticated access to real-time data (P0, agreed by 2 reviewers)
6. **Revolt allowlist not enforced** — any user can interact with the bot (P0, agreed by 2 reviewers)

Additionally, the test suite provides false confidence: `test_share_knowledge.py` tests a duplicated inline wrapper, not the actual production code, and ~400 of 648 lines in `test_integration.py` are structural checks that pass regardless of whether the code works.

**Recommended fix order:** #2 → #1 → #4 → #3 → #5 → #7 → #8 → #9 → #11 → #13 → #16 → #20 → then address P1 gated items.
