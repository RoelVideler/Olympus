## Why

Olympus Phase 1 was built as a separate platform on top of Hermes Agent, creating custom infrastructure (Express gateway, Supervisor process manager) that duplicates Hermes' native capabilities. After auditing against Hermes v0.14.0, we discovered Hermes already provides kanban for cross-profile task dispatch, MCP for communication, cron for scheduling, gateway for messaging platforms, and plugins for custom tools. Building a separate platform fights the framework rather than extending it.

## What Changes

- **Olympus becomes Hermes plugins** instead of a separate platform — Zeus, Supervisor, Revolt, Dashboard, and share_knowledge are installed as Hermes plugins
- **Zeus becomes a Hermes profile** with custom skills for routing and chip-in coordination, not a standalone orchestrator process
- **Supervisor becomes a Hermes gateway extension** that manages profile lifecycle, not a separate Python process
- **Gateway becomes Hermes native** — Revolt and Dashboard are Hermes gateway platform adapters, not Express proxies
- **Cross-profile communication uses Hermes kanban** for task dispatch instead of custom ACP/MCP adapters
- **File structure changes** from `tools/`, `supervisor/`, `gateway/` to `plugins/zeus/`, `plugins/supervisor/`, `plugins/revolt/`, `plugins/dashboard/`

## Capabilities

### New Capabilities

- `zeus-plugin`: Zeus orchestrator as Hermes profile with custom skills for routing, chip-in coordination, and conversation management
- `supervisor-plugin`: Profile lifecycle management as Hermes gateway extension — starts/stops profiles based on run_mode, monitors health, handles idle TTL
- `revolt-plugin`: Revolt messaging platform adapter for Hermes gateway — messages flow from Revolt to Zeus profile
- `dashboard-plugin`: Dashboard REST/GraphQL/WebSocket plugin for Hermes gateway — serves existing React dashboard data APIs
- `share-knowledge-plugin`: Cross-agent knowledge sharing via shared SQLite with scope enforcement (already exists, no changes needed)

### Modified Capabilities

- (none — this is a new project with no existing specs)

## Impact

- **Phase 1 implementation approach** — all Phase 1 tasks need to be re-implemented as Hermes plugins
- **Architecture spec** — updated to reflect plugin architecture instead of separate platform
- **Profile configs** — remain unchanged (standard Hermes YAML)
- **SQLite schema** — remains unchanged (shared knowledge database)
- **Tests** — need to verify plugins load correctly in Hermes runtime
