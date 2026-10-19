"""Massenklassifikation durch deterministische Worker (PRD 7.3, 7.7; ARCHITEKTUR 3).

Vorhanden: `schemas` (Ausgabemodelle aus PRD Anhang B), `queue` (Jobs öffnen, übernehmen,
Heartbeat, Aufräumen, Lauf-Lock, Ergebnis schreiben), `worker` (Ablauf je Job mit asyncio),
`proposals` (Rohvorschläge gruppieren und mit 70B prüfen), `adhoc` (Stichwörter, Kandidaten, Jobs).
"""
