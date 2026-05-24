---
title: Migrate Dashboard from aiohttp to Hermes Native Plugin
type: refactor
status: active
date: 2026-05-24
origin: openspec/changes/phase1-hermes-plugins/specs/dashboard-plugin/spec.md
---

# Migrate Dashboard from aiohttp to Hermes Native Plugin

## Overview

Replace the standalone aiohttp dashboard server (`plugins/dashboard/`) with a Hermes dashboard plugin that extends the built-in `hermes dashboard` (FastAPI, port 9119). The current approach runs a separate HTTP server on port 8080 with its own auth system. The Hermes-native approach mounts REST, GraphQL, and WebSocket routes inside the existing dashboard at `/api/plugins/olympus/`, shares its auth, and eliminates the second server process.

## Problem Frame

The current dashboard plugin starts its own aiohttp server on port 8080, creating:
- Two separate web servers (Hermes on :9119, Olympus on :8080)
- Separate auth systems (users log in twice)
- CORS complexity between origins
- Resource overhead of two HTTP servers
- A non-native feel — bolted on rather than integrated

Hermes v0.14.0 has a mature dashboard plugin system with FastAPI router mounting, session auth, WebSocket support, and a React frontend with tab navigation. The Olympus dashboard should extend this rather than duplicate it.

## Requirements Trace

From `openspec/changes/phase1-hermes-plugins/specs/dashboard-plugin/spec.md`:

- R1. Dashboard plugin serves REST endpoints: `/api/health`, `/api/wiki`, `/api/calendar`, `/api/contacts`, `/api/preferences`
- R2. Deferred endpoints return 501 Not Implemented
- R3. Dashboard plugin serves GraphQL endpoint for complex multi-type queries
- R4. Dashboard plugin serves WebSocket for streaming Zeus responses and system events
- R5. Dashboard plugin authenticates requests (now handled by Hermes dashboard session middleware)

## Scope Boundaries

- **In scope:** Backend API migration (aiohttp → FastAPI), plugin packaging, manifest creation
- **In scope:** Fix all review findings from the Phase 1 audit within each plugin
- **Out of scope:** Frontend tab UI (the Hermes dashboard plugin system supports JS bundles, but the spec only requires backend endpoints; a minimal tab can be added later)
- **Out of scope:** Changes to other plugins (zeus, supervisor, revolt, share_knowledge) except their review-fix steps

## Context & Research

### Relevant Code and Patterns

