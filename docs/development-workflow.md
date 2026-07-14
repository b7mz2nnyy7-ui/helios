# Development Workflow

Project Helios nutzt einen kleinen, bewussten Entwicklungsprozess, damit Codex
Tickets eigenstaendig bearbeiten kann, ohne Architekturentscheidungen zu
verwischen.

## Rollen

**Founder**

- definiert Ziele
- priorisiert die naechsten Schritte

**CTO**

- definiert Architektur
- formuliert Engineering-Tickets

**Codex**

- implementiert
- testet
- fuehrt Selbstreview durch
- korrigiert Fehler

## Ablauf

```text
Ziel
-> Ticket
-> Implementierung
-> Tests
-> Selbstreview
-> Korrektur
-> Abschlussmeldung
```

Codex liest zuerst die relevante Projektstruktur, fasst den Scope kurz
zusammen, aendert nur notwendige Dateien und fuehrt danach Tests, Ruff und MyPy
aus. Anschliessend wird der eigene Diff reviewed. Gefundene Probleme werden
korrigiert, bevor das Ticket als abgeschlossen gemeldet wird.

## Menschliche Freigabe

Menschliche Freigabe ist noetig, wenn eine Aufgabe Secrets, produktive Daten,
kostenpflichtige APIs, externe Dienste, Datenbankmigrationen, Git-Historie,
Commits, Pull Requests oder Dateien ausserhalb des Repositorys betrifft.

## Kleine Aenderungen

Aenderungen bleiben klein, damit Verhalten nachvollziehbar bleibt, Tests klar
zuordenbar sind und Fehler schnell gefunden werden koennen. Ein Ticket soll
nicht heimlich neue Features, Refactorings oder Architekturwechsel enthalten.

## Architekturentscheidungen

Architekturentscheidungen bleiben bewusst. Codex darf vorhandene Regeln
anwenden und lokale Verbesserungen vorschlagen, aber neue Kernabstraktionen,
Integrationen oder Automatisierungen gehoeren in eigene Tickets.

## Spaetere Automatisierung

GitHub-Automatisierung, etwa Actions, automatische Pull Requests oder
Review-Workflows, wird spaeter separat ergaenzt. Dieses Dokument beschreibt
zunaechst den lokalen Entwicklungsprozess.
