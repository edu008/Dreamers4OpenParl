---
name: ParlTopics
description: Swiss Design in Schweizer Rot, Schwarz und Weiss. Eine öffentliche Seite mit einer Aufgabe (Geschäfte finden), ein Admin-Bereich für Review, Themen und Graph.
colors:
  paper: "#ffffff"
  ink: "#111111"
  ink-soft: "#595959"
  tone: "#f2f2f2"
  rule: "#d4d4d4"
  swiss-red: "#da291c"
  swiss-red-hover: "#b51f14"
  evidence: "#fff1a8"
  evidence-line: "#b08900"
  level-high: "#1e6b45"
  level-medium: "#8a5a00"
  level-low: "#4a5a8c"
  night: "#0e0e0e"
  night-tone: "#1c1c1c"
  night-ink: "#f5f5f5"
  night-ink-soft: "#a6a6a6"
  night-rule: "#333333"
  night-red: "#e2231a"
typography:
  display:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "clamp(3rem, 9vw, 6.5rem)"
    fontWeight: 700
    lineHeight: 0.9
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "clamp(1.75rem, 4vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.05
  title:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
  body:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "1rem"
    lineHeight: 1.5
  reading:
    fontFamily: "Georgia, serif"
    fontSize: "17px"
    lineHeight: 1.6
  note:
    fontFamily: "Helvetica Neue, Helvetica, Arial, system-ui, sans-serif"
    fontSize: "0.875rem"
rounded:
  none: "0"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  header-band:
    backgroundColor: "{colors.swiss-red}"
    textColor: "#ffffff"
  button-primary:
    backgroundColor: "{colors.swiss-red}"
    textColor: "#ffffff"
    rounded: "{rounded.none}"
  button-outline:
    border: "1px {colors.ink}"
    hover: "invertiert: {colors.ink} gefüllt, Schrift weiss"
  search-field:
    border: "2px {colors.ink}"
    height: "56px"
  result-row:
    rule: "1px {colors.rule}, Liste oben und unten 2px {colors.ink}"
    grid: "8rem Datum und Parlament | Titel, Angaben, Themen"
  topic-tag:
    border: "1px {colors.ink}"
  topic-filter:
    backgroundColor: "{colors.ink}"
    textColor: "#ffffff"
---

# Design System: ParlTopics

## Overview

**Creative North Star: «Schweizer Plakat»**

Swiss Design im Sinn der Schweizer Typografie: Weiss, Schwarz und Schweizer Rot, Helvetica, ein Raster, linksbündig, grosse Schrift. Keine Rundungen, keine Schatten, keine Verläufe. Linien und Tonstufen ordnen die Seite, das Rot setzt die Marke.

