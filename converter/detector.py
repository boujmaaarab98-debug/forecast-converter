"""
detector.py
Détecte :
  1. La ligne réelle du header dans un DataFrame brut (sans supposer qu'elle est à la ligne 0).
  2. Le type de fichier (Type1, Type2, Type3 ou Inconnu).
"""

import re
import pandas as pd
from converter.week_utils import parse_week_column, parse_month_column

# ── Indices de header connus ─────────────────────────────────────────────────

HEADER_KEYWORDS = {
    "article", "désignation article", "designation article",
    "row labels", "référence of", "reference of",
    "cdc", "division", "reliquat", "désignation", "designation",
    "ref", "code article", "libellé", "libelle", "référence", "reference",
}

_RE_W = re.compile(r"^W\s*\d{1,2}[/\-]\d{4}$", re.IGNORECASE)
_RE_M = re.compile(r"^M\s*\d{1,2}[/\-]\d{4}$", re.IGNORECASE)
_RE_YYYY_S = re.compile(r"^\d{4}[_\-]?S\d{1,2}$", re.IGNORECASE)
_RE_YEAR = re.compile(r"^20\d{2}$")
_RE_MONTH_NUM = re.compile(r"^\d{1,2}$")


def _cell_is_header_hint(val: str) -> bool:
    """Retourne True si la valeur ressemble à une colonne d'en-tête connue."""
    v = str(val).strip().lower()
    if v in HEADER_KEYWORDS:
        return True
    if _RE_W.match(v) or _RE_M.match(v) or _RE_YYYY_S.match(v):
        return True
    return False


def detect_header_row(df: pd.DataFrame, max_scan: int = 20) -> int:
    """
    Scanne les max_scan premières lignes pour trouver la vraie ligne de header.
    Retourne l'index (0-based) de la ligne d'en-tête, ou 0 par défaut.
    """
    limit = min(max_scan, len(df))
    best_row = 0
    best_score = 0

    for i in range(limit):
        row_vals = [str(v).strip() for v in df.iloc[i] if pd.notna(v) and str(v).strip()]
        score = sum(1 for v in row_vals if _cell_is_header_hint(v))
        if score > best_score:
            best_score = score
            best_row = i

    return best_row


def build_dataframe_from_header(raw_df: pd.DataFrame, header_row: int) -> pd.DataFrame:
    """
    Construit un DataFrame propre à partir de la ligne header détectée.
    Les lignes avant le header sont supprimées.
    """
    headers = [str(v).strip() if pd.notna(v) else "" for v in raw_df.iloc[header_row]]
    data = raw_df.iloc[header_row + 1:].copy()
    data.columns = headers
    data = data.reset_index(drop=True)
    return data


# ── Détection du type ────────────────────────────────────────────────────────

def _col_names(df: pd.DataFrame) -> list[str]:
    return [str(c).strip().lower() for c in df.columns]


def detect_file_type(df: pd.DataFrame) -> str:
    """
    Retourne "Type1", "Type2", "Type3" ou "Inconnu".
    df doit avoir les vraies colonnes en header.
    """
    cols_lower = _col_names(df)
    cols_original = [str(c).strip() for c in df.columns]

    has_article = "article" in cols_lower
    has_desig_article = "désignation article" in cols_lower or "designation article" in cols_lower
    has_row_labels = "row labels" in cols_lower
    has_ref_of = "référence of" in cols_lower or "reference of" in cols_lower
    has_cdc = "cdc" in cols_lower

    # Colonnes hebdo / mensuelles
    week_cols_w = [c for c in cols_original if _RE_W.match(c)]
    month_cols_m = [c for c in cols_original if _RE_M.match(c)]
    week_cols_s = [c for c in cols_original if _RE_YYYY_S.match(c)]

    # Détection années / numéros de mois (Type2 tableau croisé)
    year_cols = [c for c in cols_original if _RE_YEAR.match(c)]
    # Pour Type2, les années peuvent aussi être dans les valeurs de la première ligne
    # On vérifie aussi si des colonnes ressemblent à des années numériques >= 2020
    numeric_year_cols = []
    for c in cols_original:
        try:
            y = int(float(c))
            if 2020 <= y <= 2035:
                numeric_year_cols.append(c)
        except (ValueError, TypeError):
            pass

    total_cols = [c for c in cols_original if str(c).lower().startswith("total")]

    # ── TYPE 1 ──
    if (has_article or has_desig_article) and (week_cols_w or month_cols_m):
        return "Type1"

    # ── TYPE 2 ──
    if has_row_labels and (year_cols or numeric_year_cols) and total_cols:
        return "Type2"
    # Cas Type2 sans "Row Labels" exact mais avec structure similaire
    if (year_cols or numeric_year_cols) and total_cols and len(total_cols) >= 1:
        # Vérifie qu'on a aussi des colonnes numériques 1-12
        month_num_cols = [c for c in cols_original if _RE_MONTH_NUM.match(str(c).strip())]
        if month_num_cols:
            return "Type2"

    # ── TYPE 3 ──
    if (has_ref_of or has_cdc) and week_cols_s:
        return "Type3"
    # Générique Type3 : présence de colonnes yyyy-Sxx
    if week_cols_s and len(week_cols_s) >= 2:
        return "Type3"

    return "Inconnu"


def identify_best_sheet(sheets: dict[str, pd.DataFrame]) -> tuple[str, pd.DataFrame, int, str]:
    """
    Parcourt toutes les feuilles et retourne (sheet_name, df_clean, header_row, file_type)
    pour la feuille la plus pertinente (meilleur score de reconnaissance).
    """
    best = None
    best_score = -1

    for name, raw_df in sheets.items():
        if raw_df.empty:
            continue
        hrow = detect_header_row(raw_df)
        df = build_dataframe_from_header(raw_df, hrow)
        ftype = detect_file_type(df)

        # Score : Type reconnu > Inconnu ; plus de colonnes = mieux
        score = (0 if ftype == "Inconnu" else 10) + len(df.columns)
        if score > best_score:
            best_score = score
            best = (name, df, hrow, ftype)

    if best is None:
        raise ValueError("Aucune feuille valide trouvée dans le fichier.")
    return best
