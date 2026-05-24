# Phase 2: Zeus Online — Setup & Profile Configuration

## Overview

Phase 2 bridges the gap between Phase 1's complete code and a running system. All plugin code and profile configs exist but have never been installed into a live Hermes runtime. This phase adds a setup script and enriches all 10 profile configurations with system prompts and idle TTL values.

## Problem Frame

Phase 1 delivered:
- 5 plugins (zeus, supervisor, revolt, olympus-dashboard, share_knowledge)
- 10 profile configs (minimal: model, run_mode, toolsets)
- SQLite schema
- Tests

What's missing to run:
- No setup/bootstrap script — manual commands needed for every step
- Zeus system prompt doesn't reference `routing` or `chip_in` tools
- 9 specialist profiles have no system prompts — they don't know their role
- No `idle_ttl` on on-demand profiles — supervisor can't enforce idle shutdown

## Requirements Trace

From architecture doc phased rollout (Phase 2: Zeus Online):
- [x] Zeus profile online with skills (routing, chip-in coordination) — addressed by system prompt + tool references
- [x] Supervisor plugin manages profile lifecycle — addressed by idle_ttl + always-on auto-start
- [x] Zeus answers questions directly without delegation — addressed by system prompt
- [ ] Dashboard works end-to-end through Zeus — **deferred to Phase 2.5** (requires Hermes dashboard to be running with plugin routes mounted; setup script only installs plugins, does not start dashboard)

## Architecture

### Setup Script (`scripts/setup.py`)

Single idempotent bootstrap script. Four phases, sequential:

**Phase 1: Database Init**
- Read `schema/001_initial.sql`
- Execute against `~/.hermes/olympus.db`
- Creates: `olympus_knowledge`, `olympus_knowledge_fts`, `agent_profiles` tables + FTS triggers
- Seed `agent_profiles` table with all 10 profiles (name, hermes_profile, run_mode, model_provider, model_name, status='stopped')
- Safe to re-run (all `CREATE TABLE IF NOT EXISTS`, `INSERT OR REPLACE` for seed data)

**Phase 2: Profile Creation**
- For each profile directory in `profiles/`:
  - Check if profile exists via `hermes profile list`
  - If not exists, try `hermes profile create <name> --config profiles/<name>/config.yaml`
  - If `--config` flag not supported, fall back to: copy config to `~/.hermes/<name>/config.yaml` then `hermes profile create <name>`
  - If profile already exists, skip with info message
- Profiles created: zeus, chronos, iaso, hermes-agent, philia, plutus, hephaestus, metis, apollo, midas

**Phase 3: Plugin Installation**
- For each plugin in `plugins/`:
  - If `~/.hermes/plugins/<name>/` already exists (e.g., symlink from dev setup), skip
  - Otherwise, copy `plugins/<name>/` to `~/.hermes/plugins/<name>/`
- Plugins installed: zeus, supervisor, revolt, olympus-dashboard (symlink preserved), share_knowledge

**Phase 4: Verification**
- Run `hermes plugins list` — confirm all 5 plugins show as enabled
- Run `hermes profile list` — confirm all 10 profiles exist
- Report any missing items as warnings (not fatal — user may need to install Hermes first)

**Error handling:**
- Fails fast on first error with clear message
- Each phase reports progress (e.g., "Phase 1/4: Database init — done")
- Exit code 0 on success, 1 on failure
- No interactive prompts

### Profile Config Updates

All 10 `profiles/<name>/config.yaml` files updated with:

**1. `idle_ttl` (on-demand profiles only)**
- 300s (5 min): iaso, hermes-agent, philia, plutus, metis, apollo, midas
- 600s (10 min): chronos, hephaestus (recurring jobs, benefit from staying warm)
- zeus: no idle_ttl (always-on)

**2. `system_prompt` (all profiles)**

Each profile gets a domain-specific system prompt following this pattern:

```yaml
system_prompt: |
  You are <Name>, the <role> for Olympus — a personal AI life assistant.

  Your domain: <specific expertise areas>.

  Tools available:
  - share_knowledge: Read/write cross-agent facts. Write scope: <write_scopes>. Read scope: <read_scopes>.
  - <other toolsets>

  When you learn something other agents might need, call share_knowledge(action="write", scope="<scope>", domain="<domain>", fact="...").

  Tone: <profile-specific tone>.
```

