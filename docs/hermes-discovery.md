# Hermes Agent Installation and Discovery

This document captures the results of systematically exploring Hermes Agent's capabilities. Run `hermes --help` for the latest CLI reference.

- **Last updated:** 2026-05-23
- **Hermes Agent version:** 0.14.0 (2026.5.16)

---

## Step 1: Installation

- **Package name:** `hermes-agent` (confirmed on PyPI)
- **Latest version:** 0.14.0
- **Install command:** `pip install hermes-agent`

**Dependencies installed alongside:**

```
openai==2.24.0, python-dotenv==1.2.1, fire==0.7.1, httpx==0.28.1,
rich==14.3.3, tenacity==9.1.4, pyyaml==6.0.3, ruamel.yaml==0.18.17,
requests==2.33.0, jinja2==3.1.6, pydantic==2.12.5, prompt_toolkit==3.0.52,
croniter==6.0.0, PyJWT==2.12.1, psutil==7.2.2
```

**Entry points (from package metadata):**

| Command | Entry Point |
|---------|-------------|
| `hermes` | `hermes_cli.main:main` |
| `hermes-acp` | `acp_adapter.entry:main` |
| `hermes-agent` | `run_agent:main` |

---

## Step 2: Version and CLI Commands

**Version output:**

```
Hermes Agent v0.14.0 (2026.5.16)
Project: <venv>/lib/python3.14/site-packages
Python: 3.14.5
OpenAI SDK: 2.24.0
```

> **Note:** Hermes reports Python 3.14.5 as its runtime version. This reflects the Python version in the environment where Hermes was installed, not a requirement of Hermes itself.

**Available CLI commands (from `hermes --help`):**

| Command | Description |
|---------|-------------|
| `chat` | Interactive chat with the agent |
| `model` | Select default model and provider |
| `fallback` | Manage fallback providers |
| `gateway` | Messaging gateway management |
| `proxy` | Local OpenAI-compatible proxy |
| `lsp` | Language Server Protocol management |
| `setup` | Interactive setup wizard |
| `postinstall` | Bootstrap non-Python deps (node, browser, ripgrep, ffmpeg) |
| `whatsapp` | WhatsApp integration setup |
| `slack` | Slack integration helpers |
| `login`/`logout` | Authenticate with inference providers |
| `auth` | Manage pooled provider credentials |
| `status` | Show status of all components |
| `cron` | Cron job management |
| `webhook` | Manage dynamic webhook subscriptions |
| `kanban` | Multi-profile collaboration board |
| `hooks` | Inspect and manage shell-script hooks |
| `doctor` | Check configuration and dependencies |
| `dump` | Dump setup summary for support/debugging |
| `debug` | Debug tools — upload logs and system info |
| `backup` | Back up Hermes home directory to zip |
| `checkpoints` | Inspect / prune / clear checkpoints |
| `import` | Restore a Hermes backup from zip |
| `config` | View and edit configuration |
| `pairing` | Manage DM pairing codes |
| `skills` | Search, install, configure, and manage skills |
| `plugins` | Manage plugins — install, update, remove, list |
| `curator` | Background skill maintenance — status, run, pause, pin |
| `memory` | Configure external memory provider |
| `tools` | Configure which tools are enabled per platform |
| `computer-use` | Manage Computer Use (cua-driver) backend (macOS) |
| `mcp` | Manage MCP servers and run Hermes as MCP server |
| `sessions` | Manage session history (list, rename, export, prune, delete) |
| `insights` | Show usage insights and analytics |
| `claw` | OpenClaw migration tools |
| `version` | Show version information |
| `update` | Update Hermes Agent to latest version |
| `uninstall` | Uninstall Hermes Agent |
| `acp` | Run Hermes Agent as ACP server |
| `profile` | Manage profiles — multiple isolated Hermes instances |
| `completion` | Print shell completion script |
| `dashboard` | Start the web UI dashboard |
| `logs` | View and filter Hermes log files |

**Global flags:**

| Flag | Description |
|------|-------------|
| `-z, --oneshot PROMPT` | One-shot mode: send prompt, print response to stdout |
| `-m, --model MODEL` | Model override |
| `--provider PROVIDER` | Provider override |
| `-t, --toolsets TOOLSETS` | Comma-separated toolsets to enable |
| `-r, --resume SESSION` | Resume a previous session by ID |
| `-c, --continue [NAME]` | Resume session by name or most recent |
| `-w, --worktree` | Run in isolated git worktree |
| `--accept-hooks` | Auto-approve shell hooks |
| `-s, --skills SKILLS` | Preload skills for the session |
| `--yolo` | Bypass all dangerous command approval prompts |
| `--pass-session-id` | Include session ID in agent's system prompt |
| `--ignore-user-config` | Ignore `~/.hermes/config.yaml` |
| `--ignore-rules` | Skip auto-injection of AGENTS.md, SOUL.md, etc. |
| `--tui` | Launch the modern TUI |
| `--dev` | With `--tui`: run TypeScript sources via tsx |

