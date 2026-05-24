# Olympus Architecture Design

## Overview

Olympus is a personal AI life assistant — the successor to TheTemple. Built as a **collection of Hermes Agent plugins**, Olympus extends Hermes' native capabilities with multi-agent orchestration, cross-agent knowledge sharing, and process lifecycle management.

Each Olympus "god" runs as a **Hermes Agent profile** (`hermes -p <profile>`), giving full isolation of config, memory, tools, and session storage. Olympus plugins extend Hermes with:
- **Zeus plugin**: Routing, chip-in coordination, and conversation management (runs as a Hermes profile with custom skills)
- **share_knowledge plugin**: Cross-agent knowledge sharing via shared SQLite with scope enforcement
- **Supervisor plugin**: Process lifecycle management (starts/stops profiles based on `run_mode`)
- **Revolt plugin**: Revolt messaging platform adapter for Hermes gateway

This approach leverages Hermes' existing architecture (kanban for task dispatch, MCP for communication, cron for scheduling, gateway for messaging) rather than building a separate platform on top.

## Problem Statement

TheTemple's custom agent infrastructure was built from scratch on a weak foundation. Every incremental change was painful and buggy. The multi-agent system (chip-in, delegation, coordination) never worked properly despite a sound concept — partly because agents lack proper onboarding and don't know the user or their needs. Building and maintaining a custom LLM router, provider resolution, tool registry, memory broker, and scheduler diverted effort from what matters: agent behavior and domain logic. Hermes Agent has mature features (self-evolution, provider failover, MCP, agent loop) that TheTemple will never catch up to.

Olympus adopts Hermes Agent as the runtime to eliminate infrastructure debt and focus on what makes the multi-agent system valuable: agents that know the user, coordinate effectively, and deliver domain expertise.

### Design Constraint: Hermes-Native with Escape Hatch

Olympus is built as Hermes plugins — we extend Hermes' architecture, not replace it. However, the architecture should maintain modularity at integration boundaries (gateway → Zeus, Zeus → profiles, tools → external APIs) so that moving away from Hermes Agent is feasible if needed. This means:
- Plugins communicate via Hermes' native mechanisms (kanban, MCP, CLI), not custom protocols
- Domain tools expose clean interfaces that could be reimplemented in another runtime
- Profile configs are standard Hermes YAML, not custom format

## Principles

- **Hermes-native**: Adopt Hermes Agent's runtime, tool system, memory, and deployment model. Do not wrap or replace them.
- **Profile isolation**: Each agent is an independent Hermes profile with its own config, memory, skills, and session store.
- **Intentional sharing**: Cross-agent knowledge flows through an explicit `share_knowledge` tool, not implicit sync. Keeps agent reasoning debuggable.
- **Tiered by need**: Always-on for critical agents (Zeus, Chronos). On-demand for domain specialists. Configured per profile via a `run_mode` property.
- **Fresh start**: Olympus is a clean project. TheTemple's concepts carry forward; its custom agent code does not.

## Agent Roster

### Personal Cluster (Zeus-orchestrated)

| Agent | Role | Run Mode | Model Tier |
|---|---|---|---|
| Zeus | Front-door orchestrator — routing, workflow, tone, chip-in coordination | always-on | interactive (local, e.g. Qwen3.6 35B A3B) |
| Chronos | Scheduling, calendar, energy-aware planning | always-on | background (local, smaller) |
| Iaso | Health, symptoms, vitals, Withings sync | on-demand | sensitive (local only) |
| Hermes | Messenger — email triage, WhatsApp, contact forms | on-demand | triage (local, fast) |
| Philia | Relationships, social obligations | on-demand | background (local, smaller) |
| Plutus | Personal investments, portfolio | on-demand | sensitive (local only) |
| Hephaestus | Home automation, devices, maintenance | on-demand | background (local, smaller) |

### Business Cluster (Zeus-routed, on-demand)

| Agent | Role | Run Mode | Model Tier |
|---|---|---|---|
| Metis | Business domain expert — markets, practices, development strategy | on-demand | interactive (local) |
| Apollo | Creative — photography, art, events | on-demand | background (local, smaller) |
| Midas | Finance — invoicing, expenses, budget | on-demand | sensitive (local only) |

