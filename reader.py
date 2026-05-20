"""
reader.py
Lit un fichier Excel, liste les feuilles, charge les données brutes sans supposer
la position du header.
"""

import pandas as pd
from pathlib import Path


def load_all_sheets_raw(filepath: str | Path) -> dict[str, pd.DataFrame]:
    """
    Charge toutes les feuilles d'un fichier Excel sans header (header=None).
    Retourne un dict {sheet_name: DataFrame brut}.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    xl = pd.ExcelFile(filepath, engine="openpyxl")
    sheets = {}
    for name in xl.sheet_names:
        df = xl.parse(name, header=None, dtype=str)
        df = df.dropna(how="all").reset_index(drop=True)
        sheets[name] = df
    return sheets


def get_sheet_names(filepath: str | Path) -> list[str]:
    xl = pd.ExcelFile(Path(filepath), engine="openpyxl")
    return xl.sheet_names