---

## Step 3: Profile System

**Profile storage location:**

- Default profile: `~/.hermes/`
- Named profiles: `~/.hermes/profiles/<name>/`

**Profile commands (from `hermes profile --help`):**

| Command | Description |
|---------|-------------|
| `list` | List all profiles |
| `use` | Set sticky default profile |
| `create` | Create a new profile |
| `delete` | Delete a profile |
| `show` | Show profile details |
| `alias` | Manage wrapper scripts |
| `rename` | Rename a profile |
| `export` | Export a profile to archive |
| `import` | Import a profile from archive |
| `install` | Install a profile distribution from git URL or local directory |
| `update` | Re-pull a distribution and apply updates |
| `info` | Show a profile's distribution manifest |

**Creating a profile:**

```bash
hermes profile create <name>              # fresh profile + bundled skills
hermes profile create <name> --clone      # copy config.yaml, .env, SOUL.md
hermes profile create <name> --clone-all  # full copy of active profile
hermes profile create <name> --no-skills  # empty profile, no bundled skills
hermes profile create <name> --no-alias   # skip wrapper script creation
```

**Running a profile:**

```bash
hermes -p <profile_name> chat             # via -p flag
hermes --profile <profile_name> chat      # via --profile flag
<profile_name> chat                       # via wrapper alias (~/.local/bin/<name>)
HERMES_HOME=<profile_path> hermes chat    # via env var
```

**Profile directory structure (bootstrapped on create):**

```
memories/    - Agent memory files (MEMORY.md, USER.md)
sessions/    - Session history
skills/      - Installed skills (SKILL.md files)
skins/       - UI skins
logs/        - Log files
plans/       - Planning documents
workspace/   - Working directory for the profile
cron/        - Scheduled job output
home/        - Per-profile HOME for subprocess isolation
config.yaml  - Configuration file
.env         - Secrets/API keys
SOUL.md      - Persona definition
active_profile - Sticky active profile (in ~/.hermes/)
```

**Profile name rules:**

- Lowercase, alphanumeric, hyphens, underscores
- Max 64 characters
- Reserved names: `hermes`, `default`, `test`, `tmp`, `root`, `sudo`
- Cannot conflict with hermes subcommands

---

## Step 4: ACP (Agent Client Protocol)

- **ACP interface:** YES — Hermes has ACP support
- **Command:** `hermes acp`
- **Description:** Run Hermes Agent in ACP mode for editor integration (VS Code, Zed, JetBrains)

**ACP options:**

| Flag | Description |
|------|-------------|
| `--check` | Verify ACP dependencies and adapter imports |
| `--setup` | Run interactive Hermes provider/model setup for ACP |
| `--setup-browser` | Install agent-browser + Playwright Chromium |
| `--version` | Print Hermes ACP version |
| `--accept-hooks` | Auto-approve shell hooks |
| `-y, --yes` | Accept all prompts |

- **ACP entry point:** `hermes-acp` -> `acp_adapter.entry:main`
- **ACP source directory:** `~/.hermes/hermes-agent/acp_adapter/`
- **ACP registry directory:** `~/.hermes/hermes-agent/acp_registry/`

> **Note:** ACP dependencies not installed by default. Install with: `pip install -e '.[acp]'`

---

## Step 5: MCP (Model Context Protocol)

- **MCP interface:** YES — Hermes has MCP support
- **Command:** `hermes mcp`
- **Description:** Manage MCP servers and run Hermes as an MCP server

**MCP subcommands:**

| Command | Description |
|---------|-------------|
| `serve` | Run Hermes as an MCP server (expose conversations to other agents) |
| `add` | Add an MCP server (discovery-first install) |
| `remove` (`rm`) | Remove an MCP server |
| `list` (`ls`) | List configured MCP servers |
| `test` | Test MCP server connection |
| `configure` | Toggle tool selection |
| `login` | Force re-authentication for OAuth-based MCP server |

**Adding an MCP server:**

```bash
hermes mcp add <name> --url <endpoint>           # HTTP/SSE endpoint
hermes mcp add <name> --command <cmd> --args ... # stdio command
hermes mcp add <name> --preset <preset>          # Known preset
```

- **MCP tool notation:** `server:tool` (e.g., `github:create_issue`)
- MCP tools are configured per-platform via `hermes tools`
- **MCP source:** `hermes_cli/mcp_config.py`

---

## Step 6: Tool Plugin System

- **Tool system:** YES — Hermes has a comprehensive tool system
- **Command:** `hermes tools`
- **Description:** Enable, disable, or list tools for CLI, Telegram, Discord, etc.

**Tool subcommands:**

