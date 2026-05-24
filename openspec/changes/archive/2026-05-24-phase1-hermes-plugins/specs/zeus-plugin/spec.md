## ADDED Requirements

### Requirement: Zeus runs as a Hermes profile with custom skills

The Zeus orchestrator SHALL run as a Hermes Agent profile (`hermes -p zeus`) with custom skills for routing, chip-in coordination, and conversation management. The skills SHALL be registered via the Hermes plugin API and activated when the Zeus profile loads.

#### Scenario: Zeus profile loads with custom skills
- **WHEN** Hermes starts the Zeus profile
- **THEN** the Zeus plugin skills are registered and available for use

#### Scenario: Zeus routes a known-domain query
- **WHEN** Zeus receives a user message that matches a known domain (e.g., scheduling, health)
- **THEN** Zeus polls the appropriate specialist profile with a lightweight model call and incorporates the response

#### Scenario: Zeus handles an unknown query
- **WHEN** Zeus receives a user message that does not match any known domain
- **THEN** Zeus handles the query directly without delegation

### Requirement: Zeus coordinates chip-in responses via polling

After receiving a user message, Zeus SHALL respond immediately with its own answer, then poll specialist profiles with lightweight model calls to check for domain relevance. Each profile responds with a relevance score and optional insight. Zeus SHALL stream relevant chip-ins to the user as they arrive, appending them to the initial response.

#### Scenario: Zeus responds immediately, then polls
- **WHEN** Zeus receives a user message
- **THEN** Zeus sends its initial response immediately and begins polling specialist profiles in parallel

#### Scenario: Profile returns relevant insight
- **WHEN** a specialist profile has relevant domain knowledge
- **THEN** Zeus streams the insight to the user as an addition to the initial response

#### Scenario: Profile returns no match
- **WHEN** a specialist profile has no relevant domain knowledge
- **THEN** the profile returns a "no match" response quickly and no insight is streamed

#### Scenario: Multiple profiles chip in with conflicting information
- **WHEN** two or more profiles return relevant insights with conflicting information
- **THEN** Zeus streams each insight with its source attribution and adds a resolution note

#### Scenario: Polling completes within target
- **WHEN** all specialist profiles respond within 2 seconds each
- **THEN** all chip-ins arrive within 10 seconds of the initial response
