# Stammdaten

<p align="center">
  <img src="docs/img/00-zusammenfassung.png" alt="Zusammenfassung der Profiling-Ergebnisse">
</p>

**Data Quality Dashboard für den Wiener Baumkataster, nach ISO/IEC 25012**

Ein Projekt zur systematischen Prüfung von Datenqualität: von der Rohdatei über regelbasierte Validierung bis zum Dashboard, das Qualitätskennzahlen sichtbar und nachvollziehbar macht.

---

## Datenquelle

**Baumkataster bzw. Bäume Standorte Wien**
Magistrat Wien, Magistratsabteilung 42, Wiener Stadtgärten
Bezogen über [data.gv.at](https://www.data.gv.at)

Lizenz: **CC BY 4.0**. Datenquelle: Stadt Wien, data.wien.gv.at

Umfang: 232.608 Datensätze, 19 Spalten. Die Rohdatei ist bewusst nicht Teil dieses Repositorys, sie wird über das Ladeskript bezogen.

<p align="center">
  <img src="docs/img/01-struktur-datentypen.png" alt="Struktur und Datentypen der eingelesenen Datei">
</p>

---

## Architektur

```
CSV (data.gv.at)
      │
      ▼
  Profiling          01_einlesen.py      pandas
      │
      ▼
  SQL-Analyse        02_profiling.sql    DuckDB
      │
      ▼
  Regelprüfung       03_validierung.py   Great Expectations
      │
      ▼
  Ergebnisdateien    output/*.csv
      │
      ▼
  Dashboard          stammdaten.pbix     Power BI
```

---

## Projektstand

| Schritt | Status |
|---|---|
| Einlesen und Profiling | abgeschlossen |
| SQL-Analyse mit DuckDB | offen |
| Regelprüfung mit Great Expectations | offen |
| Power-BI-Dashboard | offen |

---

## Befunde aus dem Profiling

Die folgenden Beobachtungen stammen aus `src/01_einlesen.py` und bilden die Grundlage für die Prüfregeln.

### 1. Verschleierte Nullwerte

**64.410 Datensätze (27,7 %) enthalten `PFLANZJAHR = 0`**, weitere 3.712 (1,6 %) enthalten `STAMMUMFANG = 0`.

Beide Spalten sind als Integer typisiert und enthalten formal keine NULL-Werte. Eine reine Nullwertprüfung würde sie daher als vollständig ausweisen. Die Begleitspalte `PFLANZJAHR_TXT` weist dieselben Datensätze korrekt als *nicht definiert* aus. Die textuelle Darstellung dokumentiert die Lücke also ehrlich, während die numerische sie verschleiert.

*Konsequenz für die Regeln:* Vollständigkeit wird hier nicht über einen NULL-Check geprüft, sondern über einen Plausibilitätsbereich.

<p align="center">
  <img src="docs/img/02-sentinel-values.png" alt="Verschleierte Nullwerte in PFLANZJAHR und STAMMUMFANG">
</p>

### 2. Verzerrte Kennzahlen als Folge

Die verschleierten Nullwerte machen jede Auswertung der Spalte unbrauchbar. Ungefiltert ergibt sich ein durchschnittliches Pflanzjahr von **1442** bei einem Median von 1985. Nach Ausschluss der Nullwerte liegt der Mittelwert bei **1994**, der Median bei 2001.

Bemerkenswert ist der Unterschied im Verhalten der beiden Kennzahlen: Der Mittelwert bricht um über 550 Jahre ein, während sich der Median nur um 16 Jahre verschiebt. Der Median ist gegenüber Sentinel Values deutlich robuster und eignet sich damit besser für automatisierte Plausibilitätsprüfungen als der Mittelwert.

<p align="center">
  <img src="docs/img/03-wertebereich-pflanzjahr.png" alt="Wertebereich von PFLANZJAHR mit und ohne Nullwerte">
</p>

### 3. Technischer und fachlicher Schlüssel

`BAUM_ID` ist über alle 232.608 Datensätze eindeutig. `BAUMNUMMER` weist 217.831 Duplikate bei nur 14.777 verschiedenen Werten auf und ist damit kein globaler Schlüssel, sondern ein fachliches Label innerhalb einer Straße oder eines Bezirks.

*Konsequenz für die Regeln:* Eindeutigkeit wird auf `BAUM_ID` geprüft. Eine Prüfung auf `BAUMNUMMER` würde über 200.000 Falschmeldungen erzeugen.

### 4. Uneinheitliche Formatierung

**17.009 Werte in `BAUMNUMMER` (7,3 %) sind nicht rein numerisch.** Das erklärt, warum die Spalte als Text eingelesen wird, obwohl die Mehrzahl der Werte wie Zahlen aussieht.

<p align="center">
  <img src="docs/img/04-schluesselkandidaten.png" alt="Duplikatanalyse für BAUM_ID und BAUMNUMMER">
</p>

### 5. Fehlende Bezirkszuordnung

**595 Datensätze haben keinen Bezirk.** Erkennbar bereits am Datentyp: `BEZIRK` wird als `float64` gelesen, weil pandas Integer-Spalten mit Nullwerten auf Fließkomma umstellt.

<p align="center">
  <img src="docs/img/05-fehlende-werte.png" alt="Übersicht der echten NULL-Werte je Spalte">
</p>

### 6. Spalten ohne Informationsgehalt

`DATENFUEHRUNG` enthält für alle Datensätze denselben Wert. `SE_ANNO_CAD_DATA` ist vollständig leer. Beide tragen nichts zur Auswertung bei.

<p align="center">
  <img src="docs/img/06-zero-variance.png" alt="Spalten ohne Informationsgehalt">
</p>

### 7. Abweichung zwischen Metadaten und Datenbestand

Die offizielle Attributbeschreibung auf data.gv.at führt die Spalten `BAUM_ID`, `DATENFUEHRUNG`, `SHAPE`, `FID`, `OBJECTID` und `SE_ANNO_CAD_DATA` nicht auf, obwohl sie im Datenbestand vorhanden sind. Die Lücke zwischen Dokumentation und Realität ist selbst ein Qualitätsbefund.

### 8. Abweichende Platzhaltertexte

Die Datenbeschreibung gibt an, unbekannte Werte würden in den Text *nicht bekannt* umgewandelt. Tatsächlich enthalten alle 64.410 betroffenen Datensätze den Wert *nicht definiert*. Eine Prüfregel, die sich auf die dokumentierte Schreibweise stützt, würde ins Leere laufen.

*Konsequenz für die Regeln:* Platzhaltertexte werden aus dem Datenbestand abgeleitet, nicht aus der Dokumentation übernommen.

### 9. Auswirkung willkürlicher Schwellenwerte

Die zunächst gewählte Untergrenze von 1800 schloss 18 Datensätze mit Pflanzjahren zwischen 1658 und 1796 aus. Ein Häufungspunkt auf dem Schwellenwert selbst besteht nicht, auf genau 1800 liegt lediglich ein einziger Datensatz. Es handelt sich also nicht um einen weiteren Sentinel Value, sondern um reale Randfälle. Für Wien sind Pflanzjahre im 18. Jahrhundert plausibel, etwa im Augarten oder in Schönbrunn. Die Grenze wurde daraufhin auf 1650 gesenkt.

Der Fall zeigt, dass Prüfregeln selbst eine Fehlerquelle sind: Ein nicht begründeter Schwellenwert erzeugt stille Datenverluste, die in keiner Fehlerstatistik auftauchen.

---

## Geplante Prüfregeln

Zuordnung zu den inhärenten Datenqualitätsmerkmalen nach ISO/IEC 25012.

| # | Regel | Spalte | Dimension |
|---|---|---|---|
| R01 | Wert im Bereich 1650 bis 2026 | PFLANZJAHR | Vollständigkeit |
| R02 | Wert größer 0 | STAMMUMFANG | Vollständigkeit |
| R03 | Darf nicht leer sein | BEZIRK | Vollständigkeit |
| R04 | Darf nicht leer sein | GATTUNG_ART | Vollständigkeit |
| R05 | Wert im Bereich 1 bis 23 | BEZIRK | Genauigkeit |
| R06 | Wert im Bereich 0 bis 1000 cm | STAMMUMFANG | Genauigkeit |
| R07 | Kategorie aus definierter Liste | BAUMHOEHE | Genauigkeit |
| R08 | Eindeutigkeit | BAUM_ID | Genauigkeit |
| R09 | Koordinaten innerhalb Wien | SHAPE | Genauigkeit |
| R10 | Übereinstimmung mit PFLANZJAHR_TXT | PFLANZJAHR | Konsistenz |
| R11 | Übereinstimmung mit STAMMUMFANG_TXT | STAMMUMFANG | Konsistenz |
| R12 | Einheitliches Format | BAUMNUMMER | Konsistenz |
| R13 | Pflanzjahr ab 2006, davor geschätzt | PFLANZJAHR | Glaubwürdigkeit |

R13 kennzeichnet keinen Fehler, sondern eine Konfidenzstufe: Laut Datenbeschreibung der Stadt Wien wurde das Baumalter vor 2006 aus dem Stammumfang geschätzt und ist erst danach exakt erfasst.

---

## Verwendung

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python src/01_einlesen.py
```

Die Rohdatei wird unter `data/raw/baumkataster.csv` erwartet.

---

## Technologie

Python (pandas), DuckDB, Great Expectations, Power BI