| Command | Description |
|---------|-------------|
| `list` | Show all tools and their enabled/disabled status |
| `disable` | Disable toolsets or MCP tools |
| `enable` | Enable toolsets or MCP tools |
| `--summary` | Print summary of enabled tools per platform |

**Built-in toolsets (26 total):**

- **Enabled:** web, browser, terminal, file, code_execution, vision, image_gen, tts, skills, todo, memory, session_search, clarify, delegation, cronjob, messaging, homeassistant, spotify
- **Disabled:** video, x_search, moa, video_gen, yuanbao, computer_use

**Tool notation:**

- Built-in toolsets: plain names (e.g., `web`, `memory`)
- MCP tools: `server:tool` notation (e.g., `github:create_issue`)

**Plugin system:** YES — Hermes has a plugin system. Command: `hermes plugins`

| Command | Description |
|---------|-------------|
| `install <owner/repo>` | Install a plugin from a Git repository |
| `update` | Pull latest changes for installed plugins |
| `remove` (`rm`) | Remove an installed plugin |
| `list` (`ls`) | List installed plugins |
| `enable`/`disable` | Enable or disable a plugin |

- **Plugin source:** `hermes_cli/plugins.py`, `hermes_cli/plugins_cmd.py`

**How tools are registered:**

- Built-in toolsets are loaded from the Hermes package
- MCP tools are registered via `hermes mcp add`
- Plugins are installed from Git repos and provide additional capabilities
- Tool configuration is stored per-profile in `config.yaml` under `toolsets:`

**Tool discovery:**

- **Built-in:** loaded at startup from `hermes_cli/`
- **MCP:** discovered from `config.yaml` MCP server definitions
- **Plugins:** discovered from `~/.hermes/plugins/` directory
- **Skills:** discovered from `~/.hermes/skills/` directory (SKILL.md files)

---

## Step 7: Cron System

- **Cron system:** YES — Hermes has a cron/scheduled task system
- **Command:** `hermes cron`
- **Description:** Manage scheduled tasks

**Cron subcommands:**

| Command | Description |
|---------|-------------|
| `list` | List scheduled jobs |
| `create` (`add`) | Create a scheduled job |
| `edit` | Edit an existing scheduled job |
| `pause` | Pause a scheduled job |
| `resume` | Resume a paused job |
| `run` | Run a job on the next scheduler tick |
| `remove` (`rm`, `delete`) | Remove a scheduled job |
| `status` | Check if cron scheduler is running |
| `tick` | Run due jobs once and exit |

**Creating a cron job:**

```bash
hermes cron create <schedule> [prompt]
```

**Schedule formats:**

```
'30m'              - Every 30 minutes
'every 2h'         - Every 2 hours
'0 9 * * *'        - Standard cron expression (daily at 9am)
```

**Job options:**

| Flag | Description |
|------|-------------|
| `--name NAME` | Human-friendly job name |
| `--deliver DELIVER` | Delivery target: `origin`, `local`, `telegram`, `discord`, `signal`, or `platform:chat_id` |
| `--repeat REPEAT` | Optional repeat count |
| `--skill SKILLS` | Attach a skill (repeatable) |
| `--script SCRIPT` | Path to script under `~/.hermes/scripts/` |
| `--no-agent` | Skip LLM, run script directly, deliver stdout |
| `--workdir WORKDIR` | Absolute path for job to run from |

- **Cron storage:** `~/.hermes/cron/`
- **Cron source:** `hermes_cli/cron.py`

**Scheduler runs as part of the gateway service:**

```bash
hermes gateway start  - Starts the gateway (includes cron scheduler)
hermes cron tick      - Manually run due jobs once
```

---

## Step 8: How Zeus Communicates with Profiles

Zeus (the orchestrator) communicates with profiles via:

### 1. Direct CLI invocation

```bash
hermes -p <profile_name> chat -q "<prompt>"
```

### 2. Kanban board (multi-profile collaboration)

```bash
hermes kanban create --assign <profile_name> --title "..." --body "..."
```

> **Design note:** The kanban system is intended to dispatch tasks to profiles via the gateway. Profiles claim tasks atomically and execute in isolated workspaces. This is based on the kanban CLI capabilities documented in Step 13; the exact dispatch workflow for Zeus-to-profile communication is inferred from these capabilities.

### 3. Cross-platform messaging

> **Design note:** Profiles can deliver results via Telegram, Discord, Signal, etc., configured via `hermes cron create --deliver <platform>`. Using cron-based delivery as a Zeus-to-profile communication channel is an architectural projection, not a documented feature.

### 4. MCP server

```bash
hermes mcp serve
```

Exposes Hermes conversations to other agents. Other agents can connect as MCP clients.

### 5. ACP server

```bash
hermes acp
```

Runs Hermes as an ACP server for editor integration.

