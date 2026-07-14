# Project Helios

Helios ist ein AI Operating System. Der aktuelle Fokus liegt auf Engine,
Runtime, generischen Tools, Memory und dem ersten Content-Agenten Atlas.

## Atlas Demo

Der lokale Demo-Runner führt Atlas über die Helios Runtime aus und speichert den
erzeugten Trendbericht als Markdown-Datei in einem konfigurierbaren
Obsidian-Vault.

```bash
export HELIOS_OBSIDIAN_VAULT="/vollständiger/pfad/zum/vault"
uv run python scripts/run_atlas_demo.py "AI Agents"
```

Aktuell verwendet Atlas deterministische Mock-Trenddaten und ein Mock-LLM. Es
werden keine echten APIs, keine Netzwerkzugriffe und keine externen LLM-Provider
verwendet.

## Development Workflow

Die verbindlichen Codex-Projektregeln stehen in [AGENTS.md](AGENTS.md).
Der lokale Entwicklungsprozess ist in
[docs/development-workflow.md](docs/development-workflow.md) dokumentiert.

## Architecture and Roadmap

- [System Architecture](docs/system-architecture.md)
- [Technical Roadmap](docs/roadmap.md)
- [Project State](docs/project-state.md)

## Company Architecture

Helios wird als AI Company mit klar definierten Abteilungen aufgebaut. Jeder
zukuenftige Agent repraesentiert eine Abteilung oder operative Rolle innerhalb
dieser Company Architecture.

Die Kommunikation erfolgt nicht direkt zwischen Agenten, sondern ueber Runtime,
Tasks und Events. Wissen wird zentral im Memory gespeichert, damit Ergebnisse,
Entscheidungen und wiederverwendbare Kontexte langfristig verfuegbar bleiben.

Die Company Architecture ist als providerneutrales Metamodell angelegt und auf
langfristige Erweiterbarkeit ausgelegt. Sie beschreibt Rollen und
Verantwortlichkeiten, implementiert aber noch keine produktiven Agenten. Der
aktuelle Blueprint umfasst 31 AgentDefinitionen.