Die öffentliche Seite hat eine Aufgabe: Geschäfte finden (Hick's Law). Ein Suchfeld, ein Knopf, die Filter hinter einem Schalter, darunter die neuesten Geschäfte oder die Treffer. Wer ein Geschäft öffnet, sieht Fakten wie bei OpenParlData (Nummer, Typ, Daten, Quelle, Parlament) und die Themen, aber keine Konfidenz, kein Modell und keinen Prüfstand. Diese Angaben stehen im Admin-Bereich unter `/admin`.

**Key Characteristics:**
- Rotes Kopfband über die ganze Breite, Wortmarke weiss
- Ein Raster, eine linke Kante für Kopf, Inhalt und Fuss
- Helvetica-Stapel aus Systemschriften, ein grosser Titel pro Seite
- Eckig und flach: Rahmen, Linien und Füllungen statt Rundungen und Schatten

## Colors

- **Papier** (`#ffffff`) und **Tinte** (`#111111`): Grund und Schrift.
- **Tinte gedämpft** (`#595959`, 7:1): Nebenangaben.
- **Ton** (`#f2f2f2`): Filterfeld, Randspalte, Hinweise.
- **Linie** (`#d4d4d4`): Trenner zwischen Zeilen. Starke Linien (2 px) in Tinte.
- **Schweizer Rot** (`#da291c`, weisse Schrift 4.9:1): Kopfband, Hauptaktion («Suchen», «Bestätigen»), Fokusring, Hover auf Titeln.
- **Beleggelb** (`#fff1a8`): nur in der Prüfansicht für die Belegstelle.
- **Konfidenz** (nur Admin): hoch Grün, mittel Ocker, tief Schieferblau. Nie Rot.
- **Dunkelansicht:** Grund `#0e0e0e`, Ton `#1c1c1c`, Schrift `#f5f5f5`, Linie `#333333`, Rot `#e2231a`.

## Typography

Helvetica Neue, Helvetica, sonst Arial, alles Systemschriften (keine externen Ressourcen, PRD 9). `Georgia` für den Originaltext eines Geschäfts.

- **Display** `clamp(3rem, 9vw, 6.5rem)`, fett, eng gesetzt: einmal auf der Startseite.
- **Headline** `clamp(1.75rem, 4vw, 3rem)`, fett: Titel eines Geschäfts.
- **Title** 20 px, fett: Titel in der Trefferliste.
- **Body** 16 px, **Note** 14 px. Zeilenlänge höchstens 68 Zeichen.
- Keine kleinen Versalien mit Sperrung, keine Monospace-Schrift. Zahlen tabellarisch (`.tabular`).

## Layout

- Ein Rahmen für Kopf, Inhalt und Fuss: höchstens 64 rem (Review 72 rem), Rand 16 px auf dem Handy, 32 px ab `sm`.
- **Öffentlich:** rotes Kopfband mit Wortmarke. Startseite: Display, ein Satz, Suchfeld mit rotem Knopf, Zeile mit «Filter einblenden (n)» und aktivem Thema, Trefferzahl, Liste. Fuss mit «So funktioniert's» und Darstellungsschalter über einer 2-px-Linie.
- **Trefferliste:** Raster mit zwei Spalten. Links Datum (fett) und Parlament (Kürzel oder Ebene), rechts Typ · Nr. · Parlament, Titel, Ausschnitt bei einer Suche, höchstens drei Themen. Die ganze Zeile ist der Link, der Titel wird beim Hover rot.
- **Geschäftsseite:** Rückweg «← Geschäfte», Meta-Zeile «Geschäft | Nr. | Datum | Typ», Titel, Themen. Darunter Abschnitte im Raster (Titel links, Inhalt rechts): Geschäft (ID, externe ID, Nummer, Titel, langer Titel, Typ, Stand, Beginn, Ende, URL), Text, Gebiet (Parlament, Ebene, Kürzel).
- **Admin:** dieselbe Kopfzeile mit «ParlTopics Admin» und Reitern Übersicht, Review (Anzahl), Themen, Graph; der aktive Reiter ist weiss mit roter Schrift.
- Handybreite 375 px ohne seitliches Überlaufen. Bedienflächen mindestens 32 px hoch.

## Elevation & Depth

Flach. Keine Schatten. Tiefe entsteht durch Tonstufen (Ton auf Papier), Linien und Invertieren (Schwarz gefüllt bei Hover und Auswahl).

## Shapes

Keine Rundungen (`--radius: 0`). Knöpfe, Felder, Themen und Flächen sind Rechtecke. Kreise nur als Punkte im Graphen.

## Components

- **Suchfeld:** 56 px hoch, 2 px schwarzer Rahmen, daneben der rote Knopf «Suchen».
- **Knöpfe:** Hauptaktion rot gefüllt; sonst schwarzer Rahmen, beim Hover schwarz gefüllt.
- **Umschalter:** Felder in einem schwarzen Rahmen, die Auswahl schwarz gefüllt (`aria-pressed`).
- **Themen:** in der Liste Rahmen in Tinte, auf der Geschäftsseite schwarz gefüllt; ein Klick filtert die Suche. Das aktive Thema steht schwarz gefüllt mit «×» und wird beim Hover rot.
- **Hinweise und Fehler:** Tonfläche mit 4-px-Linie links in Tinte.
- **Randspalte (Admin):** je Thema Name, Konfidenz mit Wort, Zustand des Belegs, Prüfstatus, Modell.

## Do's and Don'ts

**Do**
- Eine Aufgabe pro Seite, wenige Wahlmöglichkeiten auf einen Blick (Hick's Law).
- Öffentlich nur Fakten und Themen zeigen; Konfidenz, Modell und Prüfstand gehören ins Admin.
- Systemschriften und keine externen Ressourcen (`scripts/check-web-dist.mjs` prüft das).
- Seitentitel setzen, Skip-Link, sichtbarer Fokus, Dunkel- und Handyansicht prüfen.

**Don't**
- Keine Rundungen, keine Schatten, keine Verläufe, kein Glas.
- Kein Rot für Daten, Konfidenz oder Fehler.
- Keine Kantonswappen (Wappenschutzgesetz), keine Schweizerkreuze als Schmuck.
- Keine Menüpunkte auf der öffentlichen Seite, die nicht zum Finden von Geschäften gehören.
- Keine Rollen vortäuschen: ohne Anmeldung ist `/admin` ein eigener Bereich, kein Schutz.
- Kein Stand, der nicht stimmt: Zahlen aus echten Daten oder gar nicht anzeigen.
