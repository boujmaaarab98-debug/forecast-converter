"""
streamlit_app.py
Interface web simple pour le convertisseur de prévisionnel.

Lancer avec :
    streamlit run streamlit_app.py
"""

import io
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent))

from converter.reader import load_all_sheets_raw
from converter.detector import detect_header_row, build_dataframe_from_header, detect_file_type, identify_best_sheet
from converter.transformer import transform
from converter.exporter import export_all
from converter.warnings import ConversionWarnings

# ── Config page ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Convertisseur Prévisionnel",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Convertisseur de Fichiers Prévisionnels")
st.markdown("Convertissez vos fichiers Excel clients vers un format mensuel standard exploitable dans Power BI.")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Configuration")
    client_name = st.text_input("Nom du client", value="Client A", placeholder="Ex : Airbus, Safran...")
    st.markdown("---")
    st.markdown("**Types supportés :**")
    st.markdown("- Type 1 : Prévisions W xx/yyyy + M mm/yyyy")
    st.markdown("- Type 2 : Tableau croisé pivot année/mois")
    st.markdown("- Type 3 : Hebdomadaire yyyy-Sxx")

# ── Upload ────────────────────────────────────────────────────────────────────

uploaded = st.file_uploader(
    "📁 Chargez votre fichier Excel (.xlsx)",
    type=["xlsx", "xls"],
    help="Le système détectera automatiquement le format."
)

if uploaded is not None:
    st.success(f"Fichier chargé : **{uploaded.name}**")

    # Sauvegarde temporaire
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(uploaded.read())
        tmp_path = Path(tmp.name)

    try:
        # Lecture brute
        sheets = load_all_sheets_raw(tmp_path)
        sheet_names = list(sheets.keys())

        with st.expander("📋 Feuilles disponibles", expanded=False):
            st.write(sheet_names)

        # Sélection feuille
        col1, col2 = st.columns([2, 1])
        with col1:
            sheet_choice = st.selectbox(
                "Sélectionner une feuille (ou laisser 'Auto')",
                options=["Auto"] + sheet_names,
            )

        # Détection
        warn = ConversionWarnings()

        if sheet_choice == "Auto":
            used_sheet, df_clean, hrow, ftype = identify_best_sheet(sheets)
            raw_df = sheets[used_sheet]
        else:
            used_sheet = sheet_choice
            raw_df = sheets[used_sheet]
            hrow = detect_header_row(raw_df)
            df_clean = build_dataframe_from_header(raw_df, hrow)
            ftype = detect_file_type(df_clean)

        warn.file_type = ftype
        warn.sheet_used = used_sheet
        warn.header_row = hrow

        # Affichage des infos détectées
        st.markdown("---")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("📄 Feuille utilisée", used_sheet)
        col_b.metric("🔍 Type détecté", ftype)
        col_c.metric("📌 Header ligne", hrow)

        if ftype == "Inconnu":
            st.warning(
                "⚠️ Type de fichier non reconnu. "
                "Vérifiez que les colonnes correspondent aux types supportés."
            )
            st.write("**Colonnes détectées :**", list(df_clean.columns))
        else:
            st.info(f"✅ Le fichier a été reconnu comme **{ftype}**. Prêt à convertir.")

        # Aperçu des données brutes
        with st.expander("👁️ Aperçu des données brutes (10 premières lignes)", expanded=False):
            st.dataframe(df_clean.head(10), use_container_width=True)

        # Bouton de conversion
        st.markdown("---")
        if st.button("🚀 Convertir", type="primary", disabled=(ftype == "Inconnu")):
            with st.spinner("Conversion en cours..."):
                long_df = transform(
                    df=df_clean,
                    file_type=ftype,
                    client=client_name if client_name else "Client non renseigné",
                    source_file=uploaded.name,
                    sheet_name=used_sheet,
                    warn=warn,
                    raw_df=raw_df,
                    header_row=hrow,
                )

            # Métriques de résultat
            st.markdown("### ✅ Conversion terminée")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Lignes traitées", warn.rows_processed)
            c2.metric("Références", warn.refs_processed)
            c3.metric("Mois générés", warn.months_generated)
            c4.metric("Alertes", len(warn.duplicate_weeks) + warn.non_numeric_values + warn.empty_refs)

            # Aperçu Power BI
            if not long_df.empty:
                with st.expander("📊 Aperçu table Power BI (20 premières lignes)", expanded=True):
                    st.dataframe(long_df.head(20), use_container_width=True)

            # Alertes
            if warn.duplicate_weeks or warn.non_numeric_values or warn.unrecognized_columns:
                with st.expander("⚠️ Alertes détectées", expanded=True):
                    if warn.duplicate_weeks:
                        st.warning(f"Semaines dupliquées : {', '.join(warn.duplicate_weeks)}")
                    if warn.non_numeric_values:
                        st.warning(f"Valeurs non numériques remplacées par 0 : {warn.non_numeric_values}")
                    if warn.unrecognized_columns:
                        st.info(f"Colonnes non reconnues : {', '.join(warn.unrecognized_columns)}")

            # Export
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as out_tmp:
                out_path = Path(out_tmp.name)

            export_all(long_df, warn, out_path,
                       client_name if client_name else "Client non renseigné")

            with open(out_path, "rb") as f:
                excel_bytes = f.read()

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_filename = f"{Path(uploaded.name).stem}_converti_{ts}.xlsx"

            st.markdown("---")
            st.markdown("### 📥 Téléchargement")
            st.download_button(
                label="⬇️ Télécharger le fichier Excel (3 onglets)",
                data=excel_bytes,
                file_name=out_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement : {e}")
        st.exception(e)

    finally:
        tmp_path.unlink(missing_ok=True)

else:
    st.info("👆 Commencez par charger un fichier Excel ci-dessus.")
    st.markdown("""
    ### Comment ça marche ?
    1. **Chargez** votre fichier Excel client.
    2. **Saisissez** le nom du client dans la barre latérale.
    3. **Cliquez** sur "Convertir".
    4. **Téléchargez** le fichier Excel avec 3 onglets :
       - `PowerBI_Long` — table longue pour Power BI
       - `Format_Large` — tableau croisé par mois
       - `Rapport_Controle` — alertes et statistiques
    """)
