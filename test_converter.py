"""
tests/test_converter.py
Tests unitaires pour les modules principaux du convertisseur.
Lancer avec : python -m pytest tests/ -v
"""

import sys
from pathlib import Path
from datetime import date

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from converter.week_utils import parse_week_column, parse_month_column, dominant_month
from converter.detector import detect_header_row, build_dataframe_from_header, detect_file_type
from converter.warnings import ConversionWarnings
from converter.transformer import transform_type1, transform_type3


# ── week_utils ────────────────────────────────────────────────────────────────

class TestWeekUtils:
    def test_parse_w_slash(self):
        d = parse_week_column("W 19/2026")
        assert d is not None
        assert d.year == 2026
        assert d.month == 5  # semaine 19 de 2026 → mai

    def test_parse_w_no_space(self):
        d = parse_week_column("W19/2026")
        assert d is not None

    def test_parse_yyyy_s(self):
        d = parse_week_column("2026-S19")
        assert d is not None
        assert d.year == 2026

    def test_parse_yyyy_s_underscored(self):
        d = parse_week_column("2026_S19")
        assert d is not None

    def test_parse_unknown_returns_none(self):
        assert parse_week_column("Total 2026") is None
        assert parse_week_column("Article") is None
        assert parse_week_column("") is None

    def test_parse_month_column(self):
        d = parse_month_column("M 09/2026")
        assert d == date(2026, 9, 1)

    def test_dominant_month_boundary(self):
        # Semaine qui chevauche deux mois
        d = dominant_month(2026, 22)  # Fin mai / début juin 2026
        assert isinstance(d, date)
        assert d.day == 1

    def test_w23_june(self):
        d = parse_week_column("W 23/2026")
        assert d is not None
        assert d.month == 6  # Juin 2026


# ── detector ─────────────────────────────────────────────────────────────────

class TestDetector:
    def _make_raw_with_junk(self):
        """DataFrame brut avec lignes de junk avant le vrai header."""
        data = [
            ["Total général", 100, 200, 300],
            [None, None, None, None],
            ["Article", "Désignation article", "Division", "W 19/2026"],
            ["REF001", "Pièce A", "DIV1", 50],
            ["REF002", "Pièce B", "DIV2", 30],
        ]
        return pd.DataFrame(data)

    def test_detect_header_row(self):
        raw = self._make_raw_with_junk()
        hrow = detect_header_row(raw)
        assert hrow == 2

    def test_build_dataframe_from_header(self):
        raw = self._make_raw_with_junk()
        hrow = detect_header_row(raw)
        df = build_dataframe_from_header(raw, hrow)
        assert "Article" in df.columns
        assert "W 19/2026" in df.columns
        assert len(df) == 2

    def test_detect_type1(self):
        df = pd.DataFrame({
            "Article": ["REF1"],
            "Désignation article": ["Pièce"],
            "Division": ["D1"],
            "W 19/2026": [10],
            "M 09/2026": [20],
        })
        assert detect_file_type(df) == "Type1"

    def test_detect_type3(self):
        df = pd.DataFrame({
            "Cdc": ["CDC1"],
            "Référence OF": ["REF1"],
            "Désignation": ["Pièce"],
            "2026-S17": [10],
            "2026-S18": [20],
        })
        assert detect_file_type(df) == "Type3"

    def test_detect_unknown(self):
        df = pd.DataFrame({"Col1": [1], "Col2": [2]})
        assert detect_file_type(df) == "Inconnu"


# ── transformer type1 ─────────────────────────────────────────────────────────

class TestTransformerType1:
    def _make_type1_df(self):
        return pd.DataFrame({
            "Article": ["E532.001", "E532.002"],
            "Désignation article": ["Pièce X", "Pièce Y"],
            "Division": ["DIV1", "DIV2"],
            "Reliquat": [5, 3],
            "W 19/2026": [10, 20],
            "W 20/2026": [15, 25],
            "M 09/2026": [30, 40],
        })

    def test_basic_conversion(self):
        df = self._make_type1_df()
        warn = ConversionWarnings()
        result = transform_type1(df, "ClientA", "test.xlsx", "Sheet1", warn)
        assert not result.empty
        assert "Ref" in result.columns
        assert "Date_Mois" in result.columns
        assert "Quantité" in result.columns

    def test_ref_mapping(self):
        df = self._make_type1_df()
        warn = ConversionWarnings()
        result = transform_type1(df, "ClientA", "test.xlsx", "Sheet1", warn)
        assert "E532.001" in result["Ref"].values

    def test_weekly_aggregation(self):
        # W19 et W20 2026 → tous les deux en Mai 2026
        df = self._make_type1_df()
        warn = ConversionWarnings()
        result = transform_type1(df, "ClientA", "test.xlsx", "Sheet1", warn)
        may = result[(result["Ref"] == "E532.001") & (result["Mois"] == 5)]
        assert not may.empty
        # 10 + 15 = 25
        assert may["Quantité"].sum() == 25.0

    def test_reliquat_not_in_quantity(self):
        df = self._make_type1_df()
        warn = ConversionWarnings()
        result = transform_type1(df, "ClientA", "test.xlsx", "Sheet1", warn)
        # Le reliquat ne doit pas être dans Quantité
        assert result["Quantité"].max() < 100  # 5 ou 3 n'ont pas été ajoutés


# ── transformer type3 ─────────────────────────────────────────────────────────

class TestTransformerType3:
    def _make_type3_df(self):
        return pd.DataFrame({
            "Cdc": ["CDC1", "CDC1"],
            "Référence OF": ["M001", "M002"],
            "Désignation": ["Pièce A", "Pièce B"],
            "2026-S17": [10, 20],
            "2026-S18": [15, 25],
            "2027-S01": [5, 10],
            "Total général": [30, 55],  # doit être ignoré
        })

    def test_total_ignored(self):
        df = self._make_type3_df()
        warn = ConversionWarnings()
        result = transform_type3(df, "ClientB", "test.xlsx", "Sheet1", warn)
        assert "Total général" not in warn.unrecognized_columns or "Total général" in warn.ignored_columns

    def test_ref_mapping(self):
        df = self._make_type3_df()
        warn = ConversionWarnings()
        result = transform_type3(df, "ClientB", "test.xlsx", "Sheet1", warn)
        assert "M001" in result["Ref"].values

    def test_cdc_preserved(self):
        df = self._make_type3_df()
        warn = ConversionWarnings()
        result = transform_type3(df, "ClientB", "test.xlsx", "Sheet1", warn)
        assert "CDC1" in result["Cdc"].values


# ── warnings ─────────────────────────────────────────────────────────────────

class TestWarnings:
    def test_to_dict_list(self):
        w = ConversionWarnings()
        w.file_type = "Type1"
        w.sheet_used = "Feuil1"
        w.header_row = 2
        w.rows_processed = 100
        w.refs_processed = 50
        w.months_generated = 12
        w.duplicate_weeks.append("W 19/2026")
        rows = w.to_dict_list()
        assert any(r["Détail"] == "Type1" for r in rows)
        assert any("W 19/2026" in str(r["Détail"]) for r in rows)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
