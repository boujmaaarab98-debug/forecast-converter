# 📊 Forecast Converter — V1

Système Python pour convertir automatiquement des fichiers Excel de prévisionnel client vers un format mensuel standard exploitable dans Power BI.

---

## 🏗️ Architecture

```
forecast_converter/
│
├── app.py                   # Point d'entrée CLI
├── streamlit_app.py         # Interface web Streamlit
├── requirements.txt
├── README.md
│
├── converter/
│   ├── __init__.py
│   ├── reader.py            # Lecture des fichiers Excel
│   ├── detector.py          # Détection du header et du type
│   ├── transformer.py       # Transformation vers format Power BI
│   ├── week_utils.py        # Conversion semaines ISO → mois
│   ├── exporter.py          # Export Excel (3 onglets)
│   └── warnings.py          # Centralisation des alertes
│
├── data/
│   ├── input/               # Déposez vos fichiers Excel ici
│   ├── output/              # Fichiers convertis générés ici
│   └── reference/           # Base article interne (V2)
│
└── tests/
    └── test_converter.py    # Tests unitaires
```

---

## 📦 Installation

### 1. Cloner / décompresser le projet

```bash
cd forecast_converter
```

### 2. Créer un environnement virtuel (recommandé)

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## 🚀 Utilisation

### Option A : Interface web (recommandée)

```bash
streamlit run streamlit_app.py
```

Ouvrez `http://localhost:8501` dans votre navigateur.

**Étapes :**
1. Saisissez le nom du client dans la barre latérale
2. Chargez votre fichier Excel
3. Cliquez sur "Convertir"
4. Téléchargez le fichier Excel résultant

---

### Option B : Ligne de commande (CLI)

**Traiter un fichier unique :**
```bash
python app.py --input data/input/mon_fichier.xlsx --client "Client A"
```

**Traiter tous les fichiers d'un dossier :**
```bash
python app.py --input data/input/ --client "Client A"
```

**Forcer une feuille spécifique :**
```bash
python app.py --input data/input/mon_fichier.xlsx --client "Client A" --sheet "Feuil2"
```

---

## 📁 Types de fichiers supportés

### Type 1 — Prévisions semaines + mois directs
Colonnes : `Article`, `Désignation article`, `Division`, `Reliquat`, `W 19/2026`, `M 09/2026`, ...

### Type 2 — Tableau croisé pivot mensuel
Colonnes : `Row Labels` + années (2025, 2026...) en ligne 1 + mois (1-12) en ligne 2

### Type 3 — Prévisions hebdomadaires longues
Colonnes : `Cdc`, `Référence OF`, `Désignation`, `2026-S17`, `2026-S18`, ...

---

## 📤 Fichier de sortie

Le fichier Excel exporté contient **3 onglets** :

| Onglet | Contenu |
|--------|---------|
| `PowerBI_Long` | Table longue exploitable dans Power BI |
| `Format_Large` | Tableau croisé une ligne par Ref, colonnes = mois |
| `Rapport_Controle` | Alertes, statistiques, colonnes ignorées |

---

## 📊 Colonnes de la table Power BI

| Colonne | Description |
|---------|-------------|
| Client | Nom du client |
| Source_File | Nom du fichier source |
| Sheet_Name | Feuille Excel utilisée |
| File_Type | Type1, Type2 ou Type3 |
| Ref | Référence article standardisée |
| Désignation | Désignation si disponible |
| Division | Division si disponible |
| Cdc | Centre de charge si disponible |
| Reliquat | Reliquat (non intégré au calcul) |
| Date_Mois | Format YYYY-MM-01 |
| Année | Année de Date_Mois |
| Mois | Numéro du mois |
| Quantité | Quantité prévisionnelle mensuelle |
| Type_Source | Weekly / Monthly / PivotMonthly |
| Import_Date | Horodatage d'importation |

---

## 🔬 Règles de conversion semaine → mois

Une semaine ISO est assignée au **mois où elle contient le plus de jours**.

| Colonne | Exemple | Résultat |
|---------|---------|----------|
| `W 19/2026` | Semaine 19 de 2026 | `2026-05-01` |
| `W 23/2026` | Semaine 23 de 2026 | `2026-06-01` |
| `2026-S17` | Semaine 17 de 2026 | mois selon calendrier ISO |
| `M 09/2026` | Septembre 2026 | `2026-09-01` |

---

## 🧪 Tests

```bash
# Depuis le dossier racine du projet
python -m pytest tests/ -v
```

---

## 🔮 Évolutions prévues (V2)

- Intégration d'une base article interne (Ref → CodeArticle, Programme, GAMME, Coef avion)
- Remplissage automatique des colonnes du format Excel large
- Support de nouveaux types de fichiers clients
- Calcul optionnel du reliquat
- Export direct vers Power BI via API

---

## ⚙️ Ajouter un nouveau type de fichier

1. Dans `detector.py`, ajouter la logique de détection dans `detect_file_type()`.
2. Dans `transformer.py`, créer une fonction `transform_typeX()`.
3. Dans la fonction `transform()`, ajouter un `elif file_type == "TypeX"`.
4. Ajouter des tests dans `tests/test_converter.py`.

---

## 🐛 Problèmes courants

| Problème | Solution |
|----------|----------|
| Type non reconnu | Vérifier les noms de colonnes (espaces, accents, casse) |
| Header mal détecté | Utiliser `--sheet` pour forcer la feuille, ou vérifier les 20 premières lignes |
| Valeurs = 0 partout | Vérifier que les cellules contiennent des nombres et non du texte |
| Doublon de semaines | Normal — les semaines dupliquées sont sommées et signalées dans le rapport |
