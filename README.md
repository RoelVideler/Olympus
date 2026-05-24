# Olympus

Personal AI life assistant built on Nous Research's Hermes Agent.

## Architecture

Olympus runs as a set of Hermes plugins that extend the Hermes Agent runtime:

| Plugin | Purpose |
|--------|---------|
| **zeus** | Orchestrator profile with routing and chip-in coordination skills |
| **supervisor** | Profile lifecycle management (start/stop/health-check/idle TTL) |
| **revolt** | Revolt messaging platform adapter (gateway) |
| **dashboard** | Web dashboard with REST, GraphQL, and WebSocket endpoints |
| **share_knowledge** | Cross-profile knowledge sharing with scope enforcement |

## Profiles

10 agent profiles, each with a specific role:

| Profile | Role | Run Mode | LLM |
|---------|------|----------|-----|
| **zeus** | Orchestrator | always-on | Qwen3.6 35B A3B |
| **chronos** | Scheduling | on-demand | Qwen3.6 8B |
| **iaso** | Health & fitness | on-demand | Qwen3.6 8B |
| **hermes-agent** | Messenger | on-demand | Qwen3.6 8B |
| **philia** | Relationships | on-demand | Qwen3.6 8B |
| **plutus** | Investments | on-demand | Qwen3.6 8B |
| **hephaestus** | Home & maintenance | on-demand | Qwen3.6 8B |
| **metis** | Business expert | on-demand | Qwen3.6 35B A3B |
| **apollo** | Creative & writing | on-demand | Qwen3.6 8B |
| **midas** | Finance & budgeting | on-demand | Qwen3.6 8B |

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Hermes Agent

```bash
pip install hermes-agent
```

### 3. Run setup wizard (optional)

```bash
hermes setup
```

### 4. Install Olympus

```bash
pip install -e .
```

### 5. Install plugins

Plugins are installed by copying to the Hermes plugins directory:

```bash
# Install all plugins
for plugin in zeus supervisor revolt dashboard share_knowledge; do
  cp -r plugins/$plugin ~/.hermes/plugins/$plugin
done
```

Or install individually:

```bash
cp -r plugins/zeus ~/.hermes/plugins/zeus
cp -r plugins/supervisor ~/.hermes/plugins/supervisor
cp -r plugins/revolt ~/.hermes/plugins/revolt
cp -r plugins/dashboard ~/.hermes/plugins/dashboard
cp -r plugins/share_knowledge ~/.hermes/plugins/share_knowledge
```

### 6. Create profiles

```bash
hermes profile create zeus --config profiles/zeus/config.yaml
hermes profile create chronos --config profiles/chronos/config.yaml
hermes profile create iaso --config profiles/iaso/config.yaml
hermes profile create hermes-agent --config profiles/hermes-agent/config.yaml
hermes profile create philia --config profiles/philia/config.yaml
hermes profile create plutus --config profiles/plutus/config.yaml
hermes profile create hephaestus --config profiles/hephaestus/config.yaml
hermes profile create metis --config profiles/metis/config.yaml
hermes profile create apollo --config profiles/apollo/config.yaml
hermes profile create midas --config profiles/midas/config.yaml
```

### 7. Seed test data (optional)

```bash
python plugins/dashboard/seed_data.py
```

### 8. Verify installation

```bash
hermes plugins list    # Should show all 5 plugins as enabled
hermes profile list    # Should show all 10 profiles
```

### 9. Run a profile

```bash
hermes -p zeus chat                     # Interactive chat with Zeus
hermes -p zeus -z "What's on my calendar today?"   # One-shot query
```

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `OLYMPUS_DB_PATH` | Path to shared SQLite database | `~/.hermes/olympus.db` |
| `REVOLT_BOT_TOKEN` | Revolt bot authentication token | (required for revolt plugin) |
| `REVOLT_API_URL` | Revolt API base URL | `https://api.revolt.chat` |

### Profile Configuration

Each profile's `config.yaml` supports:

```yaml
run_mode: always-on | on-demand | cron-only
idle_ttl: 300  # seconds (for on-demand profiles)
llm:
  provider: ollama
  model: qwen3.6-8b
tools:
  - zeus  # plugin toolsets to enable
system_prompt: |
  Your system prompt here...
```

## Run Tests

```bash
pytest tests/ -v
```

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Foundation: plugins, profiles, SQLite, share_knowledge |
| **Phase 2** | Planned | Dashboard: REST endpoints, GraphQL, WebSocket |
| **Phase 3** | Planned | Revolt: messaging integration |
| **Phase 4** | Planned | Supervisor: profile lifecycle management |
| **Phase 5** | Planned | Knowledge: interactive interviews + document ingestion |

See `docs/2026-05-23-olympus-architecture-design.md` for full architecture specification.
