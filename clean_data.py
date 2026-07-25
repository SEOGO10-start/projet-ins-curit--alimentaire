# clean_data.py
import pandas as pd
import numpy as np
from pathlib import Path

# ==============================================
# 0. FONCTION D'ENRICHISSEMENT (pivot climat)
# ==============================================

def enrich_data(df, indicator_col='indicator_code_clim', value_col='value'):
    """
    Pivote les indicateurs climatiques pour créer des colonnes dédiées (ex: pluviometrie).
    Suppose que le DataFrame contient les colonnes :
        - country_name, country_iso3, year
        - indicator_code_clim (ou colonne donnée)
        - value (ou colonne donnée)
    """
    # Vérifier les colonnes nécessaires
    required = ['country_name', 'country_iso3', 'year']
    if indicator_col not in df.columns:
        print(f"⚠️ Colonne '{indicator_col}' introuvable. Pas de pivotement.")
        return df
    if value_col not in df.columns:
        print(f"⚠️ Colonne '{value_col}' introuvable. Pas de pivotement.")
        return df
    
    # Filtrer les lignes contenant des indicateurs climatiques (si possible)
    # On conserve toutes les lignes, le pivot fera le tri.
    df_pivot = df.pivot_table(
        index=['country_name', 'country_iso3', 'year'],
        columns=indicator_col,
        values=value_col
    ).reset_index()
    
    # Renommer les colonnes connues
    rename_map = {
        'AG.LND.PRCP.MM': 'pluviometrie',
        # Ajoutez d'autres codes selon vos données
        # Ex: 'TEMP' : 'temperature',
    }
    # Appliquer le renommage uniquement sur les colonnes existantes
    df_pivot.rename(columns=rename_map, inplace=True)
    
    return df_pivot


# ==============================================
# 1. FONCTIONS DE CHARGEMENT ET NETTOYAGE
# ==============================================

def load_all_raw_data():
    """Charge tous les fichiers CSV du dossier data/raw/"""
    data_dir = Path("data/raw")
    if not data_dir.exists():
        raise FileNotFoundError(f"Le dossier {data_dir} n'existe pas.")
    
    data_dict = {}
    for file in data_dir.glob("*.csv"):
        key = file.stem
        try:
            df = pd.read_csv(file, encoding='utf-8')
            data_dict[key] = df
            print(f"✅ Chargé : {key}.csv ({len(df)} lignes)")
        except Exception as e:
            print(f"❌ Erreur chargement {key}.csv : {e}")
    return data_dict


