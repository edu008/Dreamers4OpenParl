"""Volltextsuche, Trigramm-Kandidaten und Navigationssuche (PRD 7.4, 7.6, 7.10).

`navigate`: Schleife, Grenzen, Rückweg und Fallback der Navigationssuche, ohne DB und LLM; die
Anbindung steht in `api/navigate.py`. Die Volltextsuche (GET /v1/search) liegt in `api/queries.py`,
die Trigramm-Kandidaten für Tag-Vorschläge in `classify/proposals.py`.
"""
