# Projet d'analyse prédictive de l'insécurité alimentaire

## Installation
1. Cloner le dépôt
2. `python -m venv venv && source venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python -m models.ml_model` pour entraîner le modèle
5. `streamlit run app.py`

## Sources de données
- FAO Stat
- WFP VAM
- Open-Meteo

## Structure
- `app.py` : Interface Streamlit
- `models/` : Modèle ML et base de données
- `data/` : Données brutes et traitées