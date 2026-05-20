"""
app.py
Point d'entrée CLI du système de conversion de prévisionnel.

Usage :
    python app.py --input data/input/mon_fichier.xlsx --client "Client A"
    python app.py --input data/input/mon_fichier.xlsx --client "Client A" --sheet "Feuil1"
    python app.py --input data/input/ --client "Client A"   # traite tous les xlsx du dossier
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from converter.reader import load_all_sheets_raw
from converter.detector import detect_header_row, build_dataframe_from_header, detect_file_type, identify_best_sheet
from converter.transformer import transform
from converter.exporter import export_all
from converter.warnings import ConversionWarnings


def process_file(filepath: Path, client: str, sheet_name: str | None = None) -> Path:
    """
    Traite un fichier Excel et exporte les résultats.
    Retourne le chemin du fichier de sortie.
    """
    print(f"\n{'='*60}")
    print(f"  Fichier   : {filepath.name}")
    print(f"  Client    : {client}")
    print(f"{'='*60}")

    warn = ConversionWarnings()

    # 1. Lecture brute
    sheets = load_all_sheets_raw(filepath)
    print(f"  Feuilles trouvées : {list(sheets.keys())}")

    # 2. Sélection de la feuille
    if sheet_name and sheet_name in sheets:
        raw_df = sheets[sheet_name]
        hrow = detect_header_row(raw_df)
        df_clean = build_dataframe_from_header(raw_df, hrow)
        ftype = detect_file_type(df_clean)
        used_sheet = sheet_name
    else:
        used_sheet, df_clean, hrow, ftype = identify_best_sheet(sheets)
        raw_df = sheets[used_sheet]

    warn.file_type = ftype
    warn.sheet_used = used_sheet
    warn.header_row = hrow

    print(f"  Feuille utilisée  : {used_sheet}")
    print(f"  Header à la ligne : {hrow}")
    print(f"  Type détecté      : {ftype}")

    if ftype == "Inconnu":
        print("  ⚠  Type non reconnu — export du rapport uniquement.")
        warn.add_note(f"Colonnes détectées : {list(df_clean.columns)}")

    # 3. Transformation
    long_df = transform(
        df=df_clean,
        file_type=ftype,
        client=client,
        source_file=filepath.name,
        sheet_name=used_sheet,
        warn=warn,
        raw_df=raw_df,
        header_row=hrow,
    )

    print(f"  Lignes traitées   : {warn.rows_processed}")
    print(f"  Références        : {warn.refs_processed}")
    print(f"  Mois générés      : {warn.months_generated}")

    if warn.duplicate_weeks:
        print(f"  ⚠  Semaines dupliquées : {warn.duplicate_weeks}")
    if warn.non_numeric_values:
        print(f"  ⚠  Valeurs non numériques : {warn.non_numeric_values}")

    # 4. Export
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"{filepath.stem}_converti_{ts}.xlsx"
    out_path = filepath.parent.parent / "output" / out_name

    export_all(long_df, warn, out_path, client)
    print(f"\n  ✅ Fichier exporté : {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Convertisseur de fichiers prévisionnels Excel → format mensuel standard"
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Chemin vers le fichier .xlsx ou un dossier contenant des .xlsx")
    parser.add_argument("--client", "-c", default="Client non renseigné",
                        help="Nom du client (ex: 'Client A')")
    parser.add_argument("--sheet", "-s", default=None,
                        help="Nom de la feuille à utiliser (optionnel)")
    args = parser.parse_args()

    input_path = Path(args.input)

    if input_path.is_dir():
        files = list(input_path.glob("*.xlsx")) + list(input_path.glob("*.xls"))
        if not files:
            print(f"Aucun fichier Excel trouvé dans : {input_path}")
            sys.exit(1)
        for f in files:
            try:
                process_file(f, args.client, args.sheet)
            except Exception as e:
                print(f"  ❌ Erreur sur {f.name} : {e}")
    elif input_path.is_file():
        try:
            process_file(input_path, args.client, args.sheet)
        except Exception as e:
            print(f"  ❌ Erreur : {e}")
            sys.exit(1)
    else:
        print(f"Chemin introuvable : {input_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
