# ADR 0006: Web-App als React-SPA mit shadcn/ui, ausgeliefert von FastAPI

- Status: angenommen
- Datum: 18.10.2026
- Bezug: PRD 5, 7.5, 9, 10.1, F13; ersetzt den Web-App-Stack aus PRD 0.3 (FastAPI mit Jinja2)

## Kontext

PRD 0.3 sah eine serverseitig gerenderte Web-App vor: FastAPI, Jinja2, eigenes CSS, JavaScript nur für Graph und kleine Interaktionen. Das Team will als Frontend React mit shadcn/ui. Die Web-App ist interaktiv: Review direkt auf der Seite, Graph, Navigationssuche mit Suchweg, Seitenbaum. Sie muss ohne Internet laufen und darf nichts von einem CDN laden (PRD 9).

## Entscheid

- Die Web-App ist eine Single-Page-App in `web/`: React, TypeScript, Vite, Tailwind CSS v4, shadcn/ui mit Base UI (Stil nova), React Router.
- FastAPI liefert den statischen Build aus `web/dist` aus. Alle Pfade ausserhalb von `/v1` bekommen `index.html`, damit jede Route auch beim Neuladen funktioniert. Fehlende Dateien unter `/assets/` und unbekannte API-Pfade bleiben 404.
- Daten kommen nur über die Sidecar-API (F10). Es gibt keinen zweiten Server.
- Node 22 und npm braucht nur der Build. Das App-Image und das Air-Gap-Bundle enthalten den fertigen Build.
- Systemschriften, keine Web-Fonts. `scripts/check-web-dist.mjs` bricht den Build ab, wenn eine URL zu einem nicht erlaubten Host auftaucht.
- shadcn-Komponenten kommen über die CLI ins Repo und liegen als Quellcode in `web/src/components/ui/`.

## Folgen

- Review, Graph und Suche lassen sich als interaktive Oberfläche bauen, ohne eigenes Frontend-Gerüst.
- Komponenten sind Quellcode im Repo und lassen sich anpassen; es gibt keine Laufzeitabhängigkeit von einem UI-Dienst.
- Zusätzliche Toolchain: Node 22, `web/package-lock.json`, eigener CI-Job `web`. Lizenzen der Laufzeitpakete: MIT, dazu class-variance-authority (Apache-2.0) und Lucide (ISC).
- Ein Neubau des Frontends im Air-Gap ist nicht vorgesehen, weil er die npm-Registry bräuchte.
- Die Sidecar-API wird zur einzigen Schnittstelle der Oberfläche; neue Ansichten brauchen passende Endpunkte.
- Keine serverseitige Darstellung und keine Suchmaschinen-Optimierung; für eine interne Instanz ist das nicht nötig.

## Verworfene Alternativen

- **FastAPI mit Jinja2 (PRD 0.3):** weniger Werkzeuge, aber Review, Graph und Suche wären mit eigenem JavaScript mühsamer, und das Team wünscht React mit shadcn/ui.
- **Next.js oder React Router mit eigenem Server:** ein zweiter Laufzeitdienst mit Node. Das widerspricht dem Ziel, Node nur zur Build-Zeit zu brauchen.
- **Vite-Entwicklungsserver im Betrieb:** nicht für den Betrieb gedacht.
