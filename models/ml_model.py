# models/ml_model.py
import joblib
import os
import numpy as np
from datetime import datetime

# Chemin vers le pipeline Random Forest entraîné par train_model.py
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "risk_model.pkl")
_model_cache = None


def _load_model():
    """Charge le pipeline entraîné une seule fois (mis en cache en mémoire)."""
    global _model_cache
    if _model_cache is None and os.path.exists(_MODEL_PATH):
        _model_cache = joblib.load(_MODEL_PATH)
    return _model_cache


def predict_risk(features):
    """
    Prédit le risque alimentaire en fonction des features.

    Utilise le pipeline Random Forest entraîné (risk_model.pkl) si présent.
    Si le modèle est introuvable ou échoue, retombe sur une logique de
    secours à seuils fixes (voir _predict_risk_rules ci-dessous) pour que
    l'application reste utilisable même sans modèle entraîné.

    Args:
        features: Liste de valeurs [production, pluviometrie, prix_ou_superficie]
                 ou [production, pluviometrie] (pour la rétrocompatibilité)

    Returns:
        dict: Résultats de la prédiction avec risk_level et probabilities
    """
    model = _load_model()
    if model is not None:
        try:
            return _predict_risk_model(features, model)
        except Exception as e:
            print(f"⚠️ Échec de la prédiction par le modèle entraîné, repli sur les règles : {e}")

    return _predict_risk_rules(features)


def _predict_risk_model(features, model):
    """Prédiction via le pipeline Random Forest réellement entraîné."""
    features = _normalize_features(features)
    prediction = model.predict([features])[0]
    proba_raw = model.predict_proba([features])[0]

    # Le modèle n'a pas toujours appris les 3 classes (ex: classe "Élevé"
    # rare dans le jeu de données) ; on réaligne les probabilités sur les
    # 3 classes [0, 1, 2] pour que l'affichage reste cohérent, en mettant
    # 0.0 pour toute classe absente de model.classes_.
    full_proba = [0.0, 0.0, 0.0]
    for cls, p in zip(model.classes_, proba_raw):
        full_proba[int(cls)] = float(p)

    risk_labels = {0: "Faible", 1: "Moyen", 2: "Élevé"}
    return {
        "risk_level": int(prediction),
        "risk_label": risk_labels.get(int(prediction), "Inconnu"),
        "probabilities": full_proba,
        "features_used": {
            "production": features[0],
            "pluviometrie": features[1],
            "superficie_ou_prix": features[2],
        },
        "source": "random_forest",
    }


def _normalize_features(features):
    """Ramène toujours la liste de features à exactement 3 valeurs,
    en complétant avec une valeur par défaut si besoin (rétrocompatibilité
    avec les appels historiques à 2 features)."""
    features = list(features)
    if len(features) == 2:
        features = features + [200.0]
    elif len(features) > 3:
        features = features[:3]
    while len(features) < 3:
        features.append(200.0)
    return features


def _predict_risk_rules(features):
    """
    Logique de secours à seuils fixes, utilisée uniquement si le modèle
    entraîné (risk_model.pkl) est introuvable ou indisponible.
    """
    try:
        # Normalisation des features - toujours s'assurer d'avoir 3 paramètres
        if len(features) == 2:
            # Si seulement 2 features, ajouter un prix par défaut
            features = list(features) + [200.0]  # Prix par défaut en FCFA/kg
            print(f"ℹ️ 2 features détectées, prix par défaut ajouté: {features}")
        elif len(features) == 3:
            features = list(features)
        else:
            # Si plus ou moins, ajuster
            if len(features) < 2:
                raise ValueError(f"Minimum 2 features requis, reçu: {len(features)}")
            features = list(features[:3])  # Prendre les 3 premiers
            while len(features) < 3:
                features.append(200.0)  # Compléter avec des valeurs par défaut
        
        # Extraire les valeurs
        production, pluviometrie, prix = features[0], features[1], features[2]
        
        # Logique de prédiction simple basée sur des règles
        risk_score = 0
        
        # Critère production (plus la production est faible, plus le risque est élevé)
        if production < 50000:
            risk_score += 1.5
        elif production < 100000:
            risk_score += 0.75
        elif production < 200000:
            risk_score += 0.25
        
        # Critère pluviométrie (moins de pluie = risque plus élevé)
        if pluviometrie < 400:
            risk_score += 1.5
        elif pluviometrie < 600:
            risk_score += 0.75
        elif pluviometrie < 800:
            risk_score += 0.25
        
        # Critère prix (prix élevé = risque plus élevé)
        if prix > 500:
            risk_score += 0.75
        elif prix > 350:
            risk_score += 0.5
        elif prix > 250:
            risk_score += 0.25
        
        # Déterminer le niveau de risque
        if risk_score <= 0.5:
            risk_level = 0  # Faible
            probabilities = [0.70, 0.20, 0.10]
            label = "Faible"
        elif risk_score <= 1.5:
            risk_level = 1  # Moyen
            probabilities = [0.15, 0.65, 0.20]
            label = "Moyen"
        else:
            risk_level = 2  # Élevé
            probabilities = [0.05, 0.15, 0.80]
            label = "Élevé"
        
        # Retourner les résultats
        return {
            'risk_level': int(risk_level),
            'risk_label': label,
            'probabilities': probabilities,
            'risk_score': round(risk_score, 2),
            'features_used': {
                'production': production,
                'pluviometrie': pluviometrie,
                'prix': prix
            },
            'source': 'regles_fixes'
        }
        
    except Exception as e:
        print(f"❌ Erreur dans predict_risk: {str(e)}")
        # Retourner un résultat par défaut
        return {
            'risk_level': 1,
            'risk_label': 'Moyen',
            'probabilities': [0.33, 0.34, 0.33],
            'error': str(e),
            'source': 'regles_fixes'
        }

# Alias conservé pour compatibilité avec du code appelant explicitement
# predict_risk_with_model (ex: notebooks, scripts de test). Redirige vers
# la même logique que predict_risk : modèle entraîné si disponible, sinon
# repli sur les règles fixes.
def predict_risk_with_model(features, model_path=None):
    if model_path is not None and model_path != _MODEL_PATH:
        # Permet de pointer vers un autre chemin de modèle si besoin
        try:
            model = joblib.load(model_path)
            return _predict_risk_model(features, model)
        except Exception as e:
            print(f"⚠️ Échec du chargement du modèle depuis {model_path} : {e}")
            return _predict_risk_rules(features)
    return predict_risk(features)