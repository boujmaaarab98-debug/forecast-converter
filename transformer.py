"""
transformer.py
Transforme chaque type de fichier vers un DataFrame "long" Power BI propre.
"""

import re
import numpy as np
import pandas as pd
from datetime import datetime, date

from converter.week_utils import parse_week_column, parse_month_column
from converter.warnings import ConversionWarnings

# ── Regex utilitaires ────────────────────────────────────────────────────────

_RE_W = re.compile(r"^W\s*\d{1,2}[/\-]\d{4}$", re.IGNORECASE)
_RE_M = re.compile(r"^M\s*\d{1,2}[/\-]\d{4}$", re.IGNORECASE)
_RE_YYYY_S = re.compile(r"^\d{4}[_\-]?S\d{1,2}$", re.IGNORECASE)
_RE_YEAR = re.compile(r"^20\d{2}$")
_RE_MONTH_NUM = re.compile(r"^\d{1,2}$")

# Colonnes à ignorer (totaux, vides)
_IGNORE_PATTERNS = re.compile(
    r"^(total|total général|total general|\(vide\)|vide|nan|unnamed).*$",
    re.IGNORECASE,
)

# Mapping standardisé des colonnes fixes
COL_MAPPING = {
    "article": "Ref",
    "row labels": "Ref",
    "référence of": "Ref",
    "reference of": "Ref",
    "référence": "Ref",
    "reference": "Ref",
    "code article": "Ref",
    "ref": "Ref",
    "désignation article": "Désignation",
    "designation article": "Désignation",
    "désignation": "Désignation",
    "designation": "Désignation",
    "libellé": "Désignation",
    "libelle": "Désignation",
    "division": "Division",
    "cdc": "Cdc",
    "reliquat": "Reliquat",
}


def _should_ignore_col(col: str) -> bool:
    s = str(col).strip()
    return bool(_IGNORE_PATTERNS.match(s)) or s == "" or s.lower() == "nan"


