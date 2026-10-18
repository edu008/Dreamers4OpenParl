"""Massenklassifikation durch deterministische Worker (PRD 7.3, 7.7; ARCHITEKTUR 3).

Vorhanden: `schemas` mit den Ausgabemodellen aus PRD Anhang B.
Geplant (M1): `queue` (Jobs öffnen, übernehmen, Heartbeat, Aufräumen, Lauf-Lock),
`worker` (Ablauf je Job mit asyncio), `proposals` (Rohvorschläge gruppieren und prüfen).
"""