Actual scope values per profile (filled into each prompt):
- zeus: Write: global, personal, business. Read: global, personal, business.
- chronos: Write: global, personal. Read: global, personal.
- iaso: Write: personal. Read: global, personal.
- hermes-agent: Write: global, personal. Read: global, personal.
- philia: Write: personal. Read: global, personal.
- plutus: Write: personal. Read: global, personal.
- hephaestus: Write: personal. Read: global, personal.
- metis: Write: global, business. Read: global, business.
- apollo: Write: business. Read: global, business.
- midas: Write: business. Read: global, business.

**Zeus system prompt update:**
The existing Zeus prompt is updated to explicitly reference the `routing` and `chip_in` tools:

```yaml
system_prompt: |
  You are Zeus, the front-door orchestrator for Olympus — a personal AI life assistant.

  Your role:
  1. Receive user messages and respond immediately with your own answer.
  2. After responding, use the chip_in tool to poll specialist profiles in parallel for relevant chip-ins.
  3. Stream relevant chip-ins to the user as they arrive.
  4. Handle unknown queries directly without delegation.
  5. Use the routing tool to detect query domain and route to specialist profiles.

  Tools:
  - chip_in: Poll all specialist profiles for relevance scores and insights.
  - routing: Detect query domain and get specialist responses.
  - share_knowledge: Read/write cross-agent facts (scope: global, personal, business).
  - supervisor: Start/stop/check profiles.

  Specialist profiles:
  - Chronos: scheduling, calendar, energy-aware planning
  - Iaso: health, fitness, nutrition, sleep
  - Philia: relationships, social, family, dating
  - Plutus: investments, stocks, portfolio, crypto
  - Hephaestus: home, maintenance, repair, appliances
  - Metis: business, strategy, startup, marketing
  - Apollo: creative, writing, art, music, design
  - Midas: finance, budgeting, expenses, saving, spending

  Tone: Direct, helpful, concise. No filler. No "I'd be happy to help."
  When you don't know something, say so plainly and move on.
```

**Scope assignments per profile:**

Scope enforcement is handled by `plugins/share_knowledge/__init__.py` via `scopes.json`. The system prompt references the allowed scopes as documentation for the agent. Values below match the existing `_default_scopes()` in the plugin code:

| Profile | Write scopes | Read scopes |
|---------|-------------|-------------|
| zeus | global, personal, business | global, personal, business |
| chronos | global, personal | global, personal |
| iaso | personal | global, personal |
| hermes-agent | global, personal | global, personal |
| philia | personal | global, personal |
| plutus | personal | global, personal |
| hephaestus | personal | global, personal |
| metis | global, business | global, business |
| apollo | business | global, business |
| midas | business | global, business |

**Sensitive data constraints:**
- iaso: "Handle health data with care. Do not share sensitive health facts outside your domain."
- plutus: "Handle investment and portfolio data with care. Do not share sensitive financial facts outside your domain."
- midas: "Handle business finance data with care. Do not share sensitive financial facts outside your domain."

## Output Structure

```
Olympus repo:
scripts/
└── setup.py              # Bootstrap script (new)

profiles/
├── zeus/config.yaml      # Updated: system_prompt references tools
├── chronos/config.yaml   # Updated: system_prompt, idle_ttl
├── iaso/config.yaml      # Updated: system_prompt, idle_ttl
├── hermes-agent/config.yaml  # Updated: system_prompt, idle_ttl
├── philia/config.yaml    # Updated: system_prompt, idle_ttl
├── plutus/config.yaml    # Updated: system_prompt, idle_ttl
├── hephaestus/config.yaml # Updated: system_prompt, idle_ttl
├── metis/config.yaml     # Updated: system_prompt, idle_ttl
├── apollo/config.yaml    # Updated: system_prompt, idle_ttl
└── midas/config.yaml     # Updated: system_prompt, idle_ttl
```

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hermes CLI version mismatch | Low | Medium | Script checks `hermes --version` first, warns if < 0.14.0 |
| Profile create fails (different CLI syntax) | Medium | High | Script catches error, shows manual fallback command |
| System prompts too long | Low | Low | Hermes has no documented prompt length limit; keep under 2000 chars |
| idle_ttl too short/long | Low | Low | Tunable — user can edit config.yaml after setup |

## Rollback Plan

Profile configs are version-controlled. To rollback:
1. `git checkout main -- profiles/` — restore original configs
2. `hermes profile delete <name>` for each profile, then re-create
3. Setup script is safe to re-run after rollback
