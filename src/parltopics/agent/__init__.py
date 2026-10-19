"""Agent für Suche und Ad-hoc-Dialog mit Apertus 70B (PRD 7.8, ARCHITEKTUR 4).

`tools`: Argument-Modelle und Definitionen der acht lesenden Werkzeuge. `execute`: die Werkzeuge
auf Datenbank, Registry und Seitenbaum. `loop`: Schleife mit JSON-Protokoll statt Tool-Calling
(ARCHITEKTUR 4.6), Schrittgrenze, Zitatprüfung und Protokoll in agent_runs; die API ruft sie unter
POST /v1/agent/search auf.
"""
