# Saugroboter-Automatik mit Home Assistant

## Ziel

Der Saugroboter bleibt jederzeit manuell ueber die Hersteller-App steuerbar.
Zusaetzlich soll Home Assistant automatische Reinigungen starten, wenn die Bedingungen passen.

## Kernregeln

1. Manuelle Steuerung hat immer Vorrang.
2. Automatik startet nur, wenn keine manuelle Reinigung laeuft.
3. Auto-Reinigung nur zwischen `08:00` und `22:00`.
4. Ein Lauf startet nur, wenn er sicher vor `22:00` beendet werden kann.
5. Alle `30 Minuten` wird geprueft, ob Reinigung sinnvoll ist.
6. Zeitbudget basiert auf Rueckreisezeit und Restzeit bis 22:00.
7. Wenn die Person schneller zurueckkommt als erwartet, wird ein Auto-Lauf abgebrochen.
8. Reisemodus: Nach `24h` ausserhalb des Berlin-Radius wird die Automatik deaktiviert.
9. Bei Rueckkehr in den Berlin-Radius wird die Automatik wieder aktiviert.

## Praesenz- und Radiuslogik

- Wohnungspraesenz (fuer Putzentscheidungen): ueber `FRITZ!Box Tools` (home/away an der Wohnung).
- Stadt-Radius (fuer Reisemodus): eigener Radius/Zone fuer Berlin.
- Bedeutung:
  - `Wohnung verlassen`: Auto-Reinigung darf geprueft werden.
  - `Berlin verlassen >24h`: Reisemodus aktivieren (Auto aus).
  - `Wieder in Berlin`: Reisemodus beenden (Auto wieder an).

## Raumintervalle (Kalendertage)

- Bad: taeglich (1 Kalendertag)
- Kueche: alle 2 Kalendertage
- Wohnzimmer: alle 3 Kalendertage
- Schlafzimmer: alle 3 Kalendertage

## Intervallmodell

- Intervall-Logik gilt in Kalendertagen, nicht als striktes 24h-Rolling.
- Dadurch haengt ein Raum nicht an der exakten Uhrzeit der letzten Reinigung.
- Beispiel: Reinigung heute 18:00 -> Bewertung startet am naechsten Kalendertag neu.

## Score-Modell (v1)

### Formeln

- `score = stunden_seit_letzter_reinigung / intervall_h`
- `forecast_buffer_h = min(max(reisezeit_h * 0.25, 0.5), 2.0)`
- `score_forecast = (stunden_seit_letzter_reinigung + forecast_buffer_h) / intervall_h`
- `score_forecast_capped = min(score_forecast, 2.0)`

### Intervallstunden

- Bad: `24h`
- Kueche: `48h`
- Wohnzimmer: `72h`
- Schlafzimmer: `72h`

### Gewichte (Startwerte)

- Bad: `1.40`
- Kueche: `1.20`
- Wohnzimmer: `1.00`
- Schlafzimmer: `1.00`

### Auswahl und Priorisierung

- Raum wird nur betrachtet, wenn `score >= 0.8` oder `score_forecast >= 1.0`.
- Ueberfaellige Raeume (`score_forecast >= 1.0`) werden immer vor nicht ueberfaelligen Raeumen einsortiert.
- Innerhalb derselben Stufe:
  - zuerst nach `score_forecast_capped` absteigend
  - dann Gewicht als Feintuning
  - dann kuerzere Reinigungsdauer zuerst
- Prioritaetsformel innerhalb derselben Stufe:
  - `priority = score_forecast_capped + (gewicht - 1.0) * 0.2`
- Ergebnis: Gewicht hilft bei knappen Entscheidungen, kann aber nicht dominieren.

### Zeitbudget-Regel

- `verfuegbare_zeit_min = min(restzeit_bis_22_uhr_min, reisezeit_h * 60)`
- Es werden nur Raeume eingeplant, deren kumulierte Dauer in dieses Budget passt.

## Laufverhalten und Geraetestatus (Dreame)

- Ein Service-Call `dreame_vacuum.vacuum_clean_segment` mit mehreren Segmenten (z. B. `[bad, kueche]`) gilt als ein gemeinsamer Auftrag.
- Neue Segment-Calls werden nur gestartet, wenn der Roboter nicht aktiv reinigt.
- Solange der Roboter `cleaning` ist, wird kein neuer Segment-Call gesendet.
- Neue Planung/Start ist erst wieder bei `idle` oder `docked` erlaubt.
- Dadurch werden laufende Auftraege nicht ueberschrieben oder ungewollt unterbrochen.
- Wenn im spaeteren 30-Minuten-Check mehr Zeitbudget verfuegbar ist, werden zusaetzliche Raeume erst als naechster Auftrag gestartet (nicht in den laufenden Auftrag injiziert).

## Push bei Rueckkehr

- Trigger: Person wechselt auf `home` (Wohnungspraesenz).
- Inhalt: Zusammenfassung aller seit Abwesenheitsbeginn gereinigten Raeume.
- Deduplizierung: Jeder Raum kommt maximal einmal vor.
- Beispiel: Statt `Bad, Bad, Kueche` wird `Bad, Kueche` gesendet.
- Es gibt keine zusaetzlichen Pushes bei Start/Stopp/Abbruch.

## Technische Vorgaben

1. Reisezeit-Berechnung: `Waze Travel Time` in Home Assistant.
2. Zuhause/Abwesend-Erkennung: `FRITZ!Box Tools` (Device Tracker / Presence).
3. Saugroboter-Integration: `Tasshack/dreame-vacuum`.
4. Reisemodus-Radius: Berlin als eigene Zone/Radius in Home Assistant.
5. Quelle: `https://github.com/Tasshack/dreame-vacuum`

## Noch offen

1. Sollen Gewichte/Forecast-Startwerte nach 1-2 Wochen Laufzeit angepasst werden?
2. Optional: Ab welcher Differenz gelten Scores als "aehnlich" fuer den Tie-Break (z. B. `<= 0.1`)?
