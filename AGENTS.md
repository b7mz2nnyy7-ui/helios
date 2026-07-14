# Project Helios Agent Rules

## Project

Project Helios ist eine modulare Agent Engine fuer autonome digitale
Organisationen. Der aktuelle Fokus ist die Content-Organisation und Atlas als
Trend Research Agent.

## Architekturregeln

- Engine-Code unter `engine/` darf niemals von `agents/` oder `integrations/`
  abhaengen.
- Agenten duerfen Engine-Abstraktionen verwenden.
- Externe Systeme gehoeren unter `integrations/`.
- Agenten kommunizieren nicht direkt miteinander.
- Kommunikation erfolgt ueber Tasks, Runtime, Capabilities und Events.
- Neue Provider und Tools muessen austauschbar bleiben.
- Keine unnoetigen Abstraktionen oder Features ausserhalb des Tickets.
- Bestehendes Verhalten darf nicht still geaendert werden.
- Aenderungen muessen klein und fokussiert bleiben.

## Arbeitsweise

Fuer jedes neue Ticket soll Codex:

1. Repository und relevante Dateien zuerst lesen.
2. Den Scope des Tickets kurz zusammenfassen.
3. Bestehende Architektur respektieren.
4. Nur notwendige Dateien aendern.
5. Tests ergaenzen oder anpassen.
6. Alle Qualitaetspruefungen ausfuehren.
7. Den eigenen Git-Diff kritisch reviewen.
8. Gefundene Probleme selbst korrigieren.
9. Qualitaetspruefungen erneut ausfuehren.
10. Erst danach die Aufgabe als abgeschlossen melden.

## Qualitaetspruefungen

Verwende standardmaessig:

```bash
uv run --python 3.12 python -m unittest discover -s tests
uv run --python 3.12 --with ruff ruff check .
uv run --python 3.12 --with mypy mypy engine agents integrations scripts tests
```

Falls ein Ordner nicht existiert, soll MyPy nur auf vorhandene Projektordner
angewendet werden.

## Definition of Done

Eine Aufgabe ist nur abgeschlossen, wenn:

- alle Tests gruen sind
- Ruff gruen ist
- MyPy gruen ist
- der eigene Diff reviewed wurde
- keine unbeabsichtigten Aenderungen enthalten sind
- keine offenen Fehler verschwiegen werden

## Ausgabeformat

Nach jedem Ticket nur kompakt ausgeben:

- Umgesetzte Aenderungen
- Geaenderte Dateien
- Testergebnisse
- Ruff-Ergebnis
- MyPy-Ergebnis
- Selbstreview
- Offene Punkte oder Risiken

Nicht automatisch den vollstaendigen Inhalt aller Dateien ausgeben, ausser der
Benutzer verlangt es ausdruecklich.

## Sicherheit

Codex darf nicht ohne ausdrueckliche Freigabe:

- Secrets oder API-Keys erzeugen oder committen
- produktive Daten loeschen
- produktive Dienste veraendern
- kostenpflichtige APIs aktivieren
- Datenbankmigrationen ausfuehren
- Git-Historie ueberschreiben
- force pushen
- Commits oder Pull Requests erstellen
- Dateien ausserhalb des Repositorys veraendern
