"""
warnings.py
Centralise toutes les alertes générées pendant la conversion.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversionWarnings:
    file_type: str = "Inconnu"
    sheet_used: str = ""
    header_row: int = -1

    ignored_columns: list[str] = field(default_factory=list)
    unrecognized_columns: list[str] = field(default_factory=list)
    duplicate_weeks: list[str] = field(default_factory=list)
    empty_refs: int = 0
    non_numeric_values: int = 0
    ignored_totals: list[str] = field(default_factory=list)

    rows_processed: int = 0
    refs_processed: int = 0
    months_generated: int = 0

    extra_notes: list[str] = field(default_factory=list)

    def add_note(self, msg: str):
        self.extra_notes.append(msg)

    def to_dict_list(self) -> list[dict]:
        """Retourne une liste de dicts {Catégorie, Détail} pour export Excel."""
        rows = []

        def add(cat, detail):
            rows.append({"Catégorie": cat, "Détail": str(detail)})

        add("Type de fichier détecté", self.file_type)
        add("Feuille utilisée", self.sheet_used)
        add("Header détecté à la ligne", self.header_row if self.header_row >= 0 else "N/A")
        add("Lignes traitées", self.rows_processed)
        add("Références traitées", self.refs_processed)
        add("Mois générés", self.months_generated)
        add("Valeurs non numériques remplacées par 0", self.non_numeric_values)
        add("Références vides ignorées", self.empty_refs)

        for c in self.ignored_columns:
            add("Colonne ignorée (total/vide)", c)
        for c in self.unrecognized_columns:
            add("Colonne non reconnue", c)
        for w in self.duplicate_weeks:
            add("Semaine dupliquée détectée", w)
        for t in self.ignored_totals:
            add("Ligne total ignorée", t)
        for n in self.extra_notes:
            add("Note", n)

        add("Date d'import", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return rows