## Architecture

```
User (Dashboard / CLI / Revolt)
        │
        ▼
┌─────────────────────────────────────────────┐
│  Hermes Gateway                             │
│  - Revolt plugin (messaging platform)       │
│  - Dashboard plugin (REST/GraphQL/WebSocket)│
│  - Supervisor plugin (profile lifecycle)    │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│              Zeus (always-on profile)            │
│  Hermes profile + Zeus plugin skills             │
│  - Receives all user messages                    │
│  - Top-down: routes known-domain queries to profiles │
│  - Listens for chip-ins from agents with relevant domain knowledge │
│  - Coordinates chip-in responses, resolves conflicts, summarizes │
│  - Uses Hermes kanban for task dispatch to profiles │
└────┬──────┬──────┬──────┬──────┬──────┬──────┬───┘
     │      │      │      │      │      │      │
     ▼      ▼      ▼      ▼      ▼      ▼      ▼
   Chron  Iaso  Hermes Philia Plutus Heph   Metis  Apollo  Midas
    (on-demand profiles, started/stopped by Supervisor plugin)
                                                        │
                                     Business cluster — Zeus routes directly
                                     to all 3 as peers (no sub-orchestrator)
```

Olympus is a set of Hermes plugins installed into the Hermes runtime. Zeus is a Hermes profile with custom skills for routing and chip-in coordination. The Supervisor is a Hermes gateway extension that manages profile lifecycle. Cross-agent knowledge flows through the share_knowledge plugin accessing a shared SQLite database.

## Deployment Model

### Run Modes

Each profile has a `run_mode` property controlling lifecycle:

| Mode | Behavior | Use Case |
|---|---|---|
| `always-on` | Process starts with Olympus, stays resident. Memory stays hot. | Zeus, Chronos |
| `on-demand` | Process starts on first request, stays alive for idle TTL, then stops. Chip-in adds minimal latency (first request only). | Iaso, Hermes, Philia, etc. |
| `cron-only` | Only starts when a cron job fires. Never responds to interactive requests. | Data sync, nightly reports |

### Process Management

The **Olympus Supervisor plugin** extends Hermes' gateway with profile lifecycle management:

- Starts profiles based on `run_mode` configuration
- Monitors profile health (process liveness, not just gateway PID)
- Kills idle on-demand profiles after configurable timeout
- Restarts crashed profiles
- Exposes an API that Zeus can call for profile lifecycle operations

Implementation: A Hermes gateway extension that reads `run_mode` from profile configs and manages profile processes. Runs as part of the Hermes gateway process, not a separate service.

## Memory Architecture

### Per-Profile (Hermes Native, SQLite + FTS5)

Each profile maintains its own:
- **Session storage**: `hermes_state.sqlite` — conversation history with full-text search
- **Memory files**: `MEMORY.md`, `USER.md` — cross-session facts
- **Skills**: `~/.hermes/<profile>/skills/` — auto-generated procedural skills from Hermes' self-evolution loop

This stays entirely native. No modifications to Hermes' memory system.

### Cross-Agent Knowledge (SQLite + FTS5)

A shared SQLite database stores cross-agent knowledge that multiple agents need:

```sql
-- Shared facts that any agent can read/write
CREATE TABLE olympus_knowledge (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,        -- 'personal', 'business', 'global'
    domain TEXT NOT NULL,        -- 'health', 'finance', 'schedule', 'contact', ...
    fact TEXT NOT NULL,          -- The knowledge statement
    confidence REAL DEFAULT 1.0,
    source_profile TEXT NOT NULL,-- Which agent wrote this
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Full-text search index
CREATE VIRTUAL TABLE olympus_knowledge_fts USING fts5(
    fact, domain, scope,
    content='olympus_knowledge',
    content_rowid='rowid'
);

-- Agent registry (models, run modes, status)
CREATE TABLE agent_profiles (
    name TEXT PRIMARY KEY,       -- 'zeus', 'chronos', etc.
    hermes_profile TEXT NOT NULL,-- Maps to Hermes profile name
    run_mode TEXT NOT NULL DEFAULT 'on-demand',
    model_provider TEXT,
    model_name TEXT,
    status TEXT DEFAULT 'stopped'
);
```

