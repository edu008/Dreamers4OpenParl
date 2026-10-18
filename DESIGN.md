---
name: ParlTopics
description: Amtliches Bulletin für Themen-Labels zu Schweizer Parlamentsgeschäften, ruhig, belegt, ohne Dekor.
colors:
  paper: "#f8f9f8"
  ink: "#1b2a27"
  ink-soft: "#55655f"
  surface: "#ffffff"
  margin-tint: "#eff2f0"
  accent-wash: "#e4ece8"
  rule: "#d8dad3"
  field-edge: "#7f8a84"
  forest: "#1f4d3f"
  evidence: "#fff1a8"
  evidence-line: "#b08900"
  level-medium: "#8a5a00"
  level-low: "#9b2c2c"
  night: "#171918"
  night-surface: "#1e2120"
  night-ink: "#e4e6e5"
  night-ink-soft: "#a4aaa7"
  night-rule: "#34383a"
  night-accent: "#a9bfb5"
  night-evidence: "#4a4020"
  night-evidence-line: "#d9b43a"
typography:
  display:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 600
    lineHeight: 1.25
  headline:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.25
  title:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 500
  body:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  reading:
    fontFamily: "Georgia, serif"
    fontSize: "1rem"
    lineHeight: 1.6
  label:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
rounded:
  sm: "2px"
  md: "4px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.forest}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  nav-item-active:
    backgroundColor: "{colors.margin-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
  segmented-active:
    backgroundColor: "{colors.margin-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "32px"
  margin-notes:
    backgroundColor: "{colors.margin-tint}"
    textColor: "{colors.ink}"
    padding: "16px"
  evidence-mark:
    backgroundColor: "{colors.evidence}"
    textColor: "{colors.ink}"
---

# Design System: ParlTopics

## Overview

**Creative North Star: «Das Amtliche Bulletin»**

ParlTopics zeigt, welchen Themen ein Parlamentsgeschäft zugeordnet wurde, und weshalb. Die Oberfläche soll wie ein Bulletin der Bundesversammlung wirken: kühles Papier, dunkle Tinte, Haarlinien, eine einzige Farbe. Gestaltung tritt zurück, Text und Beleg tragen die Seite. Die Zielgruppe (Verwaltungsmitarbeitende, Reviewer, Journalisten) arbeitet damit, sie soll sich nicht beeindruckt fühlen, sondern verlässlich geführt.

Dichte und Takt sind die einer Arbeitsfläche: kleine Schrift in Tabellen und Randspalten, 16 px nur für Fliesstext. Hierarchie entsteht aus Gewicht, Grösse und Abstand, nicht aus Flächen, Schatten oder Farbe. Eine Aussage über das Modell wird nie nur durch Farbe getragen, sondern immer durch ein Wort daneben («hoch», «mittel», «tief», «Beleg nicht im Text gefunden»).

Bestätigte Ablehnungen: kein dunkles Dashboard-Aussehen, kein graues Standard-shadcn, keine Karten um alles, keine vielen Trennlinien, kein dekorativer Verlauf, keine KI-Glanzoptik.

**Key Characteristics:**
- Papier und Tinte, ein Grün, Gelb nur für den Beleg
- Haarlinien statt Flächen, keine Schatten
- Kleine Ecken, Systemschriften (Air-Gap-tauglich, keine externen Ressourcen)
- Jede Zahl hat eine Bezeichnung oder steht in einer Spalte mit Kopf

## Colors

Zurückhaltende Palette mit einer Markenfarbe. Die Dunkelansicht ist ein eigener neutraler Satz, kein Abbild des hellen.