def _to_numeric(val, warnings: ConversionWarnings) -> float:
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return 0.0
    try:
        return float(str(val).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        warnings.non_numeric_values += 1
        return 0.0


def _base_meta(row: pd.Series, col_map: dict) -> dict:
    """Extrait les métadonnées fixes d'une ligne (Ref, Désignation, Division, Cdc, Reliquat)."""
    meta = {
        "Ref": "",
        "Désignation": "",
        "Division": "",
        "Cdc": "",
        "Reliquat": "",
    }
    for src, tgt in col_map.items():
        if tgt in meta and src in row.index:
            val = str(row[src]).strip() if pd.notna(row[src]) else ""
            if val.lower() not in ("nan", "none", ""):
                meta[tgt] = val
    return meta


def _make_long_row(meta: dict, d: date, qty: float, source_type: str,
                   client: str, source_file: str, sheet_name: str,
                   file_type: str, import_dt: str) -> dict:
    return {
        "Client": client,
        "Source_File": source_file,
        "Sheet_Name": sheet_name,
        "File_Type": file_type,
        "Ref": meta["Ref"],
        "Désignation": meta["Désignation"],
        "Division": meta["Division"],
        "Cdc": meta["Cdc"],
        "Reliquat": meta["Reliquat"],
        "Date_Mois": d.strftime("%Y-%m-%d"),
        "Année": d.year,
        "Mois": d.month,
        "Quantité": qty,
        "Type_Source": source_type,
        "Import_Date": import_dt,
    }


# ── TYPE 1 ───────────────────────────────────────────────────────────────────

def transform_type1(df: pd.DataFrame, client: str, source_file: str,
                    sheet_name: str, warn: ConversionWarnings) -> pd.DataFrame:
    """
    Fichier avec colonnes W xx/yyyy et/ou M mm/yyyy.
    Les semaines sont converties en mois et agrégées par Ref+Mois.
    """
    import_dt = datetime.now().isoformat(timespec="seconds")
    cols = list(df.columns)

    # Identifier le mapping des colonnes fixes
    col_map = {}
    for c in cols:
        key = str(c).strip().lower()
        if key in COL_MAPPING:
            col_map[COL_MAPPING[key]] = c  # tgt -> src_col_name

    # Inverser pour _base_meta : src_col_name -> tgt
    inv_map = {v: k for k, v in col_map.items()}

    # Colonnes hebdo/mensuelles
    week_cols = {}   # col_name -> date
    month_cols = {}  # col_name -> date
    ignored = []
    unrecognized = []

    # Détecter les doublons de noms de colonnes (même nom exact)
    seen_col_names: set[str] = set()

    for c in cols:
        if _should_ignore_col(c):
            ignored.append(c)
            continue
        clow = str(c).strip().lower()
        if clow in COL_MAPPING:
            continue  # colonne fixe

        c_stripped = str(c).strip()
        if c_stripped in seen_col_names:
            warn.duplicate_weeks.append(c_stripped)
        else:
            seen_col_names.add(c_stripped)

        d_week = parse_week_column(c)
        d_month = parse_month_column(c)

        if _RE_W.match(c_stripped):
            if d_week:
                week_cols[c] = d_week
            else:
                unrecognized.append(c)
        elif _RE_M.match(c_stripped):
            if d_month:
                month_cols[c] = d_month
            else:
                unrecognized.append(c)
        else:
            unrecognized.append(c)

    warn.ignored_columns.extend(ignored)
    warn.unrecognized_columns.extend(unrecognized)

    rows_out = []
    for _, row in df.iterrows():
        ref_col = col_map.get("Ref", "")
        ref_val = str(row[ref_col]).strip() if ref_col and pd.notna(row[ref_col]) else ""
        if not ref_val or ref_val.lower() in ("nan", "none", ""):
            warn.empty_refs += 1
            continue

        meta = {
            "Ref": ref_val,
            "Désignation": str(row[col_map["Désignation"]]).strip() if "Désignation" in col_map and pd.notna(row[col_map["Désignation"]]) else "",
            "Division": str(row[col_map["Division"]]).strip() if "Division" in col_map and pd.notna(row[col_map["Division"]]) else "",
            "Cdc": str(row[col_map["Cdc"]]).strip() if "Cdc" in col_map and pd.notna(row[col_map["Cdc"]]) else "",
            "Reliquat": str(row[col_map["Reliquat"]]).strip() if "Reliquat" in col_map and pd.notna(row[col_map["Reliquat"]]) else "",
        }

        # Agréger semaines -> mois
        monthly_agg: dict[date, float] = {}
        for col, d in week_cols.items():
            qty = _to_numeric(row[col], warn)
            monthly_agg[d] = monthly_agg.get(d, 0.0) + qty

        for col, d in month_cols.items():
            qty = _to_numeric(row[col], warn)
            monthly_agg[d] = monthly_agg.get(d, 0.0) + qty

        for d, qty in monthly_agg.items():
            src_type = "Weekly" if d in {v for v in week_cols.values()} else "Monthly"
            # Si un même mois a des sources W et M, on prend Monthly pour les M
            # (En pratique, on tag par colonne d'origine - simplifié ici)
            rows_out.append(_make_long_row(meta, d, qty, src_type,
                                           client, source_file, sheet_name,
                                           "Type1", import_dt))

    warn.rows_processed = len(df)
    result = pd.DataFrame(rows_out)
    if result.empty:
        return result
    warn.refs_processed = result["Ref"].nunique()
    warn.months_generated = result["Date_Mois"].nunique()
    return result


# ── TYPE 2 ───────────────────────────────────────────────────────────────────

def transform_type2(raw_df: pd.DataFrame, client: str, source_file: str,
                    sheet_name: str, warn: ConversionWarnings,
                    raw_for_header: pd.DataFrame = None,
                    header_row: int = 0) -> pd.DataFrame:
    """
    Tableau croisé pivot : années en ligne supérieure, mois (1-12) en ligne inférieure.
    On reconstruit les colonnes (année, mois) depuis les 2 premières lignes.
    """
    import_dt = datetime.now().isoformat(timespec="seconds")

    # Pour Type2, le vrai header peut être en 2 lignes (année + mois)
    # raw_df = le DataFrame BRUT (header=None), header_row = ligne détectée
    # On va utiliser les lignes header_row et header_row+1 comme en-têtes composites
    if raw_for_header is not None:
        raw = raw_for_header
    else:
        raw = raw_df

    # Ligne des années
    year_line = [str(v).strip() if pd.notna(v) else "" for v in raw.iloc[header_row]]
    # Ligne des mois (juste après)
    if header_row + 1 < len(raw):
        month_line = [str(v).strip() if pd.notna(v) else "" for v in raw.iloc[header_row + 1]]
    else:
        month_line = [""] * len(year_line)

    # Données à partir de header_row + 2
    data = raw.iloc[header_row + 2:].copy().reset_index(drop=True)

    # Construire les colonnes composites
    composite_cols = []
    current_year = ""
    for i, (y, m) in enumerate(zip(year_line, month_line)):
        if _RE_YEAR.match(y):
            current_year = y
        col_type = "year_header" if _RE_YEAR.match(y) else ""

        if _should_ignore_col(y) and _should_ignore_col(m):
            composite_cols.append(("__ignore__", i))
            continue

        if str(y).lower().startswith("total") or str(m).lower().startswith("total"):
            composite_cols.append(("__total__", i))
            warn.ignored_columns.append(f"{y} / {m}")
            continue

        if _RE_MONTH_NUM.match(m) and current_year:
            try:
                mo = int(m)
                yr = int(current_year)
                if 1 <= mo <= 12:
                    composite_cols.append((date(yr, mo, 1), i))
                    continue
            except ValueError:
                pass

        # Colonne fixe (Row Labels, Ref, etc.)
        label = y if y else m
        composite_cols.append((label, i))

    # Identifier la colonne Ref (Row Labels ou première colonne texte)
    ref_col_idx = None
    for col_val, idx in composite_cols:
        if isinstance(col_val, str) and col_val.lower() in ("row labels", "ref", "article", "référence", "reference"):
            ref_col_idx = idx
            break
    if ref_col_idx is None:
        # Première colonne non-date non-total
        for col_val, idx in composite_cols:
            if isinstance(col_val, str) and col_val not in ("__ignore__", "__total__"):
                ref_col_idx = idx
                break

    rows_out = []
    for _, row in data.iterrows():
        row_vals = list(row)
        ref_val = str(row_vals[ref_col_idx]).strip() if ref_col_idx is not None and ref_col_idx < len(row_vals) else ""
        if not ref_val or ref_val.lower() in ("nan", "none", ""):
            warn.empty_refs += 1
            continue

        meta = {"Ref": ref_val, "Désignation": "", "Division": "", "Cdc": "", "Reliquat": ""}

        for col_val, idx in composite_cols:
            if not isinstance(col_val, date):
                continue
            if idx >= len(row_vals):
                continue
            qty = _to_numeric(row_vals[idx], warn)
            if qty == 0.0:
                continue
            rows_out.append(_make_long_row(meta, col_val, qty, "PivotMonthly",
                                           client, source_file, sheet_name,
                                           "Type2", import_dt))

    warn.rows_processed = len(data)
    result = pd.DataFrame(rows_out)
    if result.empty:
        return result
    warn.refs_processed = result["Ref"].nunique()
    warn.months_generated = result["Date_Mois"].nunique()
    return result


# ── TYPE 3 ───────────────────────────────────────────────────────────────────

def transform_type3(df: pd.DataFrame, client: str, source_file: str,
                    sheet_name: str, warn: ConversionWarnings) -> pd.DataFrame:
    """
    Forecast hebdomadaire long terme : colonnes yyyy-Sxx.
    """
    import_dt = datetime.now().isoformat(timespec="seconds")
    cols = list(df.columns)

    col_map = {}
    for c in cols:
        key = str(c).strip().lower()
        if key in COL_MAPPING:
            col_map[COL_MAPPING[key]] = c

    week_cols: dict[str, date] = {}
    seen_col_names3: set[str] = set()
    ignored = []
    unrecognized = []

    for c in cols:
        clow = str(c).strip().lower()
        if _should_ignore_col(c):
            ignored.append(c)
            continue
        if clow in COL_MAPPING:
            continue

        c_stripped = str(c).strip()
        if _RE_YYYY_S.match(c_stripped):
            if c_stripped in seen_col_names3:
                warn.duplicate_weeks.append(c_stripped)
            else:
                seen_col_names3.add(c_stripped)
            d = parse_week_column(c)
            if d:
                week_cols[c] = d
            else:
                unrecognized.append(c)
        else:
            unrecognized.append(c)

    warn.ignored_columns.extend(ignored)
    warn.unrecognized_columns.extend(unrecognized)

    rows_out = []
    for _, row in df.iterrows():
        ref_col = col_map.get("Ref", "")
        ref_val = str(row[ref_col]).strip() if ref_col and ref_col in row.index and pd.notna(row[ref_col]) else ""
        if not ref_val or ref_val.lower() in ("nan", "none", ""):
            warn.empty_refs += 1
            continue

        meta = {
            "Ref": ref_val,
            "Désignation": str(row[col_map["Désignation"]]).strip() if "Désignation" in col_map and pd.notna(row.get(col_map["Désignation"])) else "",
            "Division": "",
            "Cdc": str(row[col_map["Cdc"]]).strip() if "Cdc" in col_map and pd.notna(row.get(col_map["Cdc"])) else "",
            "Reliquat": "",
        }

        # Agréger par mois
        monthly_agg: dict[date, float] = {}
        for col, d in week_cols.items():
            qty = _to_numeric(row.get(col, 0), warn)
            monthly_agg[d] = monthly_agg.get(d, 0.0) + qty

        for d, qty in monthly_agg.items():
            rows_out.append(_make_long_row(meta, d, qty, "Weekly",
                                           client, source_file, sheet_name,
                                           "Type3", import_dt))

    warn.rows_processed = len(df)
    result = pd.DataFrame(rows_out)
    if result.empty:
        return result
    warn.refs_processed = result["Ref"].nunique()
    warn.months_generated = result["Date_Mois"].nunique()
    return result


# ── Dispatcher ────────────────────────────────────────────────────────────────

def transform(df: pd.DataFrame, file_type: str, client: str,
              source_file: str, sheet_name: str,
              warn: ConversionWarnings,
              raw_df: pd.DataFrame = None,
              header_row: int = 0) -> pd.DataFrame:
    """Point d'entrée unique : dispatche vers la bonne fonction selon file_type."""
    if file_type == "Type1":
        return transform_type1(df, client, source_file, sheet_name, warn)
    elif file_type == "Type2":
        return transform_type2(df, client, source_file, sheet_name, warn,
                               raw_for_header=raw_df, header_row=header_row)
    elif file_type == "Type3":
        return transform_type3(df, client, source_file, sheet_name, warn)
    else:
        warn.add_note("Type de fichier non reconnu — aucune transformation effectuée.")
        return pd.DataFrame()
