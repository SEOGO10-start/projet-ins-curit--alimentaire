# models/utils.py
import pandas as pd
import numpy as np
from pathlib import Path

# =================== FONCTIONS DE CHARGEMENT ===================
def load_all_raw_data():
    """
    Charge tous les fichiers CSV du dossier data/raw/
    et retourne un dictionnaire {nom_fichier: DataFrame}
    """
    data_dir = Path("data/raw")
    if not data_dir.exists():
        raise FileNotFoundError(f"Le dossier {data_dir} n'existe pas. Vérifie le chemin.")
    
    data_dict = {}
    for file in data_dir.glob("*.csv"):
        key = file.stem  # nom du fichier sans extension
        try:
            df = pd.read_csv(file, encoding='utf-8')
            data_dict[key] = df
            print(f"✅ Chargé : {key}.csv ({len(df)} lignes)")
        except Exception as e:
            print(f"❌ Erreur chargement {key}.csv : {e}")
    return data_dict


# =================== FONCTIONS DE NETTOYAGE ===================
def clean_agriculture(df):
    """Nettoie le dataframe agriculture (exemple basique)"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Exemple : supprime les doublons et les lignes vides
    df_clean = df.drop_duplicates().dropna(how='all')
    # Normalise les noms de colonnes
    df_clean.columns = df_clean.columns.str.strip().str.lower().str.replace(' ', '_')
    return df_clean


def clean_climat(df):
    """Nettoie le dataframe climat (exemple basique)"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    df_clean = df.drop_duplicates().dropna(how='all')
    df_clean.columns = df_clean.columns.str.strip().str.lower().str.replace(' ', '_')
    return df_clean


# =================== FUSION ===================
def merge_data(df_agri, df_clim, df_prix):
    """
    Fusionne les trois dataframes.
    Ici, je fais une fusion sur les colonnes communes.
    À adapter selon vos données.
    """
    # Si un dataframe est vide, on le remplace par un DataFrame vide avec des colonnes identifiables
    if df_agri is None:
        df_agri = pd.DataFrame()
    if df_clim is None:
        df_clim = pd.DataFrame()
    if df_prix is None:
        df_prix = pd.DataFrame()
    
    # Exemple : on suppose qu'il y a une colonne 'year' et 'country' pour fusionner
    # Sinon, on fait une simple concaténation horizontale (danger, car les lignes peuvent ne pas correspondre)
    # Je vous suggère de remplacer cette partie par votre propre logique de fusion.
    
    # Si toutes les colonnes sont identiques (même index), on concatène
    # Mais pour l'exemple, je fais une fusion sur les colonnes 'Year' et 'Country' (à adapter)
    # Si ces colonnes n'existent pas, on fait une concaténation naïve.
    
    common_cols = set(df_agri.columns) & set(df_clim.columns) & set(df_prix.columns)
    if common_cols:
        # Fusion step by step
        merged = pd.merge(df_agri, df_clim, on=list(common_cols), how='outer')
        merged = pd.merge(merged, df_prix, on=list(common_cols), how='outer')
        return merged
    else:
        # Concaténation horizontale si pas de colonnes communes
        # On réinitialise les index pour éviter des décalages
        df_agri = df_agri.reset_index(drop=True)
        df_clim = df_clim.reset_index(drop=True)
        df_prix = df_prix.reset_index(drop=True)
        return pd.concat([df_agri, df_clim, df_prix], axis=1)


# =================== SAUVEGARDE ===================
def save_processed_data(df, filename="final_data.csv"):
    """Sauvegarde le dataframe dans data/processed/"""
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    df.to_csv(filepath, index=False)
    print(f"✅ Données sauvegardées dans {filepath}")