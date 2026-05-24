## ADDED Requirements

### Requirement: Supervisor manages profile lifecycle

The Supervisor SHALL extend Hermes' gateway with profile lifecycle management. It SHALL read `run_mode` from profile configs and manage profile processes accordingly.

#### Scenario: Supervisor starts an always-on profile
- **WHEN** Hermes gateway starts and a profile has `run_mode: always-on`
- **THEN** the Supervisor starts the profile process and monitors its health

#### Scenario: Supervisor starts an on-demand profile
- **WHEN** Zeus requests a profile with `run_mode: on-demand`
- **THEN** the Supervisor starts the profile process and tracks its idle time

#### Scenario: Supervisor kills an idle on-demand profile
- **WHEN** an on-demand profile has been idle for the configured TTL
- **THEN** the Supervisor stops the profile process

#### Scenario: Supervisor restarts a crashed profile
- **WHEN** a profile process crashes unexpectedly
- **THEN** the Supervisor detects the crash and restarts the profile

### Requirement: Supervisor exposes lifecycle API

The Supervisor SHALL expose an API that Zeus can call for profile lifecycle operations (start, stop, health-check).

#### Scenario: Zeus requests profile start
- **WHEN** Zeus calls the Supervisor API to start a profile
- **THEN** the Supervisor starts the profile and returns the process status

#### Scenario: Zeus checks profile health
- **WHEN** Zeus calls the Supervisor API to check a profile's health
- **THEN** the Supervisor returns the profile's health status (running, stopped, error)

### Requirement: Supervisor reads run_mode from profile configs

The Supervisor SHALL read the `run_mode` field from each profile's `config.yaml` file. Supported values: `always-on`, `on-demand`, `cron-only`.

#### Scenario: Supervisor reads always-on config
- **WHEN** the Supervisor reads a profile config with `run_mode: always-on`
- **THEN** the Supervisor starts the profile on gateway startup

#### Scenario: Supervisor reads on-demand config
- **WHEN** the Supervisor reads a profile config with `run_mode: on-demand`
- **THEN** the Supervisor waits for a start request before launching the profile
