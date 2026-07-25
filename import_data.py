# import_data.py
import pandas as pd
from models.database import get_collection

# Charger le CSV
df = pd.read_csv('data/processed/final_data.csv')

# Se connecter à la collection 'donnees_finales'
collection = get_collection('donnees_finales')

# Supprimer les anciennes données (si existantes)
collection.delete_many({})

# Insérer les nouvelles données
records = df.to_dict('records')
result = collection.insert_many(records)

print(f"✅ {len(result.inserted_ids)} documents importés dans MongoDB.")