SQLite is used for cross-agent knowledge because: (a) it's single-user, so concurrency is not a concern, (b) FTS5 provides full-text search across facts, (c) no separate database process needed. If semantic/vector search becomes a demonstrated need, migrate to PostgreSQL with pgvector.

Agents access this via a `share_knowledge` Hermes tool — an intentional action, not automatic sync:

```python
def share_knowledge(
    action: Literal["write", "query", "delete"],
    scope: Literal["personal", "business", "global"],
    domain: str,
    fact: str | None = None,        # required for write
    confidence: float = 1.0,        # optional, defaults to 1.0
    limit: int = 10                 # optional, for query
) -> dict:
    """Write, query, or delete cross-agent knowledge facts.
    
    Scope access is enforced in application logic: each agent's tool config
    specifies which scopes it can read and write.
    """
```

```
zeus: "Client X prefers morning calls"
    → calls share_knowledge(action="write", scope="business", domain="preference", fact="...")
metis: (later) "What does client X prefer?"
    → calls share_knowledge(action="query", scope="business", domain="preference")
    → gets the fact back
```

**Security**: The `share_knowledge` tool enforces scope filtering in application logic (no RLS needed for single-user). Each agent's tool config specifies which scopes it can read and write (e.g., Iaso can write `health` and read `global`, but cannot write `finance`). This prevents a compromised profile from reading or corrupting cross-domain knowledge.

## Tool System

### Hermes-Native Tools (automatic)

Each profile gets Hermes' built-in toolset: web search, file operations, terminal, browser, etc. These are managed by Hermes' auto-discovered `tools/*.py` registry.

### Olympus Domain Tools (Hermes custom tool plugins)

Domain-specific tools are registered through Hermes' **plugin system** (not built-in tools). Each plugin is a Python package that self-registers via `registry.register()`:

| Tool | Agents | Integration |
|---|---|---|
| `home_assistant` | Hephaestus | Home Assistant REST API |
| `withings_sync` | Iaso | Withings health API |
| `gmail_triage` | Hermes | Gmail MCP server (reconfigured from TheTemple as Hermes MCP plugin) |
| `whatsapp_send` | Hermes | WhatsApp API |
| `calendar_query` | Chronos, Zeus | Google Calendar MCP |
| `share_knowledge` | All | SQLite cross-agent knowledge |

Tools are scoped per profile via Hermes' built-in platform allow/block lists in `config.yaml` (`agent.tools.allow` / `agent.tools.block`) and toolset grouping — Hermes only activates a tool if it's in the profile's enabled toolset.

### MCP Integration

Hermes Agent already has a built-in MCP client (`tools/mcp_tool.py`). Existing MCP servers (Gmail) connect directly to the relevant Hermes profile's MCP configuration, no custom bridge needed.

## LLM Tiering

All agents run on local models by default. No third-party LLM providers receive user data. Each profile configures its own `provider` + `model` in `~/.hermes/<profile>/config.yaml`:

```yaml
# Example: Zeus config (interactive, local)
provider: openai-compatible
base_url: http://localhost:11434/v1
model: qwen3.6-35b-a3b
```

```yaml
# Example: Plutus config (background, local, smaller)
provider: openai-compatible
base_url: http://localhost:11434/v1
model: qwen3.6-8b
```

**Sensitivity labels**: The system tags conversations as `sensitive` when it detects health, finance, or personal data patterns. This classification is used internally and prepares the system for future cloud model integration — when cloud models are eventually used for non-sensitive queries, the sensitivity labels ensure the system already has confidence in its classification accuracy.

Model assignments are stored in the `agent_profiles` table and generated into profile configs during setup. Hermes' provider resolution handles failover and health checks natively.

## Cron & Automation

Hermes' built-in cron replaces TheTemple's `scheduler.py`. Chronos acts as the cron coordinator — it maintains a shared job schedule and triggers dependent profile jobs in the correct order:

