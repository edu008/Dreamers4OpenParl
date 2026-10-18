# web – Web-App von ParlTopics

React-SPA mit Vite, TypeScript, Tailwind CSS v4 und shadcn/ui (Base UI, Stil nova). FastAPI liefert
den Build aus `web/dist` aus (ADR 0006). Zur Laufzeit braucht die App weder Node noch Internet.

```bash
make web-dev     # Vite auf http://127.0.0.1:5173, /v1 und /healthz gehen an FastAPI (make api)
make web-build   # npm ci und Build nach web/dist
make web-check   # Lint, Typprüfung, Build, Prüfung auf externe URLs
```

Komponenten kommen über die shadcn-CLI dazu, zum Beispiel `npx shadcn add table`. Die App nutzt
Systemschriften (PRD 9); Symbole (Lucide) werden mitgebündelt, nichts wird von einem CDN geladen.
Details in `docs/ENTWICKLUNG.md`.