- **Papier** (`#f8f9f8`): Seitengrund, kaum getöntes Kühl-Weiss.
- **Tinte** (`#1b2a27`): Text und Linien mit Gewicht, ein dunkles Grün-Schwarz.
- **Tinte gedämpft** (`#55655f`): Nebentexte und Beschriftungen.
- **Randspalten-Tönung** (`#eff2f0`): Fläche der Randspalte und aktiver Navigationspunkt.
- **Haarlinie** (`#d8dad3`): Tabellen- und Trennlinien.
- **Feldrand** (`#7f8a84`): Rand von Eingabefeldern, mindestens 3:1 gegen Papier.
- **Waldgrün** (`#1f4d3f`): Einzige Markenfarbe. Hauptknopf, Fokus, hohe Konfidenz.
- **Beleggelb** (`#fff1a8`, Linie `#b08900`): ausschliesslich für die markierte Belegstelle im Text.
- **Braun** (`#8a5a00`) und **Rot** (`#9b2c2c`): mittlere und tiefe Konfidenz, «Prüfung nötig».
- **Dunkelansicht:** Grund `#171918`, Fläche `#1e2120`, Text `#e4e6e5`, Linie `#34383a`, Akzent gedämpftes Salbei `#a9bfb5`, Beleg `#4a4020`.

**Code-Namen.** Im Code stehen CSS-Variablen in `web/src/index.css`, Tailwind-Klassen daraus. Neue Farben nur dort anlegen, nie als Hexwert in einer Komponente.

| Name oben | CSS-Variable | Tailwind-Klasse |
|---|---|---|
| Papier | `--background` | `bg-background` |
| Tinte | `--foreground` | `text-foreground` |
| Tinte gedämpft | `--muted-foreground` | `text-muted-foreground` |
| Fläche (Karte, Popover) | `--card` | `bg-card` |
| Randspalten-Tönung | `--margin-tint`, `--secondary`, `--muted` | `bg-margin-tint`, `bg-secondary`, `bg-muted` |
| Akzent-Tönung | `--accent` | `bg-accent` |
| Haarlinie | `--border` | `border-border` |
| Feldrand | `--input` | `border-input` |
| Waldgrün | `--primary`, `--ring` | `bg-primary`, `text-primary`, `ring-ring` |
| Markiergelb | `--evidence`, `--evidence-line` | `bg-evidence`, `border-evidence-line` |
| Konfidenz hoch, mittel, tief | `--level-high`, `--level-medium`, `--level-low` | `text-level-high`, `text-level-medium`, `text-level-low` |
| Fehler | `--destructive` | `text-destructive` |

Die Dunkelansicht überschreibt dieselben Variablen unter `:root[data-theme="dark"]`. Das Attribut setzt ein Skript in `index.html` vor dem ersten Zeichnen, der Schalter im Seitenfuss ändert es. Eigene Dunkel-Sonderfälle mit `dark:` nur, wenn eine Variable nicht reicht.

Regeln: Farbe verstärkt nur, das Wort trägt die Bedeutung. Gelb steht nirgends ausser am Beleg. Grün ist keine Dekofarbe.

## Typography

Systemschrift (`ui-sans-serif, system-ui`) für die Oberfläche, `Georgia` als Platzhalter für Lesetext. Eine eigene, selbst gehostete Schrift ist noch offen und braucht eine Freigabe für den Download.

- **Display** 30 px, 600: Titel der Startseite.
- **Headline** 24 px, 600: Seitentitel.
- **Title** 18 px, 500: Abschnittstitel.
- **Body** 16 px: Fliesstext, Einleitungen, Hilfeseite. Zeilenlänge höchstens 62 bis 68 Zeichen.
- **Label** 12 bis 14 px: Tabellen, Randspalte, Nebenangaben.
- Zahlen in Tabellen sind tabellarisch ausgerichtet (`.tabular`).

## Layout

- Hauptspalte höchstens 56 rem breit (`max-w-4xl`), 24 px seitlicher Rand, 32 px oben und unten. Arbeitstabellen wie die Review-Liste dürfen breiter sein (72 rem, `max-w-6xl`); Lesetext bleibt bei 62 bis 68 Zeichen.
- Geschäftsseite: Text links, Randspalte 14 rem rechts, bei breiten Fenstern mitlaufend (sticky). Auf schmalen Fenstern steht die Randspalte unter dem Text.
- Tabellen mit festen Spaltenbreiten, damit Spalten über Seiten hinweg auf einer Linie bleiben.
- Kopfzeile bricht um: Navigation, Suche, Ansichtsschalter. Seitenfuss trägt den Darstellungsschalter.
- Handybreite 375 px ohne seitliches Überlaufen. Bedienflächen mindestens 24 px hoch (WCAG 2.5.8).

