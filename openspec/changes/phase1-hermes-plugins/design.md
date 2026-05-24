## Context

Olympus Phase 1 was implemented as a separate platform with custom infrastructure (Express gateway, Supervisor process manager, custom ACP/MCP adapters). After auditing against Hermes Agent v0.14.0, we discovered that Hermes already provides the primitives we were building separately: kanban for cross-profile task dispatch, MCP for communication, cron for scheduling, gateway for messaging platforms, and plugins for custom tools.

The existing Phase 1 code (profiles, SQLite schema, share_knowledge plugin) is functional and compatible with v0.14.0. The pivot changes the implementation approach, not the requirements.

## Goals / Non-Goals

**Goals:**
- All Olympus functionality works as Hermes plugins installed into the Hermes runtime
- No custom platform code outside of plugins — Express gateway and Supervisor process are eliminated
- Zeus runs as a Hermes profile with custom skills for routing and chip-in coordination
- Supervisor runs as a Hermes gateway extension for profile lifecycle management
- Phase 1 tests still pass (19/19 non-boot tests)
- Architecture spec updated to reflect plugin approach

**Non-Goals:**
- Contributing to Hermes upstream — we maintain independence
- Replacing Hermes' native features — we extend them
- Building a custom LLM router — Hermes' provider resolution handles this
- Changing profile configs or SQLite schema — these remain unchanged

## Decisions

### Decision 1: Zeus as Hermes profile with custom skills

Zeus is a Hermes profile (`hermes -p zeus`) with custom skills for routing and chip-in coordination. The skills are registered via the Hermes plugin API and activated when the Zeus profile loads.

**Why:** This leverages Hermes' native profile isolation and skill system. Zeus gets the same memory, session, and tool infrastructure as other profiles.

**Alternatives considered:**
- Custom orchestrator process (original approach) — fights the framework, duplicates Hermes' isolation
- Hermes gateway extension — gateway is for messaging platforms, not orchestration logic

### Decision 2: Supervisor as Hermes gateway extension

The Supervisor extends Hermes' gateway with profile lifecycle management. It reads `run_mode` from profile configs and manages profile processes (start/stop/health-check/idle TTL).

**Why:** The gateway already manages per-profile services (messaging platform connections, cron jobs). Extending it for lifecycle management keeps all process management in one place.

**Alternatives considered:**
- Separate Python process (original approach) — requires custom IPC, duplicates gateway's process management
- Hermes built-in lifecycle — Hermes doesn't have native on-demand profile lifecycle

### Decision 3: Cross-profile communication via Hermes kanban

Zeus dispatches tasks to specialist profiles using Hermes' kanban system. Profiles claim tasks atomically and execute in isolated workspaces.

**Why:** Kanban is Hermes' native cross-profile task dispatch mechanism. It provides atomic task claiming, dependency tracking, and isolated execution — exactly what Zeus needs for routing.

**Alternatives considered:**
- Custom ACP/MCP adapters (original approach) — duplicates Hermes' native communication
- Direct CLI calls (`hermes -p <name> -z <prompt>`) — no task tracking, no atomic claiming
- Shared database polling — race conditions, no atomic claiming

### Decision 4: Revolt and Dashboard as gateway platform adapters

Revolt messaging and Dashboard REST/GraphQL/WebSocket are implemented as Hermes gateway platform adapters, not separate services.

**Why:** Hermes gateway is designed for platform adapters (Telegram, Discord, WhatsApp). Revolt and Dashboard fit this pattern naturally.

**Alternatives considered:**
- Express proxy (original approach) — duplicates gateway's platform adapter system
- Separate Revolt bot service — requires custom message routing to Zeus

### Decision 5: share_knowledge plugin unchanged

The share_knowledge plugin already works as a Hermes plugin with scope enforcement. No changes needed.

**Why:** It already follows the plugin approach. The scope enforcement fixes from the audit are already applied.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Hermes plugin API changes between versions | Pin Hermes version, test plugin compatibility on each Hermes update |
| Kanban may not support real-time chip-in coordination | Fallback to MCP tool calls for time-sensitive chip-ins |
| Gateway extension API may not support process lifecycle | Build Supervisor as a separate plugin that monitors gateway PID files |
| Plugin complexity — 5 plugins to maintain | Each plugin has a single responsibility, well-defined interface |
| Hermes v0.14.0 may have undocumented plugin limitations | Phase 1 includes plugin loading verification for all 5 plugins |
