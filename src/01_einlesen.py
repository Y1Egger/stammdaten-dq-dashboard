"""
Stammdaten - Data Quality Dashboard
Schritt 1: Einlesen und Profiling des Wiener Baumkatasters

Dieses Skript prueft, ob die Rohdaten korrekt eingelesen werden, und
ermittelt die Datenqualitaetsbefunde, auf denen die spaeteren
Pruefregeln aufbauen.

Datenquelle: Stadt Wien - data.wien.gv.at (CC BY 4.0)
"""

import pandas as pd
from pathlib import Path

PFAD = Path(__file__).parent.parent / "data" / "raw" / "baumkataster.csv"

# Wien liegt bei ca. 1-23 Bezirken; Pflanzjahre vor 1800 sind unplausibel
JAHR_MIN, JAHR_MAX = 1650, 2026


def titel(text):
    """Ueberschrift fuer einen Abschnitt der Konsolenausgabe."""
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)


def befund(text):
    """Hebt einen Datenqualitaetsbefund hervor."""
    print(f"  >> BEFUND: {text}")


def anteil(teil, gesamt):
    """Formatiert eine Zahl mit Prozentangabe."""
    return f"{teil:,} von {gesamt:,} ({teil / gesamt:.1%})".replace(",", ".")


# ---------------------------------------------------------------------
# Einlesen
# ---------------------------------------------------------------------

try:
    df = pd.read_csv(PFAD, sep=",", encoding="utf-8")
    encoding_verwendet = "utf-8"
except UnicodeDecodeError:
    df = pd.read_csv(PFAD, sep=",", encoding="cp1252")
    encoding_verwendet = "cp1252"

zeilen, spalten = df.shape

print()
print("#" * 70)
print("#  STAMMDATEN - PROFILING WIENER BAUMKATASTER")
print("#  Quelle: Stadt Wien, data.wien.gv.at (CC BY 4.0)")
print("#" * 70)


# ---------------------------------------------------------------------
titel("1  STRUKTUR DER DATEI")
# ---------------------------------------------------------------------

print(f"  Datei          : {PFAD.name}")
print(f"  Encoding       : {encoding_verwendet}")
print(f"  Trennzeichen   : Komma")
print(f"  Datensaetze    : {zeilen:,}".replace(",", "."))
print(f"  Spalten        : {spalten}")
print()
print("  Spaltennamen:")
for i, spalte in enumerate(df.columns, start=1):
    print(f"    {i:>2}. {spalte}")


# ---------------------------------------------------------------------
titel("2  DATENTYPEN")
# ---------------------------------------------------------------------

for spalte, typ in df.dtypes.items():
    print(f"    {spalte:<24} {str(typ)}")

befund("BEZIRK ist float statt int - pandas weicht bei Nullwerten aus.")
befund("BAUMNUMMER ist Text, obwohl die Werte numerisch aussehen.")


# ---------------------------------------------------------------------
titel("3  VERSCHLEIERTE NULLWERTE (SENTINEL VALUES)")
# ---------------------------------------------------------------------

pflanzjahr_null = int((df["PFLANZJAHR"] == 0).sum())
stammumfang_null = int((df["STAMMUMFANG"] == 0).sum())

print(f"  PFLANZJAHR  == 0 : {anteil(pflanzjahr_null, zeilen)}")
print(f"  STAMMUMFANG == 0 : {anteil(stammumfang_null, zeilen)}")
print()
print("  Gegenprobe - was steht in der Begleitspalte PFLANZJAHR_TXT?")
gegenprobe = df.loc[df["PFLANZJAHR"] == 0, "PFLANZJAHR_TXT"].value_counts().head(3)
for wert, n in gegenprobe.items():
    print(f"    {str(wert):<20} {n:,}".replace(",", "."))

befund(
    "Fehlende Werte sind als 0 codiert, nicht als NULL. "
    "Eine reine Nullwertpruefung wuerde diese Luecke uebersehen."
)


# ---------------------------------------------------------------------
titel("4  ECHTE FEHLENDE WERTE")
# ---------------------------------------------------------------------