| Job | Profile | Schedule | Coordination |
|---|---|---|---|
| Morning briefing | Zeus | 07:00 daily | Triggered by Chronos after health sync + email triage |
| Email triage | Hermes | Every 30 min | Independent |
| Health data sync | Iaso | 08:00, 20:00 daily | Independent |
| Portfolio check | Plutus | 09:30 weekdays | Independent |
| Invoice reminder | Midas | 1st of month | Independent |

Jobs are created via Hermes' `/job` slash command or configured directly in `jobs.json`.

## Gateway

The Express gateway serves as the data API for the React dashboard (~20 REST endpoints for wiki, health, calendar, contacts, preferences, facts, issues, locations, notifications, and models, plus GraphQL and WebSocket). The gateway is **not** a thin proxy — most of its endpoints remain as database-backed CRUD APIs for the dashboard.

Changes from TheTemple gateway:

1. **Strip out**: custom LLM router, agent HTTP client, multi-agent evaluation logic, sub-agent system — these lived in the Python agent service, not the gateway
2. **Replace**: `POST /api/chat/direct` → forwards to Zeus via ACP/MCP
3. **Keep**: all existing REST/GraphQL/WebSocket endpoints that serve dashboard features (health data CRUD, wiki, calendar, contacts, preferences, etc.)
4. **Add**: Health check aggregator — pings all profile health status

## Concept Handoff from TheTemple

### Carry Forward
- Domain concepts (scheduling, health, email triage, etc.)
- SQLite schema redesigned for cross-agent knowledge only
- TheTemple's Gmail MCP server (stdio transport) will be reconfigured as a Hermes Agent MCP plugin
- Agent role definitions and system prompt knowledge

### Leave Behind
- `agents/base.py`, `sub_agent.py` — replaced by Hermes `AIAgent`
- `llm/router.py`, `providers/` — replaced by Hermes provider resolution
- `tools/registry.py` — replaced by Hermes tool registry
- `memory/broker.py` — replaced by Hermes native memory + `share_knowledge` tool
- `scheduler.py` — replaced by Hermes cron
- `chat_gateway.py` — chip-in logic moves into Zeus' prompt and orchestration
- `notification_service.py`, `conflict_resolution.py` — inter-agent coordination handled by Zeus

### No Migration
This is a clean build, not a migration. TheTemple's code stays in its repo. Olympus starts with:
```
/Users/roelvideler/openspec/Olympus/
├── plugins/            # Olympus Hermes plugins
│   ├── zeus/               # Routing, chip-in coordination skills
│   ├── share_knowledge/    # Cross-agent knowledge sharing
│   ├── supervisor/         # Profile lifecycle management
│   └── revolt/             # Revolt messaging platform adapter
├── profiles/           # Hermes profile configs per agent
├── schema/             # SQLite migration files
└── docs/               # Architecture and ops docs
```

## Phased Rollout

### Phase 1: Foundation
- Install Hermes Agent, create all 10 profiles
- Build Olympus plugins: zeus, share_knowledge, supervisor, revolt
- Set up shared SQLite schema + `share_knowledge` tool
- Verify all profiles boot independently
- Verify all plugins load correctly in Hermes

**Success criteria:**
- All 10 profiles boot and respond to a basic prompt via Hermes' native interface without errors
- All 5 Olympus plugins load correctly in Hermes (`hermes plugins list` shows them as enabled): zeus, share_knowledge, supervisor, revolt, dashboard
- `share_knowledge` tool: write from one profile, read from another, verify round-trip against shared SQLite
- Supervisor plugin starts/stops profiles based on `run_mode` configuration

### Phase 2: Zeus Online
- Zeus profile online with Zeus plugin skills (routing, chip-in coordination)
- Hermes gateway forwards chat to Zeus via Revolt plugin
- Dashboard works end-to-end through Zeus
- All non-routed queries handled by Zeus directly (no delegation yet)
- Supervisor plugin manages profile lifecycle

