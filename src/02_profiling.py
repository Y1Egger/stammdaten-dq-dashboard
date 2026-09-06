"""
Stammdaten - Data Quality Dashboard
Schritt 2: Profiling in SQL mit DuckDB

Dieselben Befunde wie in 01_einlesen.py, diesmal mengenbasiert
in SQL formuliert.

Datenquelle: Stadt Wien - data.wien.gv.at (CC BY 4.0)
"""

import duckdb
from pathlib import Path

PFAD = Path(__file__).parent.parent / "data" / "raw" / "baumkataster.csv"

con = duckdb.connect()
con.execute(f"""
    CREATE OR REPLACE TABLE baeume AS
    SELECT * FROM read_csv_auto('{PFAD.as_posix()}', header=true)
""")


def abfrage(titel, sql):
    print()
    print("=" * 70)
    print(f"  {titel}")
    print("=" * 70)
    print(con.execute(sql).df().to_string(index=False))


abfrage("Umfang", """
    SELECT COUNT(*) AS datensaetze FROM baeume
""")

abfrage("Verschleierte Nullwerte", """
    SELECT
        SUM(CASE WHEN PFLANZJAHR  = 0 THEN 1 ELSE 0 END) AS pflanzjahr_null,
        SUM(CASE WHEN STAMMUMFANG = 0 THEN 1 ELSE 0 END) AS stammumfang_null,
        ROUND(100.0 * SUM(CASE WHEN PFLANZJAHR = 0 THEN 1 ELSE 0 END)
              / COUNT(*), 1) AS pflanzjahr_prozent
    FROM baeume
""")

abfrage("Schluesselkandidaten", """
    SELECT
        COUNT(DISTINCT BAUM_ID)    AS baum_id_distinct,
        COUNT(DISTINCT BAUMNUMMER) AS baumnummer_distinct,
        COUNT(*)                   AS zeilen
    FROM baeume
""")

abfrage("Bezirksverteilung inkl. fehlender Werte", """
    SELECT
        COALESCE(CAST(BEZIRK AS VARCHAR), '(leer)') AS bezirk,
        COUNT(*) AS anzahl
    FROM baeume
    GROUP BY 1
    ORDER BY anzahl DESC
    LIMIT 25
""")

abfrage("Pflanzjahr: bereinigt vs. unbereinigt", """
    SELECT
        ROUND(AVG(PFLANZJAHR), 0) AS mittelwert_roh,
        ROUND(AVG(CASE WHEN PFLANZJAHR BETWEEN 1650 AND 2026
                       THEN PFLANZJAHR END), 0) AS mittelwert_bereinigt,
        MEDIAN(PFLANZJAHR) AS median_roh,
        MEDIAN(CASE WHEN PFLANZJAHR BETWEEN 1650 AND 2026
                    THEN PFLANZJAHR END) AS median_bereinigt
    FROM baeume
""")

abfrage("Haeufigste Baumarten", """
    SELECT GATTUNG_ART, COUNT(*) AS anzahl
    FROM baeume
    WHERE GATTUNG_ART NOT LIKE '%(%'
    GROUP BY GATTUNG_ART
    ORDER BY anzahl DESC
    LIMIT 20
""")

abfrage("Haeufigste Baumarten", """
    SELECT
    COUNT(DISTINCT GATTUNG_ART) AS arten_gesamt,
    SUM(CASE WHEN GATTUNG_ART NOT LIKE '%(%' THEN 1 ELSE 0 END) AS ohne_klammer,
    SUM(CASE WHEN TRIM(GATTUNG_ART) != GATTUNG_ART THEN 1 ELSE 0 END) AS mit_leerzeichen
    FROM baeume
""")

abfrage("Randfaelle vor 1800", """
    SELECT PFLANZJAHR, COUNT(*) AS anzahl
    FROM baeume
    WHERE PFLANZJAHR BETWEEN 1 AND 1799
    GROUP BY PFLANZJAHR
    ORDER BY PFLANZJAHR
""")