leer = df.isna().sum()
leer = leer[leer > 0].sort_values(ascending=False)

if len(leer) == 0:
    print("    Keine NULL-Werte gefunden.")
else:
    for spalte, n in leer.items():
        print(f"    {spalte:<24} {anteil(int(n), zeilen)}")

befund(f"{leer.get('BEZIRK', 0):,} Datensaetze ohne Bezirk.".replace(",", "."))


# ---------------------------------------------------------------------
titel("5  SCHLUESSELKANDIDATEN")
# ---------------------------------------------------------------------

dup_id = int(df["BAUM_ID"].duplicated().sum())
dup_nr = int(df["BAUMNUMMER"].duplicated().sum())
distinct_nr = int(df["BAUMNUMMER"].nunique())

print(f"    BAUM_ID     Duplikate : {dup_id:,}".replace(",", "."))
print(f"    BAUMNUMMER  Duplikate : {dup_nr:,}".replace(",", "."))
print(f"    BAUMNUMMER  eindeutige Werte : {distinct_nr:,}".replace(",", "."))
print()

nicht_numerisch = int((~df["BAUMNUMMER"].str.isnumeric()).sum())
print(f"    BAUMNUMMER nicht rein numerisch : {anteil(nicht_numerisch, zeilen)}")

befund(
    "BAUM_ID ist der technische Primaerschluessel. "
    "BAUMNUMMER ist nur fachlich, nicht global eindeutig."
)


# ---------------------------------------------------------------------
titel("6  SPALTEN OHNE INFORMATIONSGEHALT")
# ---------------------------------------------------------------------

for spalte in df.columns:
    n_werte = df[spalte].nunique(dropna=True)
    if n_werte <= 1:
        wert = df[spalte].dropna().unique()
        wert = wert[0] if len(wert) else "(komplett leer)"
        print(f"    {spalte:<24} nur 1 Wert: {wert}")

befund("Zero-Variance-Spalten tragen keine Information zur Auswertung bei.")


# ---------------------------------------------------------------------
titel("7  WERTEBEREICH PFLANZJAHR")
# ---------------------------------------------------------------------

print("  Mit Nullwerten:")
print(f"    Mittelwert : {df['PFLANZJAHR'].mean():.0f}")
print(f"    Median     : {df['PFLANZJAHR'].median():.0f}")
print(f"    Minimum    : {df['PFLANZJAHR'].min():.0f}")
print(f"    Maximum    : {df['PFLANZJAHR'].max():.0f}")

gueltig = df.loc[df["PFLANZJAHR"].between(JAHR_MIN, JAHR_MAX), "PFLANZJAHR"]
print()
print(f"  Nur plausible Werte ({JAHR_MIN}-{JAHR_MAX}):")
print(f"    Mittelwert : {gueltig.mean():.0f}")
print(f"    Median     : {gueltig.median():.0f}")
print(f"    Minimum    : {gueltig.min():.0f}")
print(f"    Maximum    : {gueltig.max():.0f}")

befund(
    f"Ungefiltert ergibt sich ein Durchschnittspflanzjahr von "
    f"{df['PFLANZJAHR'].mean():.0f} - die Kennzahl ist ohne "
    f"Bereinigung unbrauchbar."
)


# ---------------------------------------------------------------------
titel("ZUSAMMENFASSUNG")
# ---------------------------------------------------------------------

print(f"    {zeilen:,} Datensaetze, {spalten} Spalten geprueft".replace(",", "."))
print(f"    {pflanzjahr_null:,} verschleierte Nullwerte in PFLANZJAHR".replace(",", "."))
print(f"    {stammumfang_null:,} verschleierte Nullwerte in STAMMUMFANG".replace(",", "."))
print(f"    {int(leer.sum()):,} echte NULL-Werte insgesamt".replace(",", "."))
print()

print(df.loc[df["PFLANZJAHR"].between(1, 1799), "PFLANZJAHR"].value_counts())
print((df["PFLANZJAHR"] == 1800).sum())