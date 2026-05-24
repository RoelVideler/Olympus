## ADDED Requirements

### Requirement: Dashboard plugin serves REST endpoints

The Dashboard plugin SHALL implement a Hermes gateway platform adapter that serves REST endpoints for the React dashboard. Endpoints SHALL include health data CRUD, wiki, calendar, contacts, preferences, facts, issues, locations, notifications, and models.

#### Scenario: Dashboard plugin serves health data
- **WHEN** a client requests `GET /api/health`
- **THEN** the plugin returns health data from the shared SQLite database

#### Scenario: Dashboard plugin serves wiki data
- **WHEN** a client requests `GET /api/wiki`
- **THEN** the plugin returns wiki data from the shared SQLite database

### Requirement: Dashboard plugin serves GraphQL endpoint

The Dashboard plugin SHALL serve a GraphQL endpoint for complex queries that span multiple data types.

#### Scenario: GraphQL query returns combined data
- **WHEN** a client sends a GraphQL query requesting health and calendar data
- **THEN** the plugin returns both data types in a single response

### Requirement: Dashboard plugin serves WebSocket for streaming

The Dashboard plugin SHALL serve a WebSocket endpoint for real-time streaming of Zeus responses and system events.

#### Scenario: WebSocket streams Zeus response
- **WHEN** Zeus produces a response chunk
- **THEN** the plugin streams the chunk to connected WebSocket clients

#### Scenario: WebSocket streams system events
- **WHEN** a system event occurs (profile start/stop, cron job execution)
- **THEN** the plugin streams the event to connected WebSocket clients

### Requirement: Dashboard plugin authenticates requests

The Dashboard plugin SHALL authenticate requests using session cookies with `HttpOnly`, `SameSite=Strict` attributes and a locally-generated secret.

#### Scenario: Unauthenticated request is rejected
- **WHEN** a client requests a dashboard endpoint without a valid session cookie
- **THEN** the plugin returns a 401 Unauthorized response

#### Scenario: Authenticated request is served
- **WHEN** a client requests a dashboard endpoint with a valid session cookie
- **THEN** the plugin serves the requested data
