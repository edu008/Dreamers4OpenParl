---
name: ParlTopics
description: Schweizer Raster mit Oberflächen aus Ton. Eine öffentliche Seite mit einer Aufgabe (Geschäfte finden), ein Admin-Bereich für Review, Themen und Graph.
colors:
  ground: "#f1f1ee"
  surface: "#fbfbf9"
  well: "#e6e6e2"
  ink: "#141414"
  ink-soft: "#5c5c58"
  rule: "#dcdcd7"
  field-edge: "#8a8a85"
  swiss-red: "#dc0018"
  swiss-red-hover: "#b80014"
  evidence: "#fff1a8"
  evidence-line: "#b08900"
  level-high: "#1e6b45"
  level-medium: "#8a5a00"
  level-low: "#4a5a8c"
  data: "#3a3a37"
  night: "#18191b"
  night-surface: "#222326"
  night-well: "#2b2c30"
  night-ink: "#f2f2ef"
  night-ink-soft: "#a9a9a4"
  night-ring: "#ff5a5f"
  night-evidence: "#4a4020"
  night-evidence-line: "#d9b43a"
typography:
  display:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "clamp(2.5rem, 7vw, 5rem)"
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1.15
  title:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
  body:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  lead:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "1.25rem"
    lineHeight: 1.6
  reading:
    fontFamily: "Georgia, serif"
    fontSize: "1rem"
    lineHeight: 1.6
  note:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "0.875rem"
rounded:
  pill: "9999px"
  clay: "24px"
  md: "16px"
shadows:
  clay: "aussen weich 0 10px 24px, innen Licht oben, innen Schatten unten"
  clay-raised: "wie clay, aussen weiter und dunkler (Hover)"
  clay-pressed: "nur innen: Schatten oben, Licht unten (Felder, Mulden, gedrückt)"
  clay-primary: "rot getönter Aussenschatten, innen Licht und Schatten (Hauptaktion)"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.swiss-red}"
    textColor: "#ffffff"
    rounded: "{rounded.pill}"
    shadow: "{shadows.clay-primary}"
  search-field:
    backgroundColor: "{colors.well}"
    rounded: "{rounded.pill}"
    shadow: "{shadows.clay-pressed}"
    height: "56px"
  affair-card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.clay}"
    shadow: "{shadows.clay}"
    padding: "24px"
  topic-chip:
    backgroundColor: "{colors.well}"
    rounded: "{rounded.pill}"
    shadow: "{shadows.clay-pressed}"
  segmented:
    backgroundColor: "{colors.well}"
    selected: "{colors.surface} mit {shadows.clay}"
  evidence-mark:
    backgroundColor: "{colors.evidence}"
    textColor: "{colors.ink}"
---

# Design System: ParlTopics

## Overview

**Creative North Star: «Schweizer Raster, Oberflächen aus Ton»**

ParlTopics zeigt, welchen Themen ein Parlamentsgeschäft zugeordnet wurde, und weshalb. Die Gestaltung folgt dem Swiss Design: ein Raster, linksbündig, Helvetica, wenige grosse Schriftgrade, Rot als einziger Akzent. Die Flächen sind aus Ton (Claymorphism): weich, plastisch, mit Licht oben und Schatten unten. So wirkt die Seite ruhig und greifbar, ohne Dekor.

