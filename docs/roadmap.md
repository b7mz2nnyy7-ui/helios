# Helios Technical Roadmap

## Current Baseline

Helios currently has a synchronous runtime, capability routing, tasks with a
state machine, events, tools, provider-neutral LLM abstractions, memory storage,
an Obsidian adapter, Atlas and a local Atlas demo runner.

Atlas is still a mock-first agent. It proves the shape of the pipeline without
calling real APIs:

```text
raw query
-> mock trend candidates
-> mock LLM summary
-> TrendReport
-> Task.result
-> optional Obsidian Markdown memory
```

## Product Direction

The first production target is a reliable Atlas that can create useful trend
reports with traceable inputs, replaceable providers and safe local persistence.
Only after Atlas is useful should Helios expand into additional content
departments.

## Company Architecture

Helios is evolving into an AI Company with explicit departments. Each future
agent represents a department or operating role, but departments communicate
through Runtime, Tasks and Events rather than direct calls. Knowledge is stored
centrally in Memory so that outputs and decisions remain reusable.

The Company Architecture is a provider-neutral metamodel for long-term
extensibility. It defines departments, planned agent definitions and a registry
for those definitions without implementing productive agents. The current
blueprint contains 31 AgentDefinitions.

## Milestones

### M0: Local Deterministic Atlas

Status: complete.

- Runtime, registry, dispatcher and capability routing exist.
- Atlas handles trend research tasks.
- Reports flow through Task results.
- Obsidian persistence is optional.
- Local demo runner exists.

### M1: Atlas Report Quality and Traceability

Status: complete.

- Make saved reports self-describing.
- Include generator metadata in Markdown output.
- Keep source trend evidence visible in reports.
- Preserve deterministic tests.

### M2: Trend Tool Boundary for Real Providers

Status: complete.

- Define the minimal contract expected from trend research tools.
- Keep mock behavior as the default.
- Add adapter tests before any external provider.
- Do not add network calls yet.
- Validate trend tool and LLM tool return values inside Atlas.

### M3: LLM Provider Readiness

Status: complete.

- Add provider configuration validation without secrets.
- Keep `BaseLLMProvider` provider-neutral.
- Add fake provider tests for failure modes, token metadata and model identity.
- Add real provider only after explicit approval.
- Keep real provider adapters out of the engine until approved.

### M4: Runtime Operational Safety

Status: complete.

- Add deterministic task failure events.
- Add structured runtime health checks.
- Add observability hooks before queues or retries.
- Keep execution synchronous until queue requirements are concrete.
- Keep monitoring and queueing out until concrete requirements exist.

### M5: Production Atlas Integration

Status: planned, requires approval.

- Add one approved real trend data adapter.
- Add one approved real LLM provider adapter.
- Configure secrets outside the repository.
- Validate generated reports against quality gates.

### M6: Additional Content Departments

Status: in progress.

- Add departments one at a time through capabilities.
- Start with deterministic services where possible.
- Introduce agents only when independent behavior is needed.
- Maintain a provider-neutral company blueprint before implementation.

## Next Small Steps

1. Use the Company Architecture blueprint to prioritize future departments.
2. Extend the local demo only when it helps manual review.
3. Prepare a review decision for the first real Atlas provider integration.