## Elevation & Depth

Flach. Keine Schatten. Tiefe entsteht durch Tönung (Randspalte) und Haarlinien. Hover und aktiver Zustand ändern den Grund leicht, nie die Erhebung.

## Shapes

Kleine Ecken: 2 bis 4 px. Ränder sind 1 px. Knöpfe und Felder sind rechteckig mit leichtem Radius, keine Pillen, keine Kreise ausser den Punkten im Graphen.

## Components

- **Knopf:** Primär in Waldgrün mit weisser Schrift, sonst Umriss oder Geist. Gedrückt/aktiv per `aria-pressed`.
- **Segmentierter Umschalter** (`Segmented`): leise aneinanderliegende Knöpfe, Auswahl durch Tönung und Gewicht, `aria-pressed`, 32 px hoch. Verwendet für die Ansicht (Leser, Admin), Filter und Graph-Ansicht. Der Ansichtsschalter ist eine Demo-Ansicht ohne Zugriffskontrolle; Admin sieht Review und Admin und darf Labels entscheiden. Der Darstellungsschalter im Seitenfuss (Automatisch, Hell, Dunkel) ist die noch leisere Textvariante.
- **Konfidenz:** Zahl mit zwei Stellen, daneben das Wort (hoch ab 0.8, mittel ab 0.6, sonst tief), Farbe verstärkt. In der Randspalte steht «Konfidenz» davor, in Tabellen im Spaltenkopf.
- **Randspalte:** je Label Name, Konfidenz, Zustand des Belegs, Prüfstatus, Modellversion. Technische Angaben eingeklappt. Entscheiden nur in der Prüfansicht.
- **Belegmarkierung:** gelber Grund mit Unterlinie direkt im Originaltext.
- **Tabellen:** Haarlinien zwischen Zeilen, Kopf mit Sortierknopf (`aria-sort`), Sortierknöpfe mit vergrösserter Trefferfläche.
- **Themenbaum:** Bereiche aufklappbar, Zahl der Geschäfte neben dem Namen.
- **Graph:** Punkte in einer Farbe je Bereich, dicke Linie = gemeinsame Geschäfte, Beschriftungen kollidieren nicht, Fokusring bei Tastaturbedienung.
- **Hinweise und Fehler:** schlichte Zeile mit Titel und Erklärung, kein Dekor. Fehlerfarbe nur für echte Fehler.

## Do's and Don'ts

**Do**
- Ein Wort neben jede Zahl und jede Farbe.
- Beleg im Text zeigen, nicht nur behaupten.
- Systemschriften und keine externen Ressourcen (`scripts/check-web-dist.mjs` prüft das).
- Seitentitel setzen, Skip-Link, sichtbarer Fokus, Dunkel- und Handyansicht prüfen.
- Grenzen offen nennen: noch nicht von einem Menschen geprüft, erst wenige Geschäfte klassifiziert.

**Don't**
- Keine Karten um jeden Block, keine Schatten, keine Verläufe.
- Kein Gelb ausser am Beleg, kein Grün als Dekoration.
- Kein grosser Seitenbaum als Graph ohne Zoom oder Filter.
- Keine Rollen vortäuschen: ohne Anmeldung ist «Admin» eine Ansicht, kein Schutz.
- Kein Stand, der nicht stimmt: Zahlen aus echten Daten oder gar nicht anzeigen.

## Handbuch für Weiterbauende

### Bausteine im Code
Zuerst nachsehen, ob es das schon gibt. Pfade unter `web/src/`.