### Profile isolation

Each profile has its own:

- `config.yaml` and `.env` (API keys, model settings)
- memories, sessions, skills, logs
- gateway service (can run independently)
- cron jobs
- subprocess HOME (isolates git, ssh, gh credentials)

---

## Step 9: Key Commands to Run a Profile

**Run a profile interactively:**

```bash
hermes -p <name> chat
hermes -p <name> --tui
```

**Run a profile with a single prompt (scriptable):**

```bash
hermes -p <name> -z "Hello, what's my schedule today?"
```

**Resume a profile's previous session:**

```bash
hermes -p <name> -c
hermes -p <name> -r <session_id>
```

**Run a profile with specific toolsets:**

```bash
hermes -p <name> -z "Prompt" -t web,terminal,file
```

**Run a profile with preloaded skills:**

```bash
hermes -p <name> -z "Prompt" -s github-auth,plan
```

**Start a profile's gateway (background service):**

```bash
hermes -p <name> gateway start
```

**Check a profile's status:**

```bash
hermes -p <name> status
hermes -p <name> doctor
```

---

## Step 10: Configuration

- **Config file:** `~/.hermes/config.yaml`
- **Secrets:** `~/.hermes/.env`

**Key config sections:**

| Section | Description |
|---------|-------------|
| `model` | Default model, provider, base_url, api_key |
| `providers` | Provider definitions |
| `fallback_providers` | Fallback chain |
| `toolsets` | Enabled toolsets list |
| `agent` | max_turns, gateway_timeout, personalities, etc. |
| `terminal` | backend, timeout, docker settings |
| `browser` | inactivity_timeout, cdp_url, etc. |
| `checkpoints` | enabled, max_snapshots, retention |

**Config commands:**

```bash
hermes config show      - Show current configuration
hermes config edit      - Open config in $EDITOR
hermes config set <key> <value> - Set a config value
hermes config path      - Print config file path
hermes config env-path  - Print .env file path
hermes config check     - Check for missing/outdated config
hermes config migrate   - Update config with new options
```

---

## Step 11: Skills System

- **Skills:** YES — Hermes has a comprehensive skills system (81 builtin skills)
- **Command:** `hermes skills`
- **Categories:** apple, autonomous-ai-agents, creative, data-science, devops, email, gaming, github, mcp, media, mlops, note-taking, productivity, red-teaming, research, smart-home, social-media, software-development

**Skill commands:**

| Command | Description |
|---------|-------------|
| `browse` | Browse all available skills (paginated) |
| `search` | Search skill registries |
| `install` | Install a skill |
| `inspect` | Preview a skill without installing |
| `list` | List installed skills |
| `check` | Check installed hub skills for updates |
| `update` | Update installed hub skills |
| `audit` | Re-scan installed hub skills |
| `uninstall` | Remove a hub-installed skill |
| `reset` | Reset a bundled skill |
| `publish` | Publish a skill to a registry |
| `snapshot` | Export/import skill configurations |
| `tap` | Manage skill sources |
| `config` | Interactive skill configuration |

---

## Step 12: Session Management

- **Sessions:** YES — Hermes has SQLite-based session management
- **Command:** `hermes sessions`
- **Storage:** SQLite database (`state.db` / `hermes_state.db`)

**Session commands:**

| Command | Description |
|---------|-------------|
| `list` | List recent sessions |
| `export` | Export sessions to JSONL file |
| `delete` | Delete a specific session |
| `prune` | Delete old sessions |
| `stats` | Show session store statistics |
| `rename` | Set or change a session's title |
| `browse` | Interactive session picker |

---

## Step 13: Kanban (Multi-Profile Collaboration)

- **Kanban:** YES — Hermes has a durable SQLite-backed task board
- **Command:** `hermes kanban`
- **Description:** Multi-profile collaboration board shared across profiles

**Kanban commands:**

| Command | Description |
|---------|-------------|
| `init` | Create kanban.db if missing |
| `boards` | Manage kanban boards |
| `create` | Create a new task |
| `list` (`ls`) | List tasks |
| `show` | Show a task with comments + events |
| `assign` | Assign or reassign a task |
| `claim` | Atomically claim a ready task |
| `complete` | Mark tasks done |
| `dispatch` | One dispatcher pass: reclaim stale, promote ready, spawn workers |
| `watch` | Live-stream task events |
| `stats` | Per-status + per-assignee counts |

Tasks are claimed atomically and executed by a named profile in an isolated workspace.

---

## Step 14: Dashboard

- **Dashboard:** YES — Hermes has a web UI dashboard
- **Command:** `hermes dashboard`
- **Default port:** 9119

**Dashboard commands:**

```bash
hermes dashboard            - Start the web UI
hermes dashboard --stop     - Stop running dashboard
hermes dashboard --status   - List running dashboard processes
```
