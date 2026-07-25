# utils/report_generator.py
import pandas as pd
from datetime import datetime
import os

def generate_report(df, filename=None):
    """
    Génère un rapport simple (version sans PDF pour éviter les dépendances).
    Retourne le chemin du fichier texte.
    """
    if filename is None:
        filename = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    os.makedirs('reports', exist_ok=True)
    filepath = os.path.join('reports', filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("RAPPORT D'ANALYSE PRÉDICTIVE\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Date : {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n\n")
        
        if 'region' in df.columns:
            f.write(f"Nombre de régions : {df['region'].nunique()}\n")
        if 'production' in df.columns:
            f.write(f"Production moyenne : {df['production'].mean():.2f}\n")
        if 'risque' in df.columns:
            f.write(f"Régions à risque élevé : {df[df['risque']==2]['region'].nunique()}\n")
        
        f.write("\n--- Détails par région ---\n")
        if 'region' in df.columns:
            for region in df['region'].unique():
                f.write(f"\n{region} :\n")
                sub = df[df['region'] == region]
                if 'production' in sub.columns:
                    f.write(f"  Production moyenne : {sub['production'].mean():.2f}\n")
                if 'risque' in sub.columns:
                    f.write(f"  Risque moyen : {sub['risque'].mean():.2f}\n")
    
    return filepath