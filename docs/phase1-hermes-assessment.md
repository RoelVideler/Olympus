# Phase 1: Hermes Capability Assessment

## Date: 2026-05-24
## Hermes Agent version: 0.14.0 (2026.5.16)

## Question: Does Hermes Agent's gateway handle multi-profile management natively?

### Checklist

- [x] Can Hermes manage multiple profiles from a single gateway process?
- [x] Does Hermes have built-in health monitoring for profiles?
- [x] Does Hermes support profile lifecycle management (start/stop/idle TTL)?
- [x] Does Hermes have a scheduling system that can coordinate cross-profile cron jobs?
- [x] Does Hermes expose a programmatic API for profile management?

### Findings

#### 1. Multi-profile gateway management: NO

The Hermes gateway (`hermes gateway`) is a **messaging platform integration service** — it manages connections to Telegram, Discord, WhatsApp, and Signal. It is NOT a multi-profile orchestrator.

- Each profile runs its **own independent gateway process** with its own PID file (`gateway.pid`) and service unit (e.g., `hermes-gateway-zeus.service`, `hermes-gateway-chronos.service`).
- The gateway has no awareness of other profiles. It cannot start, stop, or manage profiles other than its own.
- Source: `hermes_cli/gateway.py` — the gateway handles systemd/launchd service installation, PID management, and messaging platform connections. No cross-profile logic exists.

#### 2. Health monitoring for profiles: NO

Hermes has **PID-file-based process tracking** for its own gateway, but no health monitoring system across profiles.

- `gateway.status.get_running_pid()` reads a PID file and checks if the process is alive.
- `hermes status` shows environment, API keys, and component status for the **current profile only**.
- There is no health check endpoint that aggregates status across multiple profiles.
- There is no mechanism to detect if a profile's agent process is healthy, unresponsive, or crashed.

#### 3. Profile lifecycle management (start/stop/idle TTL): NO

Profiles are **static directories** with CLI entry points. There is no lifecycle manager.

- Profiles are started via CLI: `hermes -p <name> chat` or `hermes -p <name> gateway start`.
- Profiles are stopped manually: `hermes gateway stop` (stops only that profile's gateway).
- **No idle TTL**: There is no mechanism to automatically stop a profile after a period of inactivity.
- **No on-demand startup**: There is no mechanism to automatically start a profile when a request arrives.
- Profile creation/deletion is purely filesystem operations (`hermes profile create/delete`).
- Source: `hermes_cli/profiles.py` — CRUD operations on profile directories, wrapper scripts, and service units. No lifecycle management.

#### 4. Cross-profile cron coordination: NO

Hermes cron is **per-profile**, stored in each profile's `cron/` directory as `jobs.json`.

- `hermes cron create` creates jobs scoped to the current profile.
- The cron scheduler runs as part of the gateway service for that profile.
- There is **no cross-profile job coordination**. Profile A's cron cannot trigger Profile B's jobs.
- There is **no dependency graph** or ordering system across profiles.
- Source: `hermes_cli/cron.py` — jobs are stored and executed per-profile. No cross-profile references.

#### 5. Programmatic API for profile management: PARTIAL

Hermes exposes a **CLI** for profile management but no programmatic API for lifecycle operations.

- Available: `hermes profile create/delete/list/rename/export/import` — filesystem CRUD.
- Available: `hermes -p <name> <command>` — run commands against a specific profile.
- Available: `hermes mcp serve` — expose a profile as an MCP server (other agents can connect).
- Available: `hermes acp` — run a profile as an ACP server (editor integration).
- **Missing**: No API to start/stop profiles programmatically based on demand.
- **Missing**: No API to query profile health or process status programmatically.
- **Missing**: No API to set or enforce idle TTL.

### Decision

- [x] **Supervisor needed**: Hermes does not handle multi-profile management natively. Build Olympus Supervisor in Phase 2.
- [ ] **Supervisor not needed**: Hermes handles all lifecycle management. Drop Supervisor from the architecture.

### Rationale

Hermes Agent provides excellent **profile isolation** — each profile is a fully independent HERMES_HOME with its own config, memory, tools, sessions, gateway, and cron. This is exactly what Olympus needs for agent isolation.

However, Hermes has **no orchestration layer** above profiles. Specifically:

1. **No on-demand lifecycle**: Olympus requires `on-demand` profiles (Iaso, Hermes, Philia, Plutus, Hephaestus, Metis, Apollo, Midas) that start on first request and stop after idle TTL. Hermes has no mechanism for this — profiles must be started manually or via their own always-on gateway service.

2. **No cross-profile coordination**: The morning briefing (Zeus, 07:00) depends on Iaso's health sync and Hermes' email triage completing first. Hermes cron is per-profile with no dependency graph. Chronos cannot coordinate cross-profile job ordering natively.

3. **No health monitoring**: If a profile crashes, Hermes has no mechanism to detect and restart it. The gateway PID file only tracks the messaging service, not the agent process itself.

4. **No programmatic lifecycle API**: Zeus (the orchestrator) needs to start/stop profiles based on incoming requests. Hermes provides CLI commands but no API that Zeus can call programmatically.

The Olympus Supervisor should be a **simple Python script** (as planned in the architecture doc) that:
- Starts profiles based on `run_mode` (always-on, on-demand, cron-only)
- Monitors profile health (process liveness, not just gateway PID)
- Kills idle on-demand profiles after configurable timeout
- Restarts crashed profiles
- Exposes a simple API that Zeus can call to request profile lifecycle operations

This aligns with the architecture doc's Phase 2 plan: "a simple Python script (not a REST API service)" that manages profile processes without depending on Hermes internals.

**Note on kanban (v0.14.0):** Hermes v0.14.0 now includes `hermes kanban` — a durable task board shared across profiles. Tasks are claimed atomically and executed by a named profile in an isolated workspace. This provides a useful task dispatch mechanism but does NOT replace the Supervisor: kanban manages tasks, not processes. The Supervisor is still needed for on-demand profile start/stop, idle TTL, crash recovery, and health monitoring.
