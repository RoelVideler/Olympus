## ADDED Requirements

### Requirement: Revolt adapter connects to Hermes gateway

The Revolt plugin SHALL implement a Hermes gateway platform adapter for the Revolt messaging platform. Messages from Revolt SHALL flow to the Zeus profile, and Zeus responses SHALL flow back to Revolt.

#### Scenario: Revolt adapter connects to gateway
- **WHEN** Hermes gateway starts with the Revolt plugin enabled
- **THEN** the adapter connects to the Revolt server and authenticates with the bot token

#### Scenario: User message flows to Zeus
- **WHEN** a user sends a message in Revolt
- **THEN** the adapter forwards the message to the Zeus profile for processing

#### Scenario: Zeus response flows back to Revolt
- **WHEN** Zeus produces a response for a Revolt message
- **THEN** the adapter sends the response back to the user's Revolt channel

### Requirement: Revolt adapter handles bot identity

The Revolt adapter SHALL configure the bot's identity (name, avatar) and handle channel structure (direct messages, group channels).

#### Scenario: Bot responds in direct message
- **WHEN** a user sends a direct message to the bot
- **THEN** the bot responds in the same DM channel

#### Scenario: Bot responds in group channel
- **WHEN** a user mentions the bot in a group channel
- **THEN** the bot responds in the same group channel

### Requirement: Revolt adapter manages message routing

The Revolt adapter SHALL route messages to the correct Hermes profile based on channel configuration or user context.

#### Scenario: Default routing to Zeus
- **WHEN** a message arrives and no specific routing rule applies
- **THEN** the message is routed to the Zeus profile
