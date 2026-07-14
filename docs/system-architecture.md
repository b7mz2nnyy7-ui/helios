# Helios System Architecture

## Current System

Project Helios is a modular Agent Engine for an autonomous AI Content Company.
The current implementation focuses on deterministic engine primitives and Atlas,
the first content agent for trend research.

## Dependency Direction

```text
engine/          core abstractions and runtime services
agents/          content agents built on engine abstractions
integrations/    adapters for external systems
scripts/         local entry points and demos
tests/           unit and integration tests
```

Rules:

- `engine/` must not import from `agents/` or `integrations/`.
- Agents may use engine abstractions.
- External systems live behind adapters in `integrations/`.
- Agents do not call each other directly.
- Work moves through Tasks, Runtime, Capabilities, Events and Memory.

## Runtime Flow

```text
Task
-> HeliosRuntime.submit_task()
-> TaskDispatcher
-> AgentRegistry.find_by_capability()
-> BaseAgent.run(task)
-> Task.result / Task.error_message
-> Runtime events
-> optional MemoryStore persistence
```

The runtime is synchronous today. There is no queue, no async execution, no
retry policy and no scheduler yet.

Runtime events currently include:

- `runtime.started`
- `runtime.stopped`
- `task.dispatched`
- `task.failed`

The runtime also exposes deterministic health inspection through
`inspect_health()` and `health_check()`. Health inspection is synchronous and
uses registered agents' `health_check()` methods.

## Engine Modules

- `engine/tasks/`: Task model, priority and status state machine.
- `engine/runtime/`: BaseAgent, registry, dispatcher, runtime and capabilities.
- `engine/events/`: synchronous in-memory EventBus.
- `engine/tools/`: generic tool interface and registry.
- `engine/llm/`: provider-neutral LLM request, response and provider interface.
- `engine/memory/`: generic memory entry and store interface.

## Atlas Today

Atlas is implemented in `agents/trend_research/`.

Current capabilities:

- handles `TREND_RESEARCH` tasks
- uses `MockTrendTool` for deterministic trend candidates
- uses `LLMTool` with `MockLLMProvider` for deterministic summaries
- returns a `TrendReport`
- stores the report on the Task result pipeline
- optionally persists reports through `BaseMemoryStore`
- can write Markdown reports to Obsidian through `ObsidianMemoryStore`

## AI Content Company Departments

The planned organization maps to capabilities rather than hard-coded agent
dependencies:

- Trend Research: identify candidate topics and evidence.
- Audience Research: map audience segments, pains and language.
- Strategy: choose content angles, positioning and sequencing.
- Script Writing: draft scripts and episode structures.
- Storyboard: transform scripts into visual plans.
- Video Production: assemble and render production assets.
- Thumbnail: create thumbnail concepts and assets.
- Caption: generate captions, shorts metadata and post text.
- Publishing: prepare platform-specific publishing payloads.
- Analytics: read performance data and summarize outcomes.
- Learning: convert outcomes into reusable operating knowledge.
- Memory: persist useful artifacts and decisions.
- Quality Control: check factuality, policy, style and completeness.

Each department can start as deterministic services and later gain specialized
agents when the behavior is valuable enough to justify them.

## Company Architecture

Helios is built as an AI Company with clear departments. Each future agent
represents a department or operating role, described by provider-neutral
`AgentDefinition` metadata under `engine/company/`.

The Company Architecture is a metamodel only. It defines departments, agent
definitions, a registry for those definitions and a blueprint for the planned
company structure. The current blueprint contains 31 AgentDefinitions. It does
not implement productive agents and does not change runtime execution.

Communication remains indirect through Runtime, Tasks and Events. Shared
knowledge is stored centrally through Memory so that reports, decisions and
operating context can be reused across departments. The architecture is designed
for long-term extensibility while keeping the engine independent from concrete
agents and integrations.

## Near-Term Architecture Principles

- Keep Atlas productive before adding more agents.
- Prefer deterministic system services for routing, validation, retries and
  monitoring.
- Keep providers replaceable through tool/provider interfaces.
- Add production integrations only behind explicit adapters.
- Avoid real network calls, paid APIs and secrets until approved.
