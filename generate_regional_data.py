# generate_synthetic_data.py (ou generate_regional_data.py)
import pandas as pd
import numpy as np
from pathlib import Path

def generate_regional_data(regions=None, years=None, output_file='data/processed/final_data.csv'):
    """
    Génère des données synthétiques régionales pour le Burkina Faso.
    Retourne un DataFrame et sauvegarde le CSV.
    """
    # 1. Définition des régions et des paramètres
    if regions is None:
        regions = [
            "Boucle du Mouhoun", "Cascades", "Centre", "Centre-Est", "Centre-Nord",
            "Centre-Ouest", "Centre-Sud", "Est", "Hauts-Bassins", "Nord",
            "Plateau-Central", "Sahel", "Sud-Ouest"
        ]

    if years is None:
        years = list(range(2020, 2026))

    # Production céréalière moyenne (tonnes)
    production_moyenne = {
        "Boucle du Mouhoun": 120000,
        "Cascades": 80000,
        "Centre": 150000,
        "Centre-Est": 100000,
        "Centre-Nord": 90000,
        "Centre-Ouest": 95000,
        "Centre-Sud": 70000,
        "Est": 110000,
        "Hauts-Bassins": 200000,
        "Nord": 85000,
        "Plateau-Central": 85000,
        "Sahel": 60000,
        "Sud-Ouest": 180000
    }

    # Pluviométrie moyenne (mm)
    pluviometrie_moyenne = {
        "Boucle du Mouhoun": 800,
        "Cascades": 1100,
        "Centre": 900,
        "Centre-Est": 850,
        "Centre-Nord": 700,
        "Centre-Ouest": 850,
        "Centre-Sud": 900,
        "Est": 850,
        "Hauts-Bassins": 1000,
        "Nord": 600,
        "Plateau-Central": 750,
        "Sahel": 450,
        "Sud-Ouest": 1200
    }

    superficie_moyenne = {
        "Boucle du Mouhoun": 180000,
        "Cascades": 100000,
        "Centre": 250000,
        "Centre-Est": 150000,
        "Centre-Nord": 130000,
        "Centre-Ouest": 140000,
        "Centre-Sud": 100000,
        "Est": 160000,
        "Hauts-Bassins": 300000,
        "Nord": 120000,
        "Plateau-Central": 120000,
        "Sahel": 90000,
        "Sud-Ouest": 250000
    }

    data = []
    np.random.seed(42)  # pour reproductibilité

    for year in years:
        for region in regions:
            # Production avec tendance à la baisse
            base_prod = production_moyenne[region]
            trend = -0.02 * (year - 2020)
            variation_prod = np.random.normal(1.0 + trend, 0.12)
            production = max(base_prod * variation_prod, 10000)

            # Pluviométrie
            base_pluie = pluviometrie_moyenne[region]
            variation_pluie = np.random.normal(1.0, 0.15)
            pluviometrie = max(base_pluie * variation_pluie, 100)

            # Superficie
            base_superficie = superficie_moyenne[region]
            variation_superficie = np.random.normal(1.0, 0.05)
            superficie = base_superficie * variation_superficie

            # Sécheresse Sahel après 2022
            if region == "Sahel" and year > 2022:
                pluviometrie *= 0.85

            # Calcul du risque
            besoin = superficie * 0.0003
            ratio = production / besoin if besoin > 0 else 0
            if ratio > 1.5:
                risque = 0
            elif ratio > 0.9:
                risque = 1
            else:
                risque = 2

            # Bruit aléatoire sur le risque
            if np.random.rand() < 0.05:
                risque = np.random.choice([0,1,2], p=[0.3,0.4,0.3])

            data.append({
                "region": region,
                "year": year,
                "production": round(production, 0),
                "pluviometrie": round(pluviometrie, 1),
                "superficie": round(superficie, 0),
                "risque": risque
            })

    df = pd.DataFrame(data)

    # Sauvegarde
    output_dir = Path(output_file).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    print(f"✅ Données synthétiques générées : {len(df)} lignes.")
    print(f"📁 Fichier sauvegardé : {output_file}")
    print("\nAperçu :")
    print(df.head(10))
    print("\nRépartition des risques :")
    print(df['risque'].value_counts().sort_index())

    return df

if __name__ == "__main__":
    # Exécution directe
    generate_regional_data()