# test_prediction.py
from pymongo import MongoClient
from models.ml_model import predict_risk
import sys

# 1. Connexion à la base de données MongoDB
try:
    client = MongoClient("mongodb://localhost:27017/")
    db = client["securite_alimentaire"]
    # Attention à l'orthographe exacte "preditions" utilisée dans Compass
    collection = db["preditions"]
    print("✅ Connexion réussie à MongoDB !")
except Exception as e:
    print(f"❌ Erreur de connexion à la base de données : {e}")
    sys.exit(1)

# 2. Récupération de toutes les données importées depuis le CSV
documents = list(collection.find())
print(f"📊 Nombre de documents récupérés : {len(documents)}")

if len(documents) == 0:
    print("⚠️ Aucun document trouvé dans la collection 'preditions'")
    sys.exit(0)

# 3. Boucle pour traiter chaque ligne et prédire le risque
print("🔄 Calcul des prédictions en cours...")
success_count = 0
error_count = 0

for i, doc in enumerate(documents):
    # Récupération des fonctionnalités (features) nécessaires à votre modèle
    production = doc.get("production")
    value = doc.get("value")  # ou pluviometrie selon votre CSV
    
    # Vérification que les données ne sont pas vides
    if production is not None and value is not None:
        try:
            # Maintenant nous avons 2 features, le modèle ajoutera un prix par défaut
            features = [float(production), float(value)]
            
            # Calcul du risque avec votre fonction importée
            prediction_result = predict_risk(features)
            
            # 4. Mise à jour du document directement dans MongoDB
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "risque_predit": prediction_result,
                    "risk_level": prediction_result.get('risk_level'),
                    "risk_label": prediction_result.get('risk_label', 'Inconnu'),
                    "risk_score": prediction_result.get('risk_score', 0),
                    "date_prediction": datetime.now()
                }}
            )
            success_count += 1
            
            # Afficher la progression
            if (i + 1) % 10 == 0:
                print(f"  ⏳ {i+1}/{len(documents)} traités...")
                
        except Exception as e:
            print(f"❌ Erreur lors de la prédiction pour le document {doc.get('_id', 'inconnu')}: {e}")
            error_count += 1
    else:
        print(f"⚠️ Document {doc.get('_id', 'inconnu')} ignoré : données manquantes")
        error_count += 1

print("\n" + "="*50)
print(f"✅ Traitement terminé !")
print(f"   📈 Succès: {success_count} documents")
print(f"   ❌ Erreurs: {error_count} documents")
print("="*50)

# Afficher un exemple de résultat
if success_count > 0:
    example = collection.find_one({"risque_predit": {"$exists": True}})
    if example:
        print("\n📋 Exemple de résultat:")
        print(f"   ID: {example.get('_id')}")
        print(f"   Production: {example.get('production')}")
        print(f"   Value: {example.get('value')}")
        print(f"   Niveau de risque: {example.get('risk_label', 'Inconnu')}")
        print(f"   Score: {example.get('risk_score', 0)}")
        print(f"   Probabilités: {example.get('risque_predit', {}).get('probabilities', [])}")