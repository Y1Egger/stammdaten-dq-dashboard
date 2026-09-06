"""
Stammdaten - Data Quality Dashboard
Schritt 3: Regelpruefung mit Great Expectations

Prueft 14 Regeln, die den inhaerenten Datenqualitaetsmerkmalen nach
ISO/IEC 25012 zugeordnet sind, und schreibt zwei Ergebnisdateien:

  output/dq_results.csv   eine Zeile je Regel
  output/dq_fehler.csv    eine Zeile je fehlerhaftem Datensatz

Datenquelle: Stadt Wien - data.wien.gv.at (CC BY 4.0)
"""

import contextlib
import io
from datetime import datetime
from pathlib import Path

import pandas as pd
import great_expectations as gx
import great_expectations.expectations as gxe

BASIS = Path(__file__).parent.parent
PFAD_ROH = BASIS / "data" / "raw" / "baumkataster.csv"
PFAD_OUT = BASIS / "output"
PFAD_OUT.mkdir(exist_ok=True)

JAHR_MIN, JAHR_MAX = 1650, 2026
STATUS_JUNGBAUM = "Jungbaum wird gepflanzt"
PLATZHALTER = "nicht definiert"
MAX_FEHLER_JE_REGEL = 500

# Bounding Box Wien, WGS84
LON_MIN, LON_MAX = 16.18, 16.58
LAT_MIN, LAT_MAX = 48.11, 48.33

LAUF = datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------
# 1  Laden und aufbereiten
# ---------------------------------------------------------------------

def laden():
    try:
        df = pd.read_csv(PFAD_ROH, sep=",", encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(PFAD_ROH, sep=",", encoding="cp1252")
    return df


def aufbereiten(df):
    """
    Erzeugt Hilfsspalten fuer die Konsistenz- und Formatpruefungen und
    entfernt Datensaetze mit Status 'Jungbaum wird gepflanzt'.

    Begruendung fuer den Ausschluss: Bei noch nicht gepflanzten Baeumen
    sind fehlende Messwerte fachlich korrekt. Ohne diesen Filter wuerden
    die Vollstaendigkeitsregeln Falschmeldungen erzeugen.
    """
    vorher = len(df)
    df = df.loc[df["GATTUNG_ART"] != STATUS_JUNGBAUM].copy()
    ausgeschlossen = vorher - len(df)

    # Konsistenz: TXT-Spalten auf die numerische Darstellung normalisieren
    df["_pflanzjahr_aus_txt"] = (
        df["PFLANZJAHR_TXT"]
        .replace(PLATZHALTER, "0")
        .astype(str)
        .str.extract(r"(\d+)")[0]
        .fillna("0")
        .astype(int)
    )
    df["_stammumfang_aus_txt"] = (
        df["STAMMUMFANG_TXT"]
        .replace(PLATZHALTER, "0")
        .astype(str)
        .str.extract(r"(\d+)")[0]
        .fillna("0")
        .astype(int)
    )

    # Genauigkeit: Koordinaten aus dem SHAPE-Text loesen
    koord = df["SHAPE"].astype(str).str.extract(
        r"POINT \(([-\d.]+) ([-\d.]+)\)"
    )
    df["_lon"] = pd.to_numeric(koord[0], errors="coerce")
    df["_lat"] = pd.to_numeric(koord[1], errors="coerce")

    return df, ausgeschlossen


# ---------------------------------------------------------------------
# 2  Regelkatalog
# ---------------------------------------------------------------------
# Jede Regel traegt ihre ISO/IEC-25012-Dimension als Metainformation mit,
# damit das Dashboard nach Dimension gruppieren kann.

REGELN = [
    ("R01", "Pflanzjahr im plausiblen Bereich", "PFLANZJAHR", "Vollstaendigkeit",
     gxe.ExpectColumnValuesToBeBetween(
         column="PFLANZJAHR", min_value=JAHR_MIN, max_value=JAHR_MAX)),

    ("R02", "Stammumfang erfasst", "STAMMUMFANG", "Vollstaendigkeit",
     gxe.ExpectColumnValuesToBeBetween(column="STAMMUMFANG", min_value=1)),

    ("R03", "Bezirk vorhanden", "BEZIRK", "Vollstaendigkeit",
     gxe.ExpectColumnValuesToNotBeNull(column="BEZIRK")),

    ("R04", "Baumart vorhanden", "GATTUNG_ART", "Vollstaendigkeit",
     gxe.ExpectColumnValuesToNotBeNull(column="GATTUNG_ART")),

    ("R05", "Bezirk zwischen 1 und 23", "BEZIRK", "Genauigkeit",
     gxe.ExpectColumnValuesToBeBetween(
         column="BEZIRK", min_value=1, max_value=23)),

    ("R06", "Stammumfang plausibel (max 1000 cm)", "STAMMUMFANG", "Genauigkeit",
     gxe.ExpectColumnValuesToBeBetween(
         column="STAMMUMFANG", min_value=0, max_value=1000)),

    ("R07", "Baumhoehe in gueltiger Kategorie", "BAUMHOEHE", "Genauigkeit",
     gxe.ExpectColumnValuesToBeInSet(
         column="BAUMHOEHE", value_set=list(range(0, 9)))),

    ("R08", "Baum-ID eindeutig", "BAUM_ID", "Genauigkeit",
     gxe.ExpectColumnValuesToBeUnique(column="BAUM_ID")),

    ("R09a", "Laengengrad innerhalb Wien", "SHAPE", "Genauigkeit",
     gxe.ExpectColumnValuesToBeBetween(
         column="_lon", min_value=LON_MIN, max_value=LON_MAX)),

    ("R09b", "Breitengrad innerhalb Wien", "SHAPE", "Genauigkeit",
     gxe.ExpectColumnValuesToBeBetween(
         column="_lat", min_value=LAT_MIN, max_value=LAT_MAX)),

    ("R10", "Pflanzjahr stimmt mit Textfassung ueberein",
     "PFLANZJAHR / PFLANZJAHR_TXT", "Konsistenz",
     gxe.ExpectColumnPairValuesToBeEqual(
         column_A="PFLANZJAHR", column_B="_pflanzjahr_aus_txt")),

    ("R11", "Stammumfang stimmt mit Textfassung ueberein",
     "STAMMUMFANG / STAMMUMFANG_TXT", "Konsistenz",
     gxe.ExpectColumnPairValuesToBeEqual(
         column_A="STAMMUMFANG", column_B="_stammumfang_aus_txt")),

    ("R12", "Baumnummer rein numerisch", "BAUMNUMMER", "Konsistenz",
     gxe.ExpectColumnValuesToMatchRegex(
         column="BAUMNUMMER", regex=r"^\d+$")),

    ("R13", "Format 'Botanischer Name (Trivialname)'",
     "GATTUNG_ART", "Konsistenz",
     gxe.ExpectColumnValuesToMatchRegex(
         column="GATTUNG_ART", regex=r"^.+\(.+\)$")),

    ("R14", "Pflanzjahr exakt erfasst (ab 2006)", "PFLANZJAHR", "Glaubwuerdigkeit",
     gxe.ExpectColumnValuesToBeBetween(
         column="PFLANZJAHR", min_value=2006, max_value=JAHR_MAX)),
]


# ---------------------------------------------------------------------
# 3  Pruefung ausfuehren
# ---------------------------------------------------------------------

def pruefen(df):
    context = gx.get_context()
    quelle = context.data_sources.add_pandas("baumkataster")
    asset = quelle.add_dataframe_asset(name="baeume")
    batch = asset.add_batch_definition_whole_dataframe("gesamt")

    suite = context.suites.add(gx.ExpectationSuite(name="stammdaten_dq"))
    for rid, name, spalte, dimension, erwartung in REGELN:
        erwartung.meta = {"rule_id": rid, "regel": name,
                          "spalte": spalte, "dimension": dimension}
        suite.add_expectation(erwartung)

    definition = context.validation_definitions.add(
        gx.ValidationDefinition(data=batch, suite=suite, name="stammdaten_vd")
    )

    # result_format COMPLETE liefert die vollstaendige Liste der fehlerhaften
    # Zeilenindizes. Ohne diese Angabe begrenzt Great Expectations sie auf 20,
    # was fuer den Drill-through im Dashboard nicht ausreicht.
    # Die Umleitung unterdrueckt lediglich den Fortschrittsbalken.
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        return definition.run(
            batch_parameters={"dataframe": df},
            result_format={"result_format": "COMPLETE"},
        )


# ---------------------------------------------------------------------
# 4  Ergebnisse aufbereiten
# ---------------------------------------------------------------------

def ergebnisse_sammeln(resultat, df):
    zusammenfassung = []
    fehlerzeilen = []

    for eintrag in resultat["results"]:
        meta = eintrag["expectation_config"].get("meta") or {}
        werte = eintrag["result"]

        geprueft = werte.get("element_count", len(df))
        fehler = werte.get("unexpected_count", 0)
        pass_rate = (geprueft - fehler) / geprueft if geprueft else 1.0

        zusammenfassung.append({
            "run_ts": LAUF,
            "rule_id": meta.get("rule_id"),
            "regel": meta.get("regel"),
            "spalte": meta.get("spalte"),
            "iso_dimension": meta.get("dimension"),
            "geprueft_zeilen": geprueft,
            "fehler_zeilen": fehler,
            "pass_rate": round(pass_rate, 4),
            "status": "PASS" if eintrag["success"] else "FAIL",
        })

        index_liste = (werte.get("unexpected_index_list")
                       or werte.get("partial_unexpected_index_list") or [])
        for idx in index_liste[:MAX_FEHLER_JE_REGEL]:
            if idx not in df.index:
                continue
            zeile = df.loc[idx]
            fehlerzeilen.append({
                "run_ts": LAUF,
                "rule_id": meta.get("rule_id"),
                "baum_id": zeile.get("BAUM_ID"),
                "bezirk": zeile.get("BEZIRK"),
                "gattung_art": zeile.get("GATTUNG_ART"),
                "spalte": meta.get("spalte"),
            })

    ergebnis = pd.DataFrame(zusammenfassung).sort_values("rule_id")
    return ergebnis, pd.DataFrame(fehlerzeilen)


# ---------------------------------------------------------------------
# 5  Ablauf
# ---------------------------------------------------------------------

def main():
    roh = laden()
    df, ausgeschlossen = aufbereiten(roh)

    print()
    print("=" * 74)
    print("  STAMMDATEN - REGELPRUEFUNG NACH ISO/IEC 25012")
    print("=" * 74)
    print(f"  Datensaetze gesamt      : {len(roh):,}".replace(",", "."))
    print(f"  Ausgeschlossen (Status) : {ausgeschlossen:,}".replace(",", "."))
    print(f"  Geprueft                : {len(df):,}".replace(",", "."))

    resultat = pruefen(df)
    ergebnis, fehler = ergebnisse_sammeln(resultat, df)

    ergebnis.to_csv(PFAD_OUT / "dq_results.csv", index=False)
    fehler.to_csv(PFAD_OUT / "dq_fehler.csv", index=False)

    print()
    print("=" * 74)
    print("  ERGEBNIS JE REGEL")
    print("=" * 74)
    anzeige = ergebnis[["rule_id", "regel", "iso_dimension",
                        "fehler_zeilen", "pass_rate", "status"]]
    print(anzeige.to_string(index=False))

    print()
    print("=" * 74)
    print("  PASS RATE JE DIMENSION")
    print("=" * 74)
    je_dim = ergebnis.groupby("iso_dimension").agg(
        regeln=("rule_id", "count"),
        fehlgeschlagen=("status", lambda s: (s == "FAIL").sum()),
        pass_rate=("pass_rate", "mean"),
    ).round(4)
    print(je_dim.to_string())

    gesamt = ergebnis["pass_rate"].mean()
    print()
    print(f"  Gesamt-Pass-Rate : {gesamt:.2%}")
    print(f"  Geschrieben      : output/dq_results.csv ({len(ergebnis)} Zeilen)")
    print(f"                     output/dq_fehler.csv  ({len(fehler)} Zeilen)")
    print()


if __name__ == "__main__":
    main()