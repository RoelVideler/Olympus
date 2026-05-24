## 1. Project Structure Reorganization

- [ ] 1.1 Create `plugins/` directory structure (`plugins/zeus/`, `plugins/supervisor/`, `plugins/revolt/`, `plugins/dashboard/`)
- [ ] 1.2 Move existing `tools/share_knowledge/` to `plugins/share_knowledge/`
- [ ] 1.3 Remove `gateway/` directory (replaced by Hermes gateway plugins)
- [ ] 1.4 Remove `supervisor/` directory (replaced by Hermes gateway extension)
- [ ] 1.5 Update `pyproject.toml` to reflect plugin structure

## 2. Zeus Plugin Implementation

- [ ] 2.1 Create `plugins/zeus/plugin.yaml` manifest
- [ ] 2.2 Create `plugins/zeus/__init__.py` with register function
- [ ] 2.3 Implement routing skill in `plugins/zeus/skills/routing.py`
- [ ] 2.4 Implement chip-in coordination skill in `plugins/zeus/skills/chip_in.py`
- [ ] 2.5 Create `plugins/zeus/profile/config.yaml` for Zeus profile
- [ ] 2.6 Verify Zeus plugin loads in Hermes (`hermes plugins list`)

## 3. Supervisor Plugin Implementation

- [ ] 3.1 Create `plugins/supervisor/plugin.yaml` manifest
- [ ] 3.2 Create `plugins/supervisor/__init__.py` with gateway extension registration
- [ ] 3.3 Implement profile lifecycle manager in `plugins/supervisor/lifecycle.py`
- [ ] 3.4 Implement health monitor in `plugins/supervisor/health.py`
- [ ] 3.5 Implement idle TTL handler in `plugins/supervisor/idle.py`
- [ ] 3.6 Implement lifecycle API for Zeus in `plugins/supervisor/api.py`
- [ ] 3.7 Verify Supervisor plugin loads in Hermes gateway

## 4. Revolt Plugin Implementation

- [ ] 4.1 Create `plugins/revolt/plugin.yaml` manifest
- [ ] 4.2 Create `plugins/revolt/__init__.py` with gateway platform adapter registration
- [ ] 4.3 Implement Revolt client in `plugins/revolt/client.py`
- [ ] 4.4 Implement message routing to Zeus in `plugins/revolt/routing.py`
- [ ] 4.5 Implement bot identity configuration in `plugins/revolt/identity.py`
- [ ] 4.6 Verify Revolt plugin loads in Hermes gateway

## 5. Dashboard Plugin Implementation

- [ ] 5.1 Create `plugins/dashboard/plugin.yaml` manifest
- [ ] 5.2 Create `plugins/dashboard/__init__.py` with gateway platform adapter registration
- [ ] 5.3 Implement REST endpoints in `plugins/dashboard/rest.py`
- [ ] 5.4 Implement GraphQL endpoint in `plugins/dashboard/graphql.py`
- [ ] 5.5 Implement WebSocket streaming in `plugins/dashboard/websocket.py`
- [ ] 5.6 Implement session cookie authentication in `plugins/dashboard/auth.py`
- [ ] 5.7 Verify Dashboard plugin loads in Hermes gateway

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
- [ ] 7.5 Zeus routes a known-domain query to specialist profile
- [ ] 7.6 Zeus handles an unknown query directly
- [ ] 7.7 Revolt message flows to Zeus and response flows back
- [ ] 7.8 Dashboard REST endpoint returns correct data
- [ ] 7.9 Dashboard WebSocket streams Zeus response

## 8. Documentation Updates

- [ ] 8.1 Update architecture spec to reflect plugin approach
- [ ] 8.2 Update README with plugin installation instructions
- [ ] 8.3 Update Phase 1 success criteria in architecture spec
- [ ] 8.4 Update Open Questions in architecture spec