- **Hermes dashboard plugin system:** `~/.hermes/hermes-agent/hermes_cli/web_server.py` — FastAPI server with plugin discovery at `plugins/*/dashboard/manifest.json`
- **Kanban plugin (reference):** `~/.hermes/hermes-agent/plugins/kanban/dashboard/` — full example with FastAPI router, WebSocket, manifest.json, and JS frontend bundle
- **Plugin API mounting:** Routes mounted at `/api/plugins/<name>/` via `app.include_router(router, prefix=f"/api/plugins/{plugin['name']}")`
- **WebSocket auth:** Session token passed as `?token=` query param (browsers can't set Authorization on WS upgrade)
- **HTTP auth:** Handled by dashboard's `auth_middleware` — plugin routes are automatically protected
- **Project plugin restriction:** Python API auto-import is blocked for "project" plugins (security restriction). Must install to `~/.hermes/plugins/` for API routes to work.

### Key Technical Decisions

- **Framework:** FastAPI (Hermes dashboard uses FastAPI; aiohttp is replaced)
- **Auth:** Remove custom session auth; rely on dashboard's built-in session middleware
- **GraphQL:** Use Strawberry (FastAPI-native GraphQL) or defer to Phase 3 if complexity is too high. The kanban plugin doesn't use GraphQL, so no reference pattern exists.
- **WebSocket:** FastAPI WebSocket endpoint within the plugin router, following kanban's `/events` pattern
- **Installation:** Symlink `plugins/olympus-dashboard/` → `~/.hermes/plugins/olympus-dashboard/` for development; `hermes plugins install` for production
- **Port:** No separate port — runs inside Hermes dashboard on :9119

## Open Questions

### Resolved During Planning

- **Frontend tab needed?** No — the spec requires backend endpoints. A minimal tab can be added later. The plugin will register without a tab or with `tab.hidden: true`.
- **GraphQL library?** No external dependency needed. The current implementation is already a lightweight string-matching parser (`_execute_query` in `graphql.py`) that doesn't use Graphene or any GraphQL library. Port as-is. The `GRAPHENE_AVAILABLE = True` typo in the except block is a separate bug to fix.
- **Where does the plugin live?** Source in `plugins/olympus-dashboard/` within the Olympus repo; symlinked to `~/.hermes/plugins/olympus-dashboard/` for development.
- **Step ordering:** Small fixes first (share_knowledge, zeus) → medium fixes (supervisor, revolt) → big migration (dashboard) → final audit. This ensures the migration happens on a stable codebase with fewer outstanding bugs, and each review gate is focused.

### Deferred to Implementation

- **Strawberry availability:** Whether Strawberry is already installed in the Hermes venv or needs to be added as a dependency
- **Seed data integration:** Whether seed_data.py runs at plugin load time or needs a separate trigger

## Output Structure

```
Olympus repo:
plugins/olympus-dashboard/
├── manifest.json          # Hermes dashboard plugin manifest
├── plugin_api.py          # FastAPI router (REST + GraphQL + WebSocket)
├── seed_data.py           # Database seed data (ported from plugins/dashboard/)
└── dist/                  # Optional: minimal frontend bundle (deferred)
    └── index.js

Installed at (symlink):
~/.hermes/plugins/olympus-dashboard/ → ../../openspec/Olympus/plugins/olympus-dashboard/

Removed:
plugins/dashboard/           # Old aiohttp-based plugin (deleted entirely)
```

## Implementation Units

### Fix Sequence: Plugin-by-Plugin with Review Gates

Before the dashboard migration, fix existing plugins in order of increasing complexity. Each step ends with `/ce:review`. The ordering is deliberate: small fixes first (quick wins, reduce P0 count), then medium fixes (isolated, well-understood), then the big migration (on a stable codebase), then final audit.

- [ ] **Step 0: Archive current state and create change branch**

**Goal:** Create a clean starting point with the review findings captured.

**Dependencies:** None

**Files:**
- Modify: (git operations only)

**Approach:**
- Commit current state as "phase1: initial implementation (pre-fix)"
- Create branch `fix/phase1-review-findings`
- Create OpenSpec change for tracking

**Verification:**
- Clean working tree on new branch

- [ ] **Step 1: Fix share_knowledge plugin (trivial fixes)**

**Goal:** Fix the two critical bugs and broken tests in share_knowledge.

**Requirements:** R1 (share-knowledge-plugin spec)

**Dependencies:** Step 0

**Files:**
- Modify: `plugins/share_knowledge/__init__.py`
- Modify: `plugins/share_knowledge/tools.py`
- Modify: `tests/test_share_knowledge.py`

**Approach:**
- Fix `SPEC` import → `SHARE_KNOWLEDGE_SCHEMA as SPEC`
- Add `register(ctx)` function that calls `ctx.register_tool()`
- Rewrite `test_share_knowledge.py` to import and test actual production code instead of the inline wrapper

**Test scenarios:**
- Happy path: Import share_knowledge plugin without ImportError
- Happy path: `register(ctx)` registers the tool successfully
- Integration: Tests call actual `ShareKnowledgeTool` from `tools.py`, not a wrapper
- Edge case: Scope enforcement works with actual production code

**Verification:**
- `pytest tests/test_share_knowledge.py` passes
- Plugin imports without error

- [ ] **Step 2: Fix zeus plugin (asyncio + toolsets)**

**Goal:** Fix the asyncio.run() crash and add supervisor to Zeus toolsets.

**Requirements:** R1, R2 (zeus-plugin spec)

**Dependencies:** Step 0

**Files:**
- Modify: `plugins/zeus/skills/chip_in.py`
- Modify: `profiles/zeus/config.yaml`

**Approach:**
- Replace `asyncio.run(_run())` with `asyncio.get_running_loop()` detection + `loop.run_in_executor()` fallback
- Add `supervisor` to the `toolsets` list in `profiles/zeus/config.yaml`

**Test scenarios:**
- Happy path: chip_in works when called from sync context
- Happy path: chip_in works when called from async context (no RuntimeError)
- Integration: Zeus profile config includes supervisor in toolsets

**Verification:**
- chip_in handler doesn't crash in either context
- Zeus config.yaml includes supervisor toolset

- [ ] **Step 3: Fix supervisor plugin (restart loop + path traversal)**

**Goal:** Fix infinite restart loop and path traversal vulnerability.

**Requirements:** R1, R2, R3, R4 (supervisor-plugin spec)

**Dependencies:** Step 0

**Files:**
- Modify: `plugins/supervisor/health.py`
- Modify: `plugins/supervisor/lifecycle.py`

**Approach:**
- Fix infinite restart loop: Add crash count tracking with exponential backoff. After N consecutive crashes within a time window, stop attempting restarts
- Fix path traversal: Validate profile name is alphanumeric before using in path. Reject names containing `/` or `..`

**Test scenarios:**
- Happy path: Always-on profile starts and stays running
- Happy path: Profile name validation rejects path traversal attempts
- Edge case: Crashing profile stops restarting after N consecutive failures
- Error path: Invalid profile name returns error without writing files

**Verification:**
- Crashing profiles don't cause infinite restart loops
- Path traversal attempts are rejected

- [ ] **Step 4: Fix revolt plugin (session lifecycle + reconnect + allowlist + dead code)**

**Goal:** Fix the session-close bug, reconnect loop CPU spin, implement user allowlist, remove dead code.

**Requirements:** R1, R3, R4 (revolt-plugin spec)

**Dependencies:** Step 0

**Files:**
- Modify: `plugins/revolt/client.py`
- Modify: `plugins/revolt/adapter.py`
- Modify: `plugins/revolt/error_handler.py`
- Remove: `plugins/revolt/routing.py` (dead code)

**Approach:**
- Fix `authenticate()`: Create `ClientSession` outside `async with`, manage lifecycle manually
- Fix reconnect loop: Check `delay < 0` after `get_backoff()`, stop reconnecting if negative
- Fix error_handler: Call `reset()` after successful reconnect
- Implement allowlist: Parse `REVOLT_ALLOWED_USERS` env var, reject messages from unauthorized users in `_on_message()`
- Remove unused `RevoltMessageRouter` import and routing.py file

**Test scenarios:**
- Happy path: Client session stays open after authenticate()
- Happy path: Messages from allowed users are processed
- Edge case: Messages from non-allowed users are rejected
- Error path: Reconnect loop stops after max retries (no CPU spin)
- Error path: Authentication errors stop retrying (not transient errors)

**Verification:**
- RevoltClient session remains usable after authenticate()
- Reconnect loop exits cleanly after max retries
- Allowlist enforcement works

- [ ] **Step 5: Migrate dashboard to Hermes native plugin (main migration)**

**Goal:** Replace aiohttp dashboard with FastAPI plugin for Hermes dashboard.

**Requirements:** R1, R2, R3, R4, R5 (dashboard-plugin spec)

**Dependencies:** Steps 1-4 (all plugin fixes complete)

**Files:**
- Create: `plugins/olympus-dashboard/manifest.json`
- Create: `plugins/olympus-dashboard/plugin_api.py`
- Create: `plugins/olympus-dashboard/seed_data.py`
- Remove: `plugins/dashboard/__init__.py`
- Remove: `plugins/dashboard/api.py`
- Remove: `plugins/dashboard/auth.py`
- Remove: `plugins/dashboard/graphql.py`
- Remove: `plugins/dashboard/websocket.py`
- Remove: `plugins/dashboard/seed_data.py`
- Remove: `plugins/dashboard/plugin.yaml`

**Approach:**
- Create `manifest.json` with plugin metadata (name: olympus, no tab — backend only)
- Create `plugin_api.py` with FastAPI `APIRouter` containing:
  - `GET /health` — system health from SQLite
  - `GET /wiki` — wiki/knowledge entries
  - `GET /calendar` — calendar events
  - `GET /contacts` — contact list
  - `GET /preferences` — user preferences
  - Deferred endpoints returning 501
  - `POST /graphql` — port existing lightweight parser as-is (no external GraphQL library needed; the current `_execute_query` function is a string-matching parser that works without Graphene)
  - `GET /ws` — WebSocket for Zeus response streaming and system events
- Port data access logic from old `api.py` (SQLite queries remain the same)
- Remove all auth code — dashboard's session middleware handles it
- Port WebSocket from old `websocket.py` using FastAPI WebSocket pattern (follow kanban's `/events` pattern with `?token=` query param)
- Port seed_data.py
- Create symlink: `~/.hermes/plugins/olympus-dashboard` → Olympus repo path
- Fix GRAPHENE_AVAILABLE typo (set to `False` in except block) as part of the port

**Key mapping — old routes to new:**

```
OLD (aiohttp :8080)              NEW (FastAPI /api/plugins/olympus/)
─────────────────────────────────────────────────────────────────────
GET  /api/health          →      GET  /health
GET  /api/wiki            →      GET  /wiki
GET  /api/calendar        →      GET  /calendar
GET  /api/contacts        →      GET  /contacts
GET  /api/preferences     →      GET  /preferences
POST /api/graphql         →      POST /graphql
POST /api/login           →      REMOVED (dashboard handles auth)
GET  /ws                  →      GET  /ws  (WebSocket)
GET  /api/tasks (501)     →      GET  /tasks  (501)
...other deferred 501...  →      ...same pattern...
```

**Auth change:**

```
OLD: Custom session cookies with hashlib.sha256 password hashing
NEW: Hermes dashboard session middleware (bearer token or session cookie)

The /api/login endpoint is REMOVED. Users authenticate via `hermes dashboard`
which prints a URL with session token. Plugin routes are automatically protected.
```

**WebSocket auth pattern (from kanban):**

```python
@router.websocket("/ws")
async def stream_events(ws: WebSocket):
    token = ws.query_params.get("token")
    if not _check_ws_token(token):
        await ws.close(code=1008)
        return
    await ws.accept()
    # ... broadcast loop ...
```

**GraphQL approach:** Port the existing `_execute_query` function as-is. It's a lightweight string-matching parser that checks if field names ("health", "wiki", "calendar", etc.) appear in the query string and calls the appropriate resolver. No Graphene, no Strawberry, no external dependency. The current implementation already works this way — we're just moving it from aiohttp to FastAPI.

**Test scenarios:**
- Happy path: Plugin manifest is valid JSON with required fields
- Happy path: GET /health returns health data from SQLite
- Happy path: GET /wiki returns wiki entries
- Happy path: GET /calendar returns calendar events
- Happy path: GET /contacts returns contacts
- Happy path: GET /preferences returns preferences
- Happy path: POST /graphql returns combined data for multi-field query
- Happy path: Deferred endpoints return 501
- Happy path: WebSocket accepts connection with valid token
- Error path: WebSocket rejects connection without token
- Error path: Unauthenticated HTTP requests are rejected (by dashboard middleware)
- Integration: Plugin is discovered by Hermes dashboard (manifest in correct location)

**Verification:**
- `hermes dashboard` starts with olympus plugin loaded
- All 5 REST endpoints return correct data
- GraphQL endpoint returns combined data
- WebSocket connects and streams events
- No separate aiohttp process running

- [ ] **Step 6: Final audit — /ce:review on entire diff**

**Goal:** Run comprehensive review on all changes, then verify against OpenSpec phase 1 specs.

**Dependencies:** Steps 1-5

**Files:** All changed files

**Approach:**
- Run `/ce:review` on the full diff
- Verify all 5 spec files are satisfied:
  - `openspec/changes/phase1-hermes-plugins/specs/zeus-plugin/spec.md`
  - `openspec/changes/phase1-hermes-plugins/specs/supervisor-plugin/spec.md`
  - `openspec/changes/phase1-hermes-plugins/specs/revolt-plugin/spec.md`
  - `openspec/changes/phase1-hermes-plugins/specs/dashboard-plugin/spec.md`
  - `openspec/changes/phase1-hermes-plugins/specs/share-knowledge-plugin/spec.md`
- Verify `tasks.md` completion
- If clean, archive the change

**Verification:**
- /ce:review verdict is "Ready to merge" or "Ready with fixes" (no P0/P1 findings)
- All spec requirements are met
- All tasks in tasks.md are complete

## System-Wide Impact

- **Interaction graph:** Dashboard plugin routes now go through Hermes dashboard middleware instead of custom auth. WebSocket clients must use `?token=` query param instead of session cookies.
- **Error propagation:** Plugin errors are now logged through Hermes dashboard's logging system, not standalone aiohttp logging.
- **API surface parity:** All REST endpoint paths change from `/api/*` to `/api/plugins/olympus/*`. Any external consumers (the React frontend) must update their base URL.
- **Unchanged invariants:** SQLite database schema, data access patterns, and seed data remain unchanged. The share_knowledge tool interface remains unchanged.

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| GraphQL parser has subtle bugs in port | Low | Low | Port the existing `_execute_query` function verbatim; add test for multi-field query |
| Plugin not discovered by Hermes dashboard | Low | High | Verify symlink is correct; test with `hermes dashboard` startup |
| WebSocket auth pattern differs from client expectations | Low | Medium | Follow kanban's established pattern exactly (`?token=` query param) |
| Existing React frontend breaks due to URL changes | High | Medium | Frontend is not in current codebase; update when frontend is rebuilt |
| Dashboard plugin API blocked for project plugins | Medium | High | Install to `~/.hermes/plugins/` (not project plugins); symlink for dev |

## Rollback Plan

If the dashboard migration causes issues:
1. Revert the commit that removes `plugins/dashboard/` and adds `plugins/olympus-dashboard/`
2. The old aiohttp dashboard can be restored immediately (it's a separate process, no data loss)
3. Plugin fixes (Steps 1-4) are independent and can be kept even if dashboard migration is reverted

## Sources & References

- **Origin spec:** `openspec/changes/phase1-hermes-plugins/specs/dashboard-plugin/spec.md`
- **Reference plugin:** `~/.hermes/hermes-agent/plugins/kanban/dashboard/` (full Hermes dashboard plugin example)
- **Dashboard web server:** `~/.hermes/hermes-agent/hermes_cli/web_server.py` (plugin discovery and mounting)
- **Phase 1 review findings:** `.context/compound-engineering/ce-review/20260524-165538-53bf1476/report.md`