**Success criteria:**
- Zeus answers 10 diverse, random questions directly without errors or crashes
- Dashboard chat: user types message → Hermes gateway → Zeus → response renders on screen
- Chat endpoint + 3-5 critical data endpoints return correct data (defer remaining dashboard endpoints to Phase 3+)
- Supervisor plugin starts/stops profiles correctly based on `run_mode`

### Phase 3: Specialized Profiles
- Chronos, Iaso online (always-on + on-demand)
- Zeus delegates domain queries to the right profile
- Chip-in mechanism — hybrid model (see below)
- Cron jobs on Chronos (morning briefing, calendar sync)

**Chip-in model (polling-based, streaming):**
- **Top-down dispatch**: Zeus proactively routes known-domain queries to specialist profiles (e.g., "what's my schedule?" → Chronos)
- **Polling chip-in**: Zeus responds to the user immediately with its own answer, then polls specialist profiles in parallel with lightweight model calls. Each profile evaluates relevance and returns an insight if applicable. Zeus streams relevant chip-ins to the user as they arrive — no hard timeout, all insights eventually arrive.
  - Initial response is immediate (no polling delay)
  - Chip-ins stream in as additions ("also, Chronos says your next meeting is at 3pm")
  - Polling latency target: under 2 seconds per profile, all chip-ins within 10 seconds
- **Zeus coordinates** chip-in responses (asks for details, resolves conflicts) and ultimately shares a conclusion or summary

**Success criteria:**
- 3 different delegations work (e.g., Zeus → Chronos, Zeus → Iaso, Zeus → Hermes)
- 3 polling chip-ins fire correctly (Zeus responds immediately, polls profile, streams insight as it arrives)
- At least one cron job executes autonomously and produces correct output
- Initial response latency is under 2 seconds (before any chip-ins arrive)

### Phase 4: Full Rollout
- Hermes, Philia, Plutus, Hephaestus — all on-demand
- Business agents (Metis, Apollo, Midas) — Zeus-routed on-demand as peers
- All agents respond correctly to domain-specific queries
- Router correctly directs queries to domain-specific agents (e.g., "schedule a meeting" → Chronos, "check my inbox" → Hermes)
- Drop all TheTemple dependencies

### Phase 5: Knowledge Gathering
The system is fully operational but empty — agents don't know the user. This phase populates each profile with domain-specific knowledge so they hit the ground running.

**Interactive interviews:**
- Zeus conducts structured interviews across sessions: preferences, routines, health history, relationships, business context, financial situation, home setup
- Each profile extracts domain-relevant facts from interview transcripts and stores them in `USER.md` and `MEMORY.md`
- Interviews are paced — not a single marathon session, but distributed over days/weeks

**Document ingestion:**
- Upload existing documents: calendar exports, email archives, health reports, financial statements, property records, business contracts
- Relevant profiles parse documents and extract structured facts via `share_knowledge`
- Documents are stored in profile-specific storage for reference

**Success criteria:**
- Each profile has a populated `USER.md` with at least 20 domain-relevant facts about the user
- At least 3 document types ingested and parsed successfully
- Zeus can answer personal questions correctly using ingested knowledge (e.g., "when's my next doctor appointment?", "what's my current portfolio value?")

## Security Considerations

### Credential Management
All LLM inference runs locally — no LLM provider API keys are needed. Credentials that do need secure storage: third-party service API keys (Withings, Google Calendar, Gmail, Home Assistant, WhatsApp), database credentials, and Revolt bot tokens. Options: macOS Keychain, environment variable injection, or a vault service. Documented before Phase 1 completes.

### Data Protection
SQLite database files are stored on the local filesystem. macOS FileVault provides encryption at rest. Session data retention policies (e.g., conversation history: 30 days) are enforced via application-level cleanup jobs.

### Inter-Profile Communication Security
All profiles run under one user account on localhost. Process isolation + localhost binding is sufficient for single-user. If profiles are ever containerized separately, add per-profile authentication tokens.

### Self-Evolution Security
Before enabling the self-evolution loop (Phase 4), implement a code execution sandbox: generated skills are written to a `skills/pending/` directory, reviewed by the user, then moved to `skills/active/`. Block dangerous operations in generated code (`os.system`, `subprocess`, `eval`, `exec`, network calls). Until the user trusts the pattern, all generated skills require human review before activation.

