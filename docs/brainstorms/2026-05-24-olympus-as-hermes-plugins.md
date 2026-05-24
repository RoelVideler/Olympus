# Olympus as Hermes Plugins — Requirements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot Olympus from a separate platform to a set of Hermes Agent plugins that extend Hermes' native capabilities with multi-agent orchestration, cross-agent knowledge sharing, and process lifecycle management.

**Architecture:** Olympus becomes a collection of Hermes plugins installed into the Hermes runtime. Zeus is a Hermes profile with custom skills for routing and chip-in coordination. The Supervisor becomes a Hermes gateway extension. Cross-agent knowledge remains a shared SQLite database accessed by the share_knowledge plugin.

**Tech Stack:** Hermes Agent v0.14.0+, Python 3.11+, SQLite, Hermes plugin API

---

## Context

Olympus Phase 1 was built as a separate platform on top of Hermes Agent. After auditing Phase 1 against Hermes v0.14.0, we discovered that Hermes already provides most of the infrastructure we were building separately: kanban for cross-profile task dispatch, MCP for communication, cron for scheduling, gateway for messaging platforms, and plugins for custom tools.

The decision: build Olympus as Hermes plugins rather than a separate platform. This leverages Hermes' architecture while maintaining independence.

## Requirements

### R1: Zeus as Hermes Profile with Custom Skills

Zeus is no longer a custom orchestrator — it's a Hermes profile with custom skills for:
- **Routing**: Incoming messages are classified and routed to the appropriate specialist profile
- **Chip-in coordination**: Zeus listens for chip-ins from specialist profiles and coordinates responses
- **Conversation management**: Zeus maintains conversation context and tone

**Acceptance criteria:**
- Zeus runs as a Hermes profile (`hermes -p zeus`)
- Zeus has custom skills for routing and chip-in coordination
- Zeus can communicate with other profiles via Hermes' native mechanisms (kanban, MCP, or direct CLI)

### R2: Supervisor as Hermes Gateway Extension

The Supervisor is no longer a custom process manager — it becomes a Hermes gateway extension that:
- Starts profiles based on `run_mode` configuration
- Monitors profile health
- Kills idle on-demand profiles after configurable timeout
- Restarts crashed profiles

**Acceptance criteria:**
- Supervisor runs as part of Hermes gateway or as a Hermes plugin
- Supervisor reads `run_mode` from profile configs
- Supervisor exposes an API that Zeus can call for profile lifecycle operations

### R3: Cross-Agent Knowledge as Plugin

The share_knowledge plugin already exists and works. No changes needed beyond ensuring it's compatible with the plugin approach.

**Acceptance criteria:**
- share_knowledge plugin loads in Hermes v0.14.0
- Scope enforcement works correctly
- All profiles can access shared knowledge within their authorized scopes

### R4: Revolt as Hermes Gateway Adapter

Revolt integration becomes a Hermes gateway platform adapter, not a custom service.

**Acceptance criteria:**
- Revolt adapter loads as a Hermes gateway platform
- Messages flow from Revolt to Zeus profile
- Zeus responses flow back to Revolt

### R5: Profile Configs Remain Unchanged

Profile configs (`profiles/*/config.yaml`) remain as Hermes profile configurations. The `run_mode` field is read by the Supervisor extension.

**Acceptance criteria:**
- All 10 profile configs load correctly in Hermes
- `run_mode` field is recognized by Supervisor extension
- Tool configurations work correctly

## Non-Goals

- Contributing to Hermes upstream — we maintain independence
- Replacing Hermes' native features — we extend them
- Building a custom LLM router — Hermes' provider resolution handles this

## Success Criteria

- All Olympus functionality works as Hermes plugins
- No custom platform code outside of plugins
- Phase 1 tests still pass
- Architecture spec updated to reflect plugin approach

## Dependencies

- Hermes Agent v0.14.0+ with plugin API
- Understanding of Hermes gateway extension API
- Understanding of Hermes skills system

## Open Questions

- Does Hermes' gateway extension API support process lifecycle management?
- Can Zeus's routing skills use Hermes' kanban for task dispatch to other profiles?
- What's the best communication mechanism between profiles: kanban, MCP, or direct CLI?