def clean_agriculture(df, indicator_filter=None):
    """
    Nettoie le dataframe agriculture.
    Si indicator_filter est fourni (ex: 'production'), filtre les lignes 
    dont 'Indicator Name' contient cette chaîne (insensible à la casse).
    Renomme ensuite la colonne 'Value' en 'production' si elle existe.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Filtrage sur l'indicateur si demandé
    if indicator_filter:
        mask = df['Indicator Name'].str.lower().str.contains(indicator_filter.lower(), na=False)
        df = df[mask].copy()
        if df.empty:
            print(f"⚠️ Aucune ligne trouvée pour l'indicateur '{indicator_filter}'.")
            return pd.DataFrame()
    
    # Nettoyage classique
    df_clean = df.drop_duplicates().dropna(how='all')
    df_clean.columns = df_clean.columns.str.strip().str.lower().str.replace(' ', '_')
    
    if 'value' in df_clean.columns:
        df_clean = df_clean.rename(columns={'value': 'production'})
    else:
        df_clean['production'] = np.nan
    
    return df_clean


def clean_climat(df):
    """Nettoie le dataframe climat (normalise les colonnes)"""
    if df is None or df.empty:
        return pd.DataFrame()
    df_clean = df.drop_duplicates().dropna(how='all')
    df_clean.columns = df_clean.columns.str.strip().str.lower().str.replace(' ', '_')
    return df_clean


def merge_agri_climat(df_agri, df_clim):
    """
    Fusionne les dataframes agriculture et climat sur les colonnes 
    'country_name', 'country_iso3', 'year'.
    """
    if df_agri.empty or df_clim.empty:
        print("⚠️ Un des dataframes est vide, fusion impossible.")
        return pd.DataFrame()
    
    common_cols = ['country_name', 'country_iso3', 'year']
    for col in common_cols:
        if col not in df_agri.columns or col not in df_clim.columns:
            common_cols = list(set(df_agri.columns) & set(df_clim.columns))
            break
    
    if not common_cols:
        print("❌ Aucune colonne commune pour la fusion. Concaténation horizontale (risque de décalage).")
        df_agri_reset = df_agri.reset_index(drop=True)
        df_clim_reset = df_clim.reset_index(drop=True)
        merged = pd.concat([df_agri_reset, df_clim_reset], axis=1)
    else:
        merged = pd.merge(df_agri, df_clim, on=common_cols, how='outer', suffixes=('_agri', '_clim'))
    
    return merged


def save_processed_data(df, filename="final_data.csv"):
    """Sauvegarde le dataframe dans data/processed/"""
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    df.to_csv(filepath, index=False)
    print(f"✅ Données sauvegardées dans {filepath}")


# ==============================================
# 2. SCRIPT PRINCIPAL
# ==============================================

# 1. Chargement
data_dict = load_all_raw_data()
print("Fichiers détectés et chargés :", list(data_dict.keys()))

# 2. Extraction
df_agri = data_dict.get('agriculture-and-rural-development_bfa')
df_clim = data_dict.get('climate-change_bfa')

# 3. Nettoyage avec filtrage de l'indicateur 'production'
INDICATOR_KEYWORD = 'production'   # modifiez si besoin
df_agri_clean = clean_agriculture(df_agri, indicator_filter=INDICATOR_KEYWORD)
df_clim_clean = clean_climat(df_clim)

# 4. Vérification
if df_agri_clean.empty:
    print(f"⚠️ Aucune donnée pour l'indicateur '{INDICATOR_KEYWORD}'. Vérifiez le mot-clé.")
    print("Indicateurs disponibles dans df_agri :", df_agri['Indicator Name'].unique() if df_agri is not None else [])
    # On crée un dataframe vide pour continuer
    df_final = pd.DataFrame()
else:
    # 5. Fusion initiale
    df_merged = merge_agri_climat(df_agri_clean, df_clim_clean)
    
    # 6. Enrichissement : pivot des indicateurs climatiques
    #    On suppose que le dataframe fusionné contient une colonne 'indicator_code_clim'
    #    et une colonne 'value' (venant du climat).
    if not df_merged.empty and 'indicator_code_clim' in df_merged.columns:
        df_enriched = enrich_data(df_merged, indicator_col='indicator_code_clim', value_col='value')
        print("✅ Enrichissement climatique effectué.")
    else:
        print("⚠️ Pas de colonne 'indicator_code_clim' trouvée. Pas d'enrichissement.")
        df_enriched = df_merged

    # 7. Calcul du risque
    if 'production' in df_enriched.columns and not df_enriched['production'].isna().all():
        mean_prod = df_enriched['production'].mean()
        std_prod = df_enriched['production'].std()
        df_enriched['risque'] = pd.cut(
            df_enriched['production'],
            bins=[-np.inf, mean_prod - std_prod, mean_prod + std_prod, np.inf],
            labels=[2, 1, 0]
        )
        print("✅ Risque calculé avec succès.")
    else:
        print("⚠️ La colonne 'production' est absente ou entièrement vide.")
        df_enriched['risque'] = np.nan
    
    df_final = df_enriched

# 8. Sauvegarde et affichage
if not df_final.empty:
    save_processed_data(df_final)
    print("\n✅ Traitement terminé ! Aperçu du résultat :")
    print(df_final.head())
else:
    print("❌ Aucune donnée finale à sauvegarder.")