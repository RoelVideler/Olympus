# Olympus

Personal AI life assistant built on Nous Research's Hermes Agent.

## Phase 1: Foundation

- Hermes Agent installed and configured
- 10 agent profiles created
- Shared SQLite database with `share_knowledge` tool
- All profiles boot independently

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

### 4. Create profiles

```bash
hermes profile create <name>              # Fresh profile
hermes profile create <name> --clone      # Clone config from default
```

### 5. Run a profile

```bash
hermes -p <name> chat                     # Interactive chat
hermes -p <name> -z "Your prompt"         # One-shot query
```

See `scripts/setup_hermes.py` for detailed Hermes Agent discovery findings.

## Install Olympus

```bash
pip install -e .
```

## Run Tests

```bash
pytest tests/ -v
```
