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

After receiving a user message, Zeus SHALL poll specialist profiles with lightweight model calls to check for domain relevance. Each profile responds with a relevance score and optional insight. Zeus SHALL collect responses, filter by threshold, and incorporate relevant chip-ins into the final response.

#### Scenario: Zeus polls for chip-ins
- **WHEN** Zeus receives a user message
- **THEN** Zeus polls specialist profiles with lightweight model calls

#### Scenario: Profile returns relevant insight
- **WHEN** a specialist profile has relevant domain knowledge
- **THEN** the profile returns a relevance score and insight, which Zeus incorporates into the response

#### Scenario: Profile returns no match
- **WHEN** a specialist profile has no relevant domain knowledge
- **THEN** the profile returns a "no match" response quickly

#### Scenario: Multiple profiles chip in with conflicting information
- **WHEN** two or more profiles return relevant insights with conflicting information
- **THEN** Zeus resolves the conflict and presents a unified response to the user

### Requirement: Zeus maintains conversation context

Zeus SHALL maintain conversation context across message exchanges, including user preferences, ongoing tasks, and chip-in history.

#### Scenario: Zeus references prior conversation
- **WHEN** Zeus responds to a user message
- **THEN** Zeus includes relevant context from prior messages in the conversation

### Requirement: Zeus polling latency stays under 2 seconds per profile

Zeus SHALL complete each polling call to a specialist profile in under 2 seconds. Total polling time across all profiles SHALL stay under 10 seconds for a 5-profile poll.

#### Scenario: Single profile poll completes quickly
- **WHEN** Zeus polls a single specialist profile
- **THEN** the poll completes in under 2 seconds

#### Scenario: Multi-profile poll completes within budget
- **WHEN** Zeus polls 5 specialist profiles
- **THEN** the total polling time stays under 10 seconds
