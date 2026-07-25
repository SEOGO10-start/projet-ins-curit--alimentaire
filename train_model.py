# train_model.py
"""
Entraîne le modèle Random Forest de prédiction du risque alimentaire
et sauvegarde le pipeline complet (imputer + scaler + classifieur)
dans models/risk_model.pkl, utilisé ensuite par models/ml_model.py.

Correction apportée par rapport à la version précédente :
- L'étiquette 'risque' brute de data/processed/final_data.csv est quasi
  constante (76/78 lignes = Faible) car la formule de génération
  synthétique (generate_regional_data.py) produit un ratio production/besoin
  toujours très supérieur au seuil de risque. Les 2 seules lignes non-Faible
  proviennent du bruit aléatoire à 5%, pas d'un vrai signal.
- On recalcule donc ici l'étiquette de risque à partir des mêmes règles que
  celles utilisées pour l'affichage dans app.py (quantiles de rendement,
  pluviométrie < 600mm, quantile de production), qui produisent une vraie
  variance corrélée aux features.
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score, roc_auc_score
from sklearn.preprocessing import label_binarize


FEATURE_COLS = ["production", "pluviometrie", "superficie"]
DATA_PATH = Path("data/processed/final_data.csv")
MODEL_DIR = Path("models")


def build_risk_label(df: pd.DataFrame) -> pd.Series:
    """Reconstruit l'étiquette de risque à partir des règles métier
    (identiques à celles de app.py::load_data), pour garantir un signal
    réel plutôt que le bruit aléatoire présent dans la colonne 'risque' brute."""
    rendement = df["production"] / df["superficie"]
    rendement = rendement.clip(upper=rendement.quantile(0.99))

    score = pd.Series(0, index=df.index)
    score += (rendement < rendement.quantile(0.33)).astype(int)
    score += (df["pluviometrie"] < 600).astype(int)
    score += (df["production"] < df["production"].quantile(0.33)).astype(int)

    risque = pd.cut(score, bins=[-1, 1, 2, 3], labels=[0, 1, 2]).astype(int)
    return risque


def main():
    df = pd.read_csv(DATA_PATH)
    df["risque_reconstruit"] = build_risk_label(df)

    print("Distribution des classes (étiquette reconstruite) :")
    print(df["risque_reconstruit"].value_counts().sort_index())
    print()

    X = df[FEATURE_COLS]
    y = df["risque_reconstruit"]

    # Split stratifié pour préserver la proportion de chaque classe,
    # y compris les classes rares (ex: seulement 2 exemples "Élevé").
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer()),
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=200,
            max_depth=6,          # limite le surapprentissage vu le peu de données
            class_weight="balanced",  # compense la rareté des classes 1 et 2
            random_state=42,
        )),
    ])

    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print("=== Rapport de classification (jeu de test) ===")
    print(classification_report(y_test, y_pred, zero_division=0))
    print("Matrice de confusion :")
    print(confusion_matrix(y_test, y_pred))

    clf = pipeline.named_steps["classifier"]
    print("\nClasses apprises par le modèle :", clf.classes_)
    print("Importance des features :", dict(zip(FEATURE_COLS, clf.feature_importances_)))

    # AUC multi-classe (one-vs-rest) — informative seulement si toutes les
    # classes sont représentées dans y_test.
    try:
        y_proba = pipeline.predict_proba(X_test)
        y_test_bin = label_binarize(y_test, classes=clf.classes_)
        auc = roc_auc_score(y_test_bin, y_proba, average="macro", multi_class="ovr")
        print(f"AUC macro (OvR): {auc:.3f}")
    except Exception as e:
        print(f"AUC non calculable sur ce split ({e})")

    # Sauvegarde
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(pipeline, MODEL_DIR / "risk_model.pkl")
    joblib.dump(FEATURE_COLS, MODEL_DIR / "feature_cols.pkl")
    print(f"\n✅ Modèle sauvegardé dans {MODEL_DIR / 'risk_model.pkl'}")


if __name__ == "__main__":
    main()