### Audit Trail
All autonomous cron actions (email triage, health sync, portfolio check, invoice reminders) log actor, action, parameters, timestamp, and result to a structured JSON file per agent. Append-only logging is sufficient for single-user traceability.

### Gateway Authentication
The dashboard is a single-user system running on localhost. Session cookie authentication is required — no "no auth" mode. Use `HttpOnly`, `SameSite=Strict` cookies with a locally-generated secret.

### Revolt Integration
Revolt (open-source, self-hostable, Discord-like UX) is the preferred chat platform. Before Phase 3: set up a self-hosted Revolt instance, implement a Hermes gateway platform adapter for Revolt, and define bot identity, channel structure, and message routing to Zeus via ACP/MCP.

### LLM Data Exposure
All agents run on local models by default — no third-party LLM providers receive health, finance, or personal data. The system labels conversations as `sensitive` when it detects health, finance, or personal data patterns, preparing for future cloud model integration. When cloud models are eventually used for non-sensitive queries, the sensitivity labels ensure the system already has confidence in its classification accuracy.

### Hermes Built-in Tools Scoping
Each profile gets Hermes' built-in toolset (web search, file operations, terminal, browser). By default, `terminal` and `browser` tools are blocked for all profiles. Enable only on a per-profile, per-need basis. For profiles handling sensitive data (Iaso, Plutus, Midas), block all filesystem-write tools. Tool scoping is configured via Hermes' `agent.tools.allow` / `agent.tools.block` in each profile's `config.yaml`.

### Hermes-Native Lock-In Mitigation
Olympus delegates heavily to Hermes Agent's runtime, tool system, memory, and deployment model. If Hermes breaks or changes its API, Olympus is impacted. Mitigation: maintain modularity at integration boundaries (gateway → Zeus via ACP/MCP, domain tools expose clean interfaces). Documented in the escape hatch design constraint.

### Supervisor Necessity
Hermes' gateway extension API may not support process lifecycle management. **Phase 1 verification**: Test if Hermes' gateway extension API can start/stop profiles, monitor health, and manage idle TTL. If yes, build Supervisor as a gateway extension plugin. If no, build Supervisor as a separate plugin that communicates with the gateway via Hermes' internal API.

### Cron Coordination
Cron jobs span multiple profiles (Zeus, Hermes, Iaso, Plutus, Midas), each with independent `jobs.json`. The morning briefing (Zeus, 07:00) may need data from Iaso's health sync and Hermes' email triage. **Design**: Chronos acts as the cron coordinator — it maintains a shared job schedule and triggers dependent profile jobs in the correct order. Independent jobs (portfolio check, invoice reminders) run without coordination.

### Third-Party Integration Failure Modes
External APIs (Gmail, Withings, Google Calendar, Home Assistant) can be down, rate-limited, or unreachable. Each domain tool must implement: retry with exponential backoff, graceful degradation (return "service unavailable" with context, not raw errors). Simple retry is sufficient — circuit breaker pattern adds state management complexity not needed for single-user.

## Open Questions

- **Zeus plugin skill design**: How much of the chip-in algorithm lives in Zeus' system prompt vs. custom Hermes skills? Must be designed before Phase 2 — it is the core architectural commitment of the multi-agent system.
- **Agent onboarding**: TheTemple's agents never worked properly partly because they lacked proper onboarding — they didn't know the user or their needs. How does each profile learn about the user? `USER.md` files? Structured onboarding flow? Must be designed before Phase 2.
- **Polling latency target**: How fast can Zeus poll a specialist profile? Target is under 2 seconds per profile so chip-ins arrive within 10 seconds of the initial response. Measured in Phase 3.
- **Hermes name collision**: The messenger agent shares its name with the Hermes Agent runtime. This will cause confusion in docs, configs, and conversation. Consider renaming the messenger agent (e.g., "Angelos" — Greek for messenger).
- **Supervisor plugin API**: Does Hermes' gateway extension API support process lifecycle management? Must be verified in Phase 1 before building the Supervisor plugin.
