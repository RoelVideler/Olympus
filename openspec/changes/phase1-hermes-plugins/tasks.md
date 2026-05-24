## 1. Project Structure Reorganization

- [ ] 1.1 Create `plugins/` directory structure (`plugins/zeus/`, `plugins/supervisor/`, `plugins/revolt/`, `plugins/dashboard/`)
- [ ] 1.2 Move existing `tools/share_knowledge/` to `plugins/share_knowledge/`
- [ ] 1.3 Update `pyproject.toml` to reflect plugin structure

## 2. Zeus Plugin Implementation

- [ ] 2.1 Create `plugins/zeus/plugin.yaml` manifest
- [ ] 2.2 Create `plugins/zeus/__init__.py` with register function
- [ ] 2.3 Implement routing skill in `plugins/zeus/skills/routing.py` — uses polling (lightweight model calls) to specialist profiles, not kanban dispatch
- [ ] 2.4 Implement chip-in coordination skill in `plugins/zeus/skills/chip_in.py` — polls profiles for relevance scores, collects and filters responses
- [ ] 2.5 Create `plugins/zeus/profile/config.yaml` for Zeus profile
- [ ] 2.6 Verify Zeus plugin loads in Hermes (`hermes plugins list`)

## 3. Supervisor Plugin Implementation

- [ ] 3.1 Create `plugins/supervisor/plugin.yaml` manifest
- [ ] 3.2 Verify Hermes gateway extension API supports process lifecycle management
- [ ] 3.3 Create `plugins/supervisor/__init__.py` — register as gateway extension if API supports it, otherwise as separate plugin
- [ ] 3.4 Implement profile lifecycle manager in `plugins/supervisor/lifecycle.py`
- [ ] 3.5 Implement health monitor in `plugins/supervisor/health.py`
- [ ] 3.6 Implement idle TTL handler in `plugins/supervisor/idle.py`
- [ ] 3.7 Implement lifecycle API for Zeus in `plugins/supervisor/api.py`
- [ ] 3.8 Verify Supervisor plugin loads in Hermes gateway

## 4. Revolt Plugin Implementation

- [ ] 4.1 Create `plugins/revolt/plugin.yaml` manifest
- [ ] 4.2 Create `plugins/revolt/__init__.py` with gateway platform adapter registration
- [ ] 4.3 Implement Revolt client in `plugins/revolt/client.py` — uses Revolt REST API (no official Python SDK exists)
- [ ] 4.4 Implement message routing to Zeus in `plugins/revolt/routing.py`
- [ ] 4.5 Implement bot identity configuration in `plugins/revolt/identity.py`
- [ ] 4.6 Implement error handling: connection retry with exponential backoff, auth failure logging, rate limit handling
- [ ] 4.7 Verify Revolt plugin loads in Hermes gateway

## 5. Dashboard Plugin Implementation

- [ ] 5.1 Create `plugins/dashboard/plugin.yaml` manifest
- [ ] 5.2 Create `plugins/dashboard/__init__.py` with gateway platform adapter registration
- [ ] 5.3 Implement session cookie authentication in `plugins/dashboard/auth.py`
- [ ] 5.4 Implement Phase 2 REST endpoints (5 critical): `GET /api/health`, `GET /api/wiki`, `GET /api/calendar`, `GET /api/contacts`, `GET /api/preferences`
- [ ] 5.5 Implement GraphQL endpoint in `plugins/dashboard/graphql.py`
- [ ] 5.6 Implement WebSocket streaming in `plugins/dashboard/websocket.py`
- [ ] 5.7 Seed test data in SQLite for integration testing
- [ ] 5.8 Verify Dashboard plugin loads in Hermes gateway

## 6. Share Knowledge Plugin Verification

- [ ] 6.1 Verify share_knowledge plugin loads in Hermes v0.14.0
- [ ] 6.2 Verify scope enforcement works correctly
- [ ] 6.3 Verify source_profile derives from Hermes context
- [ ] 6.4 Verify database path validation works

## 7. Integration Testing

- [ ] 7.1 All 10 profiles boot and respond to basic prompt
- [ ] 7.2 All 5 plugins load correctly (`hermes plugins list` shows enabled)
- [ ] 7.3 share_knowledge round-trip: write from one profile, read from another
- [ ] 7.4 Supervisor starts/stops profiles based on run_mode
- [ ] 7.5 Zeus routes a known-domain query to specialist profile via polling
- [ ] 7.6 Zeus handles an unknown query directly
- [ ] 7.7 Dashboard REST endpoint returns correct data (Phase 2 endpoints)
- [ ] 7.8 Dashboard WebSocket streams Zeus response

## 8. Documentation Updates

- [ ] 8.1 Update README with plugin installation instructions