| Baustein | Ort | Wofür |
|---|---|---|
| `Layout` | `components/layout.tsx` | Kopfzeile, Navigation, Skip-Link, Hauptspalte, Seitenfuss; setzt Tab-Titel der festen Seiten |
| `Segmented` | `components/segmented.tsx` | Umschalter mit einer Auswahl; `RoleSwitch` nutzt ihn |
| `ThemeSwitch` | `components/theme-switch.tsx` | Darstellung Automatisch, Hell, Dunkel |
| `Confidence` | `components/confidence.tsx` | Zahl mit Wort (hoch, mittel, tief); `labelled` schreibt «Konfidenz» davor |
| `EvidenceText`, `isEvidenceFound` | `components/evidence-text.tsx` | Originaltext mit markierter Belegstelle |
| `MarginNotes` | `components/margin-notes.tsx` | Randspalte der Geschäftsseite |
| `AffairTable`, `SortHeader`, `PlainHeader` | `components/affair-table.tsx`, `sort-header.tsx` | Tabelle mit festen Spalten und Sortierung (`useSort`) |
| `PageTree`, `PageRow` | `components/page-tree.tsx` | Themenbaum |
| `JobSummary` (`SystemList`, `JobTable`, `ProcessingBadge`) | `components/job-summary.tsx` | Verarbeitungsstand |
| shadcn-Bausteine | `components/ui/` | Button, Alert, Card, Breadcrumb, Skeleton, Badge, Input, Separator. Verwenden, nicht kopieren; Karten sparsam |

Hooks in `hooks/`: `useApi` (Laden, Fehler, Daten), `usePageTitle`, `useSort`, `useReview`, `useReviewQueue`. Typen und `fetchJson` stehen in `lib/api.ts`, Prüfgründe und Schwelle in `lib/label-state.ts`, Zeichnung des Graphen in `lib/graph.ts`.

### Rezept für eine neue Seite
1. Route in `App.tsx`, Seite in `pages/`.
2. Tab-Titel: feste Seiten in `STATIC_TITLES` (`layout.tsx`), dynamische mit `usePageTitle("…")`.
3. Aufbau: `h1` (`font-heading text-2xl font-semibold`), darunter ein kurzer Einleitungssatz in `text-muted-foreground`, nicht breiter als 62 bis 68 Zeichen.
4. Daten über `useApi`. Jede Seite kennt drei Zustände: **Laden** (`Skeleton`), **Fehler** (`Alert` mit Text, was fehlt und was man tun kann) und **leer** (ein erklärender Satz, nie eine leere Fläche).
5. Tabellen mit `colgroup` und festen Breiten, Rahmen mit `overflow-x-auto`, Sortierknopf im Kopf.
6. Prüfen bei 375 px Breite, im Dunkeln und mit der Tastatur. Kein seitliches Überlaufen der Seite.
7. Vor dem Commit im Ordner `web/`: `npx tsc -b`, `npm run lint`, `npm run build`, `node ../scripts/check-web-dist.mjs dist` (verbietet externe Hosts im Bundle).

### Textregeln
- Deutsch, Schweizer Schreibweise (ss statt ß), Du-Form. Anführungszeichen «so».
- Keine internen Begriffe in der Oberfläche (Sidecar, Endpunkt, Worker). Technische Angaben nur eingeklappt oder im Admin-Bereich.
- Zahlen mit Tausendertrenner (`Intl.NumberFormat("de-CH")`, also 1'499), Datum als TT.MM.JJJJ, Konfidenz mit zwei Stellen und Wort.
- Ehrlich benennen, was nicht gesichert ist: «Noch nicht von einem Menschen geprüft», «vorläufig». Nie Zahlen oder Zustände zeigen, die nicht aus den echten Daten stammen.
- Neutral: Themen beschreiben, wovon ein Geschäft handelt, und bewerten keine politische Haltung.

### Zustände
- **Fokus:** Umriss in Waldgrün (globaler Stil in `index.css`), immer sichtbar bei Tastatur. Nie `outline: none` ohne Ersatz.
- **Hover:** Grund leicht tönen (`hover:bg-muted`), Links unterstreichen (`underline-offset-2`).
- **Gewählt oder gedrückt:** `aria-pressed` plus Tönung und Gewicht, nicht nur Farbe.
- **Deaktiviert:** verminderte Deckkraft und ein Hinweis, warum.
- **Fehler:** Text plus `text-destructive`, nie nur Rot.
- **Bedienflächen:** mindestens 24 px hoch, besser 32 px; bei Textlinks `py-1.5` bis `py-2` für die Trefferfläche.
