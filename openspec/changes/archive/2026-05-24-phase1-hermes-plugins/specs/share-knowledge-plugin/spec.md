## ADDED Requirements

### Requirement: share_knowledge plugin enforces scope per profile

The share_knowledge plugin SHALL enforce scope access control based on each profile's allowed scopes. Profiles SHALL only read and write facts within their authorized scopes.

#### Scenario: Profile writes to authorized scope
- **WHEN** a profile calls share_knowledge with action=write on an authorized scope
- **THEN** the fact is written to the shared SQLite database

#### Scenario: Profile writes to unauthorized scope
- **WHEN** a profile calls share_knowledge with action=write on an unauthorized scope
- **THEN** the plugin returns an error and the fact is not written

#### Scenario: Profile queries authorized scope
- **WHEN** a profile calls share_knowledge with action=query on an authorized scope
- **THEN** the plugin returns matching facts from the shared SQLite database

#### Scenario: Profile queries unauthorized scope
- **WHEN** a profile calls share_knowledge with action=query on an unauthorized scope
- **THEN** the plugin returns an error and no facts are returned

### Requirement: share_knowledge derives source_profile from Hermes context

The share_knowledge plugin SHALL derive the `source_profile` from Hermes' `get_active_profile_name()`, not from user-supplied arguments. This prevents agents from spoofing their identity.

#### Scenario: Fact is attributed to calling profile
- **WHEN** a profile calls share_knowledge with action=write
- **THEN** the fact's source_profile is set to the calling profile's name from Hermes context

### Requirement: share_knowledge validates database path

The share_knowledge plugin SHALL validate that the database path (from `OLYMPUS_DB_PATH` environment variable or default) is within the `~/.hermes/` directory. Paths outside this directory SHALL be rejected.

#### Scenario: Valid database path is used
- **WHEN** `OLYMPUS_DB_PATH` points to a path within `~/.hermes/`
- **THEN** the plugin uses that path for the database

#### Scenario: Invalid database path is rejected
- **WHEN** `OLYMPUS_DB_PATH` points to a path outside `~/.hermes/`
- **THEN** the plugin falls back to the default path `~/.hermes/olympus.db`

### Requirement: share_knowledge uses WAL journal mode

The share_knowledge plugin SHALL use `PRAGMA journal_mode = WAL` for crash recovery robustness.

#### Scenario: Database uses WAL mode
- **WHEN** the plugin connects to the database
- **THEN** the database is opened with WAL journal mode

### Requirement: share_knowledge validates input lengths

The share_knowledge plugin SHALL validate that the `domain` field is at most 100 characters and the `fact` field is at most 10,000 characters.

#### Scenario: Domain exceeds length limit
- **WHEN** a profile calls share_knowledge with a domain longer than 100 characters
- **THEN** the plugin returns an error

#### Scenario: Fact exceeds length limit
- **WHEN** a profile calls share_knowledge with a fact longer than 10,000 characters
- **THEN** the plugin returns an error
