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

- Hauptspalte höchstens 56 rem breit, 24 px seitlicher Rand, 32 px oben und unten.
- Geschäftsseite: Text links, Randspalte 14 rem rechts, bei breiten Fenstern mitlaufend (sticky). Auf schmalen Fenstern steht die Randspalte unter dem Text.
- Tabellen mit festen Spaltenbreiten, damit Spalten über Seiten hinweg auf einer Linie bleiben.
- Zwei Bereiche mit eigener Navigation: die öffentliche Seite unter `/` (Themen, Graph, So funktioniert's; rein lesend) und der Admin-Bereich unter `/admin` (Übersicht, Review). Die öffentliche Seite verlinkt nicht in den Admin-Bereich; der Admin-Bereich hat einen Link «Öffentliche Seite».
- Kopfzeile bricht um: Navigation, Suche (öffentlich) oder Link zur öffentlichen Seite (Admin). Seitenfuss trägt den Darstellungsschalter.
- Handybreite 375 px ohne seitliches Überlaufen. Bedienflächen mindestens 24 px hoch (WCAG 2.5.8).

## Elevation & Depth

Flach. Keine Schatten. Tiefe entsteht durch Tönung (Randspalte) und Haarlinien. Hover und aktiver Zustand ändern den Grund leicht, nie die Erhebung.

## Shapes

Kleine Ecken: 2 bis 4 px. Ränder sind 1 px. Knöpfe und Felder sind rechteckig mit leichtem Radius, keine Pillen, keine Kreise ausser den Punkten im Graphen.

## Components

- **Knopf:** Primär in Waldgrün mit weisser Schrift, sonst Umriss oder Geist. Gedrückt/aktiv per `aria-pressed`.
- **Darstellungsschalter:** leise segmentierte Knöpfe, Auswahl durch Tönung und Gewicht.
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
- Keine Rollen vortäuschen: ohne Anmeldung ist `/admin` ein eigener Bereich, kein Schutz.
- Kein Stand, der nicht stimmt: Zahlen aus echten Daten oder gar nicht anzeigen.