Die öffentliche Seite hat eine Aufgabe: Geschäfte finden (Hick's Law). Ein Suchfeld, ein Knopf, die Filter hinter einem Schalter, darunter die neuesten Geschäfte oder die Treffer. Alles andere (Review, Themenbaum, Graph, Systemstand) liegt im Admin-Bereich unter `/admin`.

Eine Aussage über das Modell wird nie nur durch Farbe getragen, sondern immer durch ein Wort daneben («hoch», «mittel», «tief», «Beleg nicht im Text gefunden»).

**Key Characteristics:**
- Ein Raster, eine linke Kante für Kopf, Inhalt und Fuss
- Helvetica-Stapel aus Systemschriften, ein grosser Titel pro Seite
- Schweizer Rot nur für die Hauptaktion und den Fokus
- Clay-Flächen: Karten erhaben, Felder und Mulden eingedrückt
- Gelb nur für den Beleg

## Colors

- **Grund** (`#f1f1ee`): heller, warmer Ton als Seitengrund.
- **Fläche** (`#fbfbf9`): Karten, Filterfeld, Randspalte.
- **Mulde** (`#e6e6e2`): Suchfeld, Chips, Umschalter, Seitenfuss.
- **Tinte** (`#141414`) und **Tinte gedämpft** (`#5c5c58`, etwa 6:1): Text und Nebenangaben.
- **Feldrand** (`#8a8a85`): Rand von Eingabefeldern, mindestens 3:1 gegen den Grund.
- **Schweizer Rot** (`#dc0018`, weisse Schrift 5.2:1): einzige Akzentfarbe. Hauptaktion («Suchen», «Bestätigen») und Fokusring.
- **Beleggelb** (`#fff1a8`, Linie `#b08900`): ausschliesslich für die markierte Belegstelle im Text.
- **Konfidenz:** hoch Grün (`#1e6b45`), mittel Ocker (`#8a5a00`), tief Schieferblau (`#4a5a8c`). Nie Rot.
- **Daten** (`#3a3a37`): Balken in Auswertungen und Fortschritt, nie Rot.
- **Fehler** in Tinte: das Wort trägt die Meldung, Rot bleibt bei der Hauptaktion.
- **Dunkelansicht:** Grund `#18191b`, Fläche `#222326`, Mulde `#2b2c30`, Text `#f2f2ef`, Fokus `#ff5a5f`, Beleg `#4a4020`. Clay-Schatten dunkler, Licht innen schwach.

Regeln: Rot hat eine Bedeutung. Farbe verstärkt nur, das Wort trägt die Bedeutung. Gelb steht nirgends ausser am Beleg.

## Typography

Helvetica Neue, Helvetica, sonst Arial, alles Systemschriften (keine externen Ressourcen, PRD 9). `Georgia` bleibt Platzhalter für den Originaltext eines Geschäfts.

- **Display** `clamp(2.5rem, 7vw, 5rem)`, 700, eng gesetzt (-0.035em): einmal pro Seite, höchstens zwei Zeilen auch auf dem Handy.
- **Headline** 30 px, 700: Titel eines Geschäfts.
- **Title** 20 px, 600: Titel in Karten.
- **Lead** 20 px: ein Satz unter dem Display.
- **Body** 16 px, **Note** 14 px: Fliesstext und Nebenangaben. Zeilenlänge höchstens 62 bis 68 Zeichen.
- Keine kleinen Versalien mit Sperrung, keine Monospace-Schrift. Zahlen tabellarisch (`.tabular`).

## Layout

- Ein Rahmen für Kopf, Inhalt und Fuss: höchstens 64 rem (Review 72 rem), Rand 16 px auf dem Handy, 32 px ab `sm`.
- **Öffentlich:** Kopf nur mit Wortmarke. Startseite: Display, Lead, Suchfeld, Zeile mit «Filter einblenden (n)», aktivem Thema und Trefferzahl, darunter die Liste. Fuss mit «So funktioniert's» und dem Darstellungsschalter.
- **Admin:** Wortmarke «ParlTopics Admin», Navigation Übersicht, Review (offene Anzahl), Themen, Graph in einer Mulde, rechts «Öffentliche Seite».
- Geschäftsseite: Text als Clay-Fläche links, Randspalte 16 rem rechts, bei breiten Fenstern mitlaufend (sticky); auf schmalen Fenstern darunter.
- Handybreite 375 px ohne seitliches Überlaufen. Bedienflächen mindestens 32 px hoch.

## Elevation & Depth

Clay in drei Zuständen, als Variablen in `web/src/index.css`:

- **Ruhe** (`shadow-clay`): weicher Aussenschatten, Licht innen oben, Schatten innen unten. Karten, Filterfeld, Randspalte.
- **Angehoben** (`shadow-clay-raised`): beim Hover, dazu höchstens 2 px nach oben (`motion-safe`).
- **Eingedrückt** (`shadow-clay-pressed`): Suchfeld, Chips, Umschalter-Mulde, gedrückter Knopf.
- **Hauptaktion** (`shadow-clay-primary`): roter Knopf mit rot getöntem Aussenschatten.

Bewegung nur mit `motion-safe:`; bei `prefers-reduced-motion` fallen Wege und Übergänge weg, der Inhalt bleibt.

## Shapes

Pillen (`rounded-full`) für Knöpfe, Felder, Chips und Umschalter. Karten und Flächen 24 px (`rounded-clay`), kleine Kacheln 16 px. Keine Haarlinien als Trenner: Abstand und Tonstufen trennen. Tabellen im Admin behalten ihre Linien.

## Components

- **Suchfeld:** eine Mulde, 56 px hoch, daneben der rote Knopf «Suchen». Leer abgeschickt zeigt die Seite wieder die neuesten Geschäfte.
- **Filter:** ein Schalter «Filter einblenden (n)», darunter eine Clay-Fläche mit Ebene und Sprache (Umschalter), Parlament (Auswahl, nach Ebene gruppiert), Zeitraum (von, bis). «Filter zurücksetzen» erscheint nur bei aktiven Filtern.
- **Geschäftskarte:** die ganze Karte ist der Link. Meta-Zeile (Typ · Nr. · Datum · Parlament), Titel, Ausschnitt mit Treffern bei einer Suche, höchstens drei Themen-Chips mit Konfidenz und «+n weitere». Rechts eine Kachel mit dem Kürzel (CHE, ZH; bei Städten und Gemeinden die Ebene).
- **Themen-Chip:** Name und Konfidenz; ein Klick filtert die Suche nach diesem Thema. Das aktive Thema steht als entfernbarer Chip «Thema: Name ×».
- **Konfidenz:** Zahl mit zwei Stellen, daneben das Wort (hoch ab 0.8, mittel ab 0.6, sonst tief), Farbe verstärkt.
- **Randspalte:** je Thema Name (öffentlich ein Link zur Suche), Konfidenz, Zustand des Belegs, Prüfstatus, Modell. Entscheiden nur unter `/admin/review`.
- **Belegmarkierung:** gelber Grund mit Unterlinie direkt im Originaltext.
- **Umschalter (Segmented):** Mulde, die Auswahl liegt erhaben darin (`aria-pressed`).
- **Hinweise und Fehler:** Clay-Fläche mit Titel und Erklärung, Text in Tinte.

## Do's and Don'ts

**Do**
- Eine Aufgabe pro Seite, wenige Wahlmöglichkeiten auf einen Blick (Hick's Law).
- Ein Wort neben jede Zahl und jede Farbe.
- Beleg im Text zeigen, nicht nur behaupten.
- Systemschriften und keine externen Ressourcen (`scripts/check-web-dist.mjs` prüft das).
- Seitentitel setzen, Skip-Link, sichtbarer Fokus, Dunkel- und Handyansicht prüfen.
- Grenzen offen nennen: noch nicht von einem Menschen geprüft, erst ein Teil der Geschäfte klassifiziert.

**Don't**
- Kein Rot ausser für die Hauptaktion und den Fokus, keine roten Datenbalken, keine rote Konfidenz.
- Kein Gelb ausser am Beleg.
- Keine Verläufe, kein Glas, keine Haarlinien als Dekor.
- Keine Kantonswappen (Wappenschutzgesetz), keine Schweizerkreuze als Schmuck.
- Keine Menüpunkte auf der öffentlichen Seite, die nicht zum Finden von Geschäften gehören.
- Keine Rollen vortäuschen: ohne Anmeldung ist `/admin` ein eigener Bereich, kein Schutz.
- Kein Stand, der nicht stimmt: Zahlen aus echten Daten oder gar nicht anzeigen.
