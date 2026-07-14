# Project State

Last updated: 2026-07-14

## Repository Status

The current local repository has no tracked files yet. All project files are
visible as untracked in `git status --short`, so `git diff` does not show a
normal tracked-file patch until files are staged or committed.

No commits or pull requests are created automatically.

## Implemented Capabilities

- Agent runtime with synchronous task submission.
- Agent registry with unique IDs and capability lookup.
- Dispatcher that routes tasks by required capability.
- Task model with valid state transitions and result/error transport.
- Synchronous EventBus.
- Runtime publishes deterministic task failure events.
- Runtime exposes structured synchronous health inspection.
- Generic BaseTool and ToolRegistry.
- Provider-neutral LLM request, response and provider interfaces.
- Provider-neutral LLM configuration validation without secrets.
- Generic MemoryStore interface and MemoryEntry model.
- Obsidian Markdown memory adapter.
- Atlas Trend Research Agent using mock trend data and mock LLM output.
- Local Atlas demo runner writing reports to a configured Obsidian vault.
- Atlas reports include generator metadata in Markdown output.
- Atlas validates required trend query input before invoking trend tools.
- Atlas validates trend and LLM tool return values before completing tasks.
- Company Architecture metamodel with departments, agent definitions, registry
  and a blueprint containing 31 AgentDefinitions.

## Current Constraints

- No real APIs are enabled.
- No secrets are stored or required.
- Runtime execution is synchronous.
- There is no queue, scheduler, retry system or monitoring layer.
- Atlas uses deterministic mock tools by default.
- Company Architecture defines future roles only; it does not implement
  productive agents.

## Company Architecture

Helios is now modeled as an AI Company. Each future agent represents a
department or operating role. Communication remains indirect through Runtime,
Tasks and Events, while reusable knowledge is stored centrally in Memory.

The current Company Architecture is provider-neutral and limited to metadata:
`Department`, `AgentDefinition`, `CompanyRegistry` and the Helios company
blueprint with 31 AgentDefinitions. It is designed for long-term extensibility without coupling
`engine/` to concrete agents or external integrations.

## Active Technical Focus

The next phase should make Atlas more useful and traceable while preserving the
mock-first, provider-neutral architecture. Production integrations should be
added only after explicit approval for the provider, secret handling and cost
model.
