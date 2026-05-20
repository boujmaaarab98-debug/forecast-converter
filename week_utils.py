"""
week_utils.py
Fonctions pour convertir les semaines ISO (W xx/yyyy ou yyyy-Sxx) vers le mois dominant.
Règle : une semaine appartient au mois où elle contient le plus de jours (lundi=début).
"""

import re
from datetime import date, timedelta


def iso_week_to_monday(year: int, week: int) -> date:
    """Retourne le lundi de la semaine ISO (year, week)."""
    return date.fromisocalendar(year, week, 1)


def dominant_month(year: int, week: int) -> date:
    """
    Retourne la date YYYY-MM-01 du mois dominant pour une semaine ISO.
    La semaine va du lundi au dimanche (7 jours).
    On compte combien de jours tombent dans chaque mois et on prend le gagnant.
    """
    monday = iso_week_to_monday(year, week)
    days = [monday + timedelta(days=i) for i in range(7)]
    month_counts: dict[tuple, int] = {}
    for d in days:
        key = (d.year, d.month)
        month_counts[key] = month_counts.get(key, 0) + 1
    best = max(month_counts, key=lambda k: month_counts[k])
    return date(best[0], best[1], 1)


# ── Parsers ──────────────────────────────────────────────────────────────────

_RE_W_SLASH = re.compile(r"^W\s*(\d{1,2})[/\-](\d{4})$", re.IGNORECASE)
_RE_YYYY_S = re.compile(r"^(\d{4})[_\-]?S(\d{1,2})$", re.IGNORECASE)


def parse_week_column(col_name: str) -> date | None:
    """
    Essaie de parser un nom de colonne comme semaine.
    Formats supportés :
      - "W 19/2026" ou "W19/2026" ou "W 19-2026"
      - "2026-S19" ou "2026S19"
    Retourne date(YYYY, MM, 1) du mois dominant, ou None si non reconnu.
    """
    s = str(col_name).strip()

    m = _RE_W_SLASH.match(s)
    if m:
        week, year = int(m.group(1)), int(m.group(2))
        try:
            return dominant_month(year, week)
        except ValueError:
            return None

    m = _RE_YYYY_S.match(s)
    if m:
        year, week = int(m.group(1)), int(m.group(2))
        try:
            return dominant_month(year, week)
        except ValueError:
            return None

    return None


# ── Parsers mois directs ──────────────────────────────────────────────────────

_RE_M_SLASH = re.compile(r"^M\s*(\d{1,2})[/\-](\d{4})$", re.IGNORECASE)
_RE_YYYY_MM = re.compile(r"^(\d{4})[_\-](\d{1,2})$")


def parse_month_column(col_name: str) -> date | None:
    """
    Parse une colonne mensuelle directe.
    Formats supportés :
      - "M 09/2026"
      - "2026-09" / "2026_09"
    Retourne date(YYYY, MM, 1) ou None.
    """
    s = str(col_name).strip()

    m = _RE_M_SLASH.match(s)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        try:
            return date(year, month, 1)
        except ValueError:
            return None

    m = _RE_YYYY_MM.match(s)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            try:
                return date(year, month, 1)
            except ValueError:
                return None

    return None
