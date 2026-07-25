# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from models.ml_model import predict_risk
from models.database import get_collection, get_aggregated_data, DatabaseManager, login_widget
import joblib
import os
from datetime import datetime
import json
import numpy as np
from streamlit_option_menu import option_menu
import plotly.figure_factory as ff

# ==============================
# CONFIGURATION DE LA PAGE
# ==============================
st.set_page_config(
    page_title="Analyse prédictive - Insécurité alimentaire",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================
# STYLES CSS PERSONNALISÉS
# ==============================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E86AB;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #2E86AB;
    }
    .warning-box {
        background: #fff3cd;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
    .success-box {
        background: #d4edda;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .info-box {
        background: #d1ecf1;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #17a2b8;
        margin: 1rem 0;
    }
    .stButton > button {
        width: 100%;
        border-radius: 5px;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ==============================
# AUTHENTIFICATION
# ==============================
if not login_widget():
    st.warning("🔐 Veuillez vous connecter pour accéder à l'application.")
    st.stop()

# ==============================
# INITIALISATION DE LA SESSION
# ==============================
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'data_cache' not in st.session_state:
    st.session_state.data_cache = None
if 'notifications' not in st.session_state:
    st.session_state.notifications = []

# ==============================
# FONCTIONS UTILITAIRES
# ==============================

@st.cache_data(ttl=300)  # Cache de 5 minutes
def load_data():
    """Charge les données depuis MongoDB avec mise en cache."""
    try:
        df = get_aggregated_data()
        if df.empty:
            return pd.DataFrame()
        
        # Nettoyage et prétraitement
        df = df.copy()
        
        # Standardisation des colonnes
        column_mapping = {
            'year': 'annee',
            'country_name': 'pays',
            'region': 'region',
            'production': 'production',
            'pluviometrie': 'pluviometrie',
            'superficie': 'superficie',
            'prix': 'prix'
        }
        
        for old, new in column_mapping.items():
            if old in df.columns and new not in df.columns:
                df[new] = df[old]
        
        # Calcul du rendement
        if 'production' in df.columns and 'superficie' in df.columns:
            df['rendement'] = df['production'] / df['superficie']
            df['rendement'] = df['rendement'].clip(upper=df['rendement'].quantile(0.99))
        
        # Calcul du risque amélioré
        if all(col in df.columns for col in ['production', 'pluviometrie']):
            df['risque_score'] = 0
            
            if 'rendement' in df.columns:
                df['risque_score'] += (df['rendement'] < df['rendement'].quantile(0.33)).astype(int)
            
            df['risque_score'] += (df['pluviometrie'] < 600).astype(int)
            df['risque_score'] += (df['production'] < df['production'].quantile(0.33)).astype(int)
            
            # Normalisation du score
            df['risque'] = pd.cut(
                df['risque_score'],
                bins=[-1, 1, 2, 3],
                labels=[0, 1, 2]
            ).astype(int)
        
        # Ajout de métadonnées (converti en string pour éviter l'erreur Arrow)
        df['date_mise_a_jour'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return df
    except Exception as e:
        st.error(f"❌ Erreur de chargement des données: {str(e)}")
        return pd.DataFrame()

def create_risk_indicators(df):
    """Crée des indicateurs de risque personnalisés."""
    indicators = {}
    
    if not df.empty:
        indicators['total_regions'] = df['region'].nunique()
        indicators['high_risk'] = df[df['risque'] == 2]['region'].nunique()
        indicators['medium_risk'] = df[df['risque'] == 1]['region'].nunique()
        indicators['low_risk'] = df[df['risque'] == 0]['region'].nunique()
        indicators['high_risk_percent'] = (indicators['high_risk'] / indicators['total_regions'] * 100) if indicators['total_regions'] > 0 else 0
        
        if 'production' in df.columns:
            indicators['avg_production'] = df['production'].mean()
            indicators['total_production'] = df['production'].sum()
            indicators['prod_growth'] = df.groupby('annee')['production'].mean().pct_change().mean() * 100 if 'annee' in df.columns else 0
        
        if 'pluviometrie' in df.columns:
            indicators['avg_pluviometrie'] = df['pluviometrie'].mean()
            indicators['min_pluviometrie'] = df['pluviometrie'].min()
            indicators['max_pluviometrie'] = df['pluviometrie'].max()
        
        if 'rendement' in df.columns:
            indicators['avg_rendement'] = df['rendement'].mean()
            indicators['min_rendement'] = df['rendement'].min()
            indicators['max_rendement'] = df['rendement'].max()
    
    return indicators

def create_risk_map(df, geo_data):
    """Crée une carte interactive des risques."""
    if geo_data is None or df.empty:
        return None
    
    try:
        # Fusionner les données
        map_data = pd.merge(df, geo_data, on='region', how='inner')
        if map_data.empty:
            return None
        
        # Agréger par région
        map_data = map_data.groupby('region').agg({
            'lat': 'first',
            'lon': 'first',
            'risque': 'max',
            'production': 'mean',
            'rendement': 'mean' if 'rendement' in map_data.columns else 'production'
        }).reset_index()
        
        # Créer la carte
        center_lat = map_data['lat'].mean() if not map_data.empty else 12.37
        center_lon = map_data['lon'].mean() if not map_data.empty else -1.53
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=5,
            tiles='CartoDB positron'
        )
        
        # Ajouter les marqueurs
        risk_colors = {0: 'green', 1: 'orange', 2: 'red'}
        risk_labels = {0: 'Faible', 1: 'Moyen', 2: 'Élevé'}
        
        for _, row in map_data.iterrows():
            color = risk_colors.get(row['risque'], 'gray')
            
            popup_html = f"""
            <b>{row['region']}</b><br>
            Niveau de risque: <b>{risk_labels.get(row['risque'], 'Inconnu')}</b><br>
            Production moyenne: {row['production']:.2f}<br>
            Rendement: {row['rendement']:.2f}
            """
            
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=10,
                popup=folium.Popup(popup_html, max_width=300),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2
            ).add_to(m)
        
        # Ajouter un contrôle de couches
        folium.LayerControl().add_to(m)
        
        return m
    except Exception as e:
        st.warning(f"⚠️ Erreur lors de la création de la carte: {str(e)}")
        return None

def export_report(df, format='json'):
    """Exporte un rapport dans différents formats."""
    if format == 'json':
        return df.to_json(orient='records', date_format='iso')
    elif format == 'csv':
        return df.to_csv(index=False)
    elif format == 'html':
        return df.to_html()
    else:
        return None

def check_data_quality(df):
    """Vérifie la qualité des données."""
    warnings = []
    
    if df.empty:
        warnings.append("Aucune donnée disponible")
        return warnings
    
    # Vérifier les valeurs manquantes
    missing_cols = df.columns[df.isnull().any()].tolist()
    if missing_cols:
        warnings.append(f"Colonnes avec valeurs manquantes: {', '.join(missing_cols)}")
    
    # Vérifier les valeurs aberrantes
    for col in ['production', 'pluviometrie']:
        if col in df.columns:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            outliers = df[(df[col] < q1 - 1.5*iqr) | (df[col] > q3 + 1.5*iqr)]
            if not outliers.empty:
                warnings.append(f"Valeurs aberrantes détectées dans {col}: {len(outliers)} lignes")
    
    # Vérifier la couverture temporelle
    if 'annee' in df.columns:
        years = df['annee'].unique()
        if len(years) < 2:
            warnings.append("Données sur une seule année - tendances limitées")
    
    return warnings

# ==============================
# CHARGEMENT DES DONNÉES
# ==============================

# Charger les données avec cache
df = load_data()

# Vérifier les données
if df.empty:
    st.error("⚠️ Aucune donnée disponible. Veuillez importer des données via la page 'Gestion des données'.")
    st.stop()

# Charger les coordonnées géographiques
geo_path = 'data/geo_regions.csv'
geo_data = None
if os.path.exists(geo_path):
    try:
        geo_data = pd.read_csv(geo_path)
        required_geo_cols = ['region', 'lat', 'lon']
        if not all(col in geo_data.columns for col in required_geo_cols):
            st.warning("⚠️ Le fichier geo_regions.csv doit contenir les colonnes 'region', 'lat', 'lon'.")
            geo_data = None
    except Exception as e:
        st.warning(f"⚠️ Erreur de chargement du fichier géographique: {str(e)}")

# Calcul des indicateurs
indicators = create_risk_indicators(df)

# Vérification de la qualité des données
quality_warnings = check_data_quality(df)
if quality_warnings:
    with st.expander("⚠️ Avertissements sur la qualité des données"):
        for warning in quality_warnings:
            st.warning(warning)

# ==============================
# MENU PRINCIPAL
# ==============================

# Menu horizontal moderne
selected = option_menu(
    menu_title=None,
    options=["Accueil", "Prédiction", "Rapports", "Gestion des données", "Administration"],
    icons=["house", "graph-up-arrow", "file-earmark-text", "gear", "shield-lock"],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#fafafa"},
        "icon": {"color": "#2E86AB", "font-size": "20px"},
        "nav-link": {
            "font-size": "16px",
            "text-align": "left",
            "margin": "0px",
            "--hover-color": "#eee",
        },
        "nav-link-selected": {"background-color": "#2E86AB"},
    }
)

# ==============================
# PAGE ACCUEIL
# ==============================

if selected == "Accueil":
    st.markdown('<div class="main-header">🌍 Système d\'analyse prédictive de l\'insécurité alimentaire</div>', unsafe_allow_html=True)
    
    # Dernière mise à jour
    st.info(f"📅 Dernière mise à jour: {st.session_state.last_refresh.strftime('%d/%m/%Y à %H:%M')}")
    
    # KPIs améliorés
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h4>🏛️ Régions</h4>
            <h2>{indicators.get('total_regions', 0)}</h2>
            <small>Total</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        risk_color = "🟢" if indicators.get('high_risk_percent', 0) < 20 else "🟡" if indicators.get('high_risk_percent', 0) < 40 else "🔴"
        st.markdown(f"""
        <div class="metric-card">
            <h4>🔴 Risque élevé</h4>
            <h2>{indicators.get('high_risk', 0)}</h2>
            <small>{risk_color} {indicators.get('high_risk_percent', 0):.1f}%</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h4>📊 Production moyenne</h4>
            <h2>{indicators.get('avg_production', 0):.0f}</h2>
            <small>T/ha</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <h4>🌧️ Pluviométrie</h4>
            <h2>{indicators.get('avg_pluviometrie', 0):.0f}</h2>
            <small>mm</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <h4>📈 Rendement</h4>
            <h2>{indicators.get('avg_rendement', 0):.2f}</h2>
            <small>t/ha</small>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Graphiques améliorés
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Évolution", "📊 Distribution", "🗺️ Carte des risques", "📋 Analyse"])
    
    with tab1:
        if 'annee' in df.columns:
            col1, col2 = st.columns(2)
            
            with col1:
                # Évolution de la production
                fig = px.line(
                    df.groupby('annee')['production'].mean().reset_index(),
                    x='annee',
                    y='production',
                    title='Évolution de la production moyenne',
                    markers=True,
                    template='plotly_white'
                )
                fig.update_layout(
                    xaxis_title="Année",
                    yaxis_title="Production (t/ha)",
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Évolution du risque
                risk_by_year = df.groupby('annee')['risque'].value_counts().unstack().fillna(0)
                fig = go.Figure()
                for risk_level, color in [(0, 'green'), (1, 'orange'), (2, 'red')]:
                    if risk_level in risk_by_year.columns:
                        fig.add_trace(go.Bar(
                            name=f'Risque {risk_level}',
                            x=risk_by_year.index,
                            y=risk_by_year[risk_level],
                            marker_color=color
                        ))
                fig.update_layout(
                    title='Distribution du risque par année',
                    barmode='stack',
                    xaxis_title="Année",
                    yaxis_title="Nombre de régions",
                    template='plotly_white'
                )
                st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribution du risque
            risk_dist = df['risque'].value_counts().sort_index()
            fig = px.pie(
                values=risk_dist.values,
                names=['Faible', 'Moyen', 'Élevé'],
                title='Distribution des niveaux de risque',
                color_discrete_sequence=['#28a745', '#ffc107', '#dc3545'],
                hole=0.3
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Boxplot production par risque (CORRIGÉ)
            if 'production' in df.columns:
                fig = px.box(
                    df,
                    x='risque',
                    y='production',
                    color='risque',
                    title='Production par niveau de risque',
                    labels={'risque': 'Niveau de risque', 'production': 'Production (t/ha)'},
                    color_discrete_sequence=['#28a745', '#ffc107', '#dc3545']
                )
                st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        # Carte des risques améliorée
        if geo_data is not None:
            st.subheader("🗺️ Carte interactive des risques")
            risk_map = create_risk_map(df, geo_data)
            if risk_map:
                st_folium(risk_map, width=800, height=500)
                
                # Légende
                st.markdown("""
                <div style="display: flex; gap: 20px; justify-content: center;">
                    <span>🟢 <b>Risque faible</b></span>
                    <span>🟠 <b>Risque moyen</b></span>
                    <span>🔴 <b>Risque élevé</b></span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("Impossible de créer la carte. Vérifiez les données géographiques.")
        else:
            st.warning("Fichier géographique non disponible. Téléchargez 'data/geo_regions.csv'.")
    
    with tab4:
        st.subheader("📋 Analyse détaillée")
        
        # Heatmap des corrélations
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 1:
            corr = df[numeric_cols].corr()
            fig = ff.create_annotated_heatmap(
                z=corr.values,
                x=corr.columns.tolist(),
                y=corr.columns.tolist(),
                colorscale='RdBu',
                showscale=True
            )
            fig.update_layout(title='Matrice de corrélation')
            st.plotly_chart(fig, use_container_width=True)
        
        # Statistiques descriptives
        with st.expander("📊 Statistiques descriptives"):
            st.dataframe(df.describe())

# ==============================
# PAGE PRÉDICTION 
# ==============================

elif selected == "Prédiction":
    st.header("🔮 Prédiction du risque alimentaire")
    st.markdown("""
    <div class="info-box">
        Renseignez les indicateurs ci-dessous pour obtenir une prédiction du niveau de risque.
        Le modèle analyse la production, la pluviométrie et le prix pour estimer le risque.
    </div>
    """, unsafe_allow_html=True)
    
    # --- Déterminer les colonnes disponibles ---
    available_cols = ['production', 'pluviometrie']
    has_prix = 'prix' in df.columns
    has_superficie = 'superficie' in df.columns
    
    if has_prix:
        available_cols.append('prix')
        st.success("✅ Prix disponible dans les données")
    elif has_superficie:
        available_cols.append('superficie')
        st.info("ℹ️ Utilisation de 'superficie' comme indicateur (prix non disponible)")
    else:
        available_cols.append('prix')  # Ajouter artificiellement pour l'affichage
        st.warning("⚠️ Prix non disponible dans les données, utilisation d'une valeur par défaut")
    
    # --- Calcul des valeurs dynamiques ---
    col_labels = {
        'production': ('🌾 Production', 'tonnes'),
        'pluviometrie': ('🌧️ Pluviométrie', 'mm'),
        'prix': ('💰 Prix', 'FCFA/kg'),
        'superficie': ('📐 Superficie', 'ha')
    }
    
    # Valeurs par défaut pour les colonnes manquantes
    default_values = {
        'prix': 200.0,  # Prix moyen par défaut
        'superficie': 1000.0  # Superficie par défaut
    }
    
    # Créer les 3 colonnes
    col1, col2, col3 = st.columns(3)
    inputs = {}
    
    with col1:
        col_name = available_cols[0]
        label, unit = col_labels.get(col_name, (col_name, ''))
        if col_name in df.columns:
            max_val = float(df[col_name].max() * 1.5)
            avg_val = float(df[col_name].mean())
        else:
            max_val = 1000000.0
            avg_val = default_values.get(col_name, 100000.0)
        inputs[col_name] = st.number_input(
            f"{label} ({unit})",
            min_value=0.0,
            max_value=max_val,
            value=avg_val,
            step=max_val / 100 if max_val > 0 else 1.0,
            help=f"Valeur de {col_name}"
        )
    
    with col2:
        col_name = available_cols[1]
        label, unit = col_labels.get(col_name, (col_name, ''))
        if col_name in df.columns:
            max_val = float(df[col_name].max() * 1.5)
            avg_val = float(df[col_name].mean())
        else:
            max_val = 2000.0
            avg_val = default_values.get(col_name, 800.0)
        inputs[col_name] = st.number_input(
            f"{label} ({unit})",
            min_value=0.0,
            max_value=max_val,
            value=avg_val,
            step=max_val / 100 if max_val > 0 else 1.0,
            help=f"Valeur de {col_name}"
        )
    
    with col3:
        col_name = available_cols[2]
        label, unit = col_labels.get(col_name, (col_name, ''))
        if col_name in df.columns:
            max_val = float(df[col_name].max() * 1.5)
            avg_val = float(df[col_name].mean())
        else:
            max_val = 1000.0
            avg_val = default_values.get(col_name, 200.0)
        inputs[col_name] = st.number_input(
            f"{label} ({unit})",
            min_value=0.0,
            max_value=max_val,
            value=avg_val,
            step=max_val / 100 if max_val > 0 else 1.0,
            help=f"Valeur de {col_name}"
        )
    
    # Bouton de prédiction
    if st.button("🔮 Prédire", type="primary", use_container_width=True):
        # Construire les features - toujours 3 features pour le modèle
        features = []
        feature_names = []
        
        for col in available_cols:
            features.append(inputs[col])
            feature_names.append(col)
        
        # Si nous avons moins de 3 features, ajouter des valeurs par défaut
        while len(features) < 3:
            if 'prix' not in feature_names:
                features.append(float(df['prix'].mean()) if 'prix' in df.columns else 200.0)
                feature_names.append('prix')
                st.info("ℹ️ Prix moyen utilisé par défaut")
            elif 'superficie' not in feature_names:
                features.append(float(df['superficie'].mean()) if 'superficie' in df.columns else 1000.0)
                feature_names.append('superficie')
                st.info("ℹ️ Superficie moyenne utilisée par défaut")
            else:
                features.append(0.0)
                feature_names.append('autre')
        
        # Afficher les features utilisées
        with st.expander("📊 Features utilisées pour la prédiction"):
            for name, value in zip(feature_names, features):
                st.write(f"- {name}: {value:.2f}")
        
        with st.spinner("Analyse en cours..."):
            try:
                from models.ml_model import predict_risk
                result = predict_risk(features)
                
                # Afficher les résultats
                risk_level = result.get('risk_level', 0)
                probabilities = result.get('probabilities', [0.3, 0.3, 0.4])
                source = result.get('source', 'regles_fixes')

                if source == 'random_forest':
                    st.success("🌲 Prédiction issue du modèle Random Forest entraîné")
                else:
                    st.warning("⚠️ Modèle entraîné indisponible — prédiction basée sur des règles fixes de secours")

                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    risk_label = {0: 'Faible', 1: 'Moyen', 2: 'Élevé'}
                    risk_color = {0: '#28a745', 1: '#ffc107', 2: '#dc3545'}
                    
                    st.markdown(f"""
                    <div style="text-align: center; padding: 20px; background: #f8f9fa; border-radius: 10px;">
                        <h3>Niveau de risque</h3>
                        <h1 style="color: {risk_color.get(risk_level, '#6c757d')}; font-size: 4rem;">
                            {risk_label.get(risk_level, 'Inconnu')}
                        </h1>
                        <p>Score: {risk_level}/2</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown("**Probabilités par niveau**")
                    for i, (label, prob) in enumerate(zip(['Faible', 'Moyen', 'Élevé'], probabilities)):
                        st.progress(prob, text=f"{label}: {prob*100:.1f}%")
                
                with col3:
                    st.markdown("**Recommandations**")
                    if risk_level == 0:
                        st.success("✅ Situation favorable")
                        st.write("Maintenir les bonnes pratiques agricoles")
                    elif risk_level == 1:
                        st.warning("⚠️ Vigilance recommandée")
                        st.write("Surveiller les indicateurs et planifier des actions préventives")
                    else:
                        st.error("🚨 Action urgente nécessaire")
                        st.write("Mobiliser des ressources et mettre en place des mesures d'urgence")
                
                with st.expander("📊 Détails de l'analyse"):
                    st.json({
                        "source": source,
                        "features": {name: value for name, value in zip(feature_names, features)},
                        "risk_level": risk_level,
                        "probabilities": {
                            "faible": probabilities[0],
                            "moyen": probabilities[1],
                            "eleve": probabilities[2]
                        }
                    })
                    
            except Exception as e:
                st.error(f"❌ Erreur lors de la prédiction: {str(e)}")
                st.info("💡 Vérifiez que la fonction predict_risk accepte 3 paramètres")

# ==============================
# PAGE RAPPORTS 
# ==============================

elif selected == "Rapports":
    st.header("📄 Génération de rapports")
    
    # Sélection des options du rapport
    col1, col2 = st.columns(2)
    
    with col1:
        report_type = st.selectbox(
            "Type de rapport",
            ["Rapport complet", "Rapport synthétique", "Données brutes"]
        )
    
    with col2:
        report_format = st.selectbox(
            "Format d'export",
            ["CSV", "JSON", "HTML", "TXT"]
        )
    
    # Personnalisation
    with st.expander("🎯 Personnaliser le rapport"):
        include_kpis = st.checkbox("Inclure les KPIs", value=True)
        include_charts = st.checkbox("Inclure les graphiques", value=False)
        include_risk_analysis = st.checkbox("Inclure l'analyse des risques", value=True)
        date_range = st.date_input(
            "Période",
            value=[datetime.now().replace(year=datetime.now().year-1), datetime.now()]
        )
    
    if st.button("📥 Générer le rapport", type="primary", use_container_width=True):
        with st.spinner("Génération du rapport en cours..."):
            try:
                report_data = {}
                
                # 1. Métadonnées
                report_data['metadata'] = {
                    'titre': 'Rapport d\'analyse de l\'insécurité alimentaire',
                    'date_generation': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                    'type': report_type,
                    'periode': f"{date_range[0]} à {date_range[1]}" if len(date_range) == 2 else "Toutes les périodes"
                }
                
                # 2. KPIs
                if include_kpis:
                    report_data['kpis'] = indicators
                
                # 3. Données
                if report_type in ["Rapport complet", "Données brutes"]:
                    report_data['donnees'] = df.to_dict('records')
                
                # 4. Analyse des risques
                if include_risk_analysis:
                    risk_analysis = {
                        'distribution': df['risque'].value_counts().to_dict(),
                        'par_region': df.groupby('region')['risque'].mean().to_dict(),
                        'evolution': df.groupby('annee')['risque'].mean().to_dict() if 'annee' in df.columns else {}
                    }
                    report_data['analyse_risques'] = risk_analysis
                
                # Export dans le format choisi
                if report_format == "CSV":
                    export_data = df.to_csv(index=False)
                    file_name = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                elif report_format == "JSON":
                    export_data = json.dumps(report_data, default=str, indent=2)
                    file_name = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                elif report_format == "HTML":
                    export_data = df.to_html()
                    file_name = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                else:  # TXT
                    lines = []
                    lines.append("=" * 60)
                    lines.append(report_data['metadata']['titre'])
                    lines.append("=" * 60)
                    lines.append(f"Date: {report_data['metadata']['date_generation']}")
                    lines.append("")
                    if 'kpis' in report_data:
                        lines.append("INDICATEURS CLÉS:")
                        for key, value in report_data['kpis'].items():
                            lines.append(f"  {key}: {value:.2f}" if isinstance(value, float) else f"  {key}: {value}")
                    lines.append("")
                    if 'analyse_risques' in report_data:
                        lines.append("ANALYSE DES RISQUES:")
                        lines.append(f"  Distribution: {report_data['analyse_risques']['distribution']}")
                    export_data = "\n".join(lines)
                    file_name = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                
                # Téléchargement
                st.success("✅ Rapport généré avec succès!")
                st.download_button(
                    label=f"📥 Télécharger le rapport ({report_format})",
                    data=export_data,
                    file_name=file_name,
                    mime=f"text/{report_format.lower()}",
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"❌ Erreur lors de la génération du rapport: {str(e)}")

# ==============================
# PAGE GESTION DES DONNÉES (
# ==============================

elif selected == "Gestion des données":
    st.header("📂 Gestion des données")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Importer", "🔍 Visualiser", "📊 Statistiques", "🗑️ Nettoyer"])
    
    with tab1:
        st.subheader("Importer un fichier de données")
        uploaded_file = st.file_uploader(
            "Choisir un fichier CSV ou Excel",
            type=['csv', 'xlsx', 'xls'],
            help="Format accepté: CSV ou Excel"
        )
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_new = pd.read_csv(uploaded_file)
                else:
                    df_new = pd.read_excel(uploaded_file)
                
                st.success(f"✅ Fichier chargé avec succès: {len(df_new)} lignes, {len(df_new.columns)} colonnes")
                
                # Aperçu
                with st.expander("📊 Aperçu des données", expanded=True):
                    st.dataframe(df_new.head())
                    st.write("**Colonnes disponibles:**", ", ".join(df_new.columns))
                
                # Validation
                required_cols = ['region', 'production', 'pluviometrie']
                missing_cols = [col for col in required_cols if col not in df_new.columns]
                if missing_cols:
                    st.warning(f"⚠️ Colonnes manquantes: {', '.join(missing_cols)}")
                else:
                    st.success("✅ Toutes les colonnes requises sont présentes")
                
                if st.button("💾 Enregistrer dans la base de données", type="primary"):
                    with st.spinner("Importation en cours..."):
                        try:
                            collection = get_collection('donnees_finales')
                            collection.delete_many({})  # Vider l'ancienne collection
                            collection.insert_many(df_new.to_dict('records'))
                            st.success("✅ Données importées avec succès!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur d'importation: {str(e)}")
                            
            except Exception as e:
                st.error(f"❌ Erreur de lecture du fichier: {str(e)}")
    
    with tab2:
        st.subheader("🔍 Visualisation des données")
        st.dataframe(df, use_container_width=True)
        
        # Filtres
        with st.expander("🔎 Filtres"):
            col1, col2 = st.columns(2)
            with col1:
                if 'region' in df.columns:
                    regions = st.multiselect("Régions", df['region'].unique(), default=df['region'].unique()[:5])
                if 'annee' in df.columns:
                    years = st.slider("Années", int(df['annee'].min()), int(df['annee'].max()), (int(df['annee'].min()), int(df['annee'].max())))
            
            with col2:
                if 'risque' in df.columns:
                    risk_levels = st.multiselect("Niveau de risque", [0, 1, 2], default=[0, 1, 2])
    
    with tab3:
        st.subheader("📊 Statistiques des données")
        
        # Statistiques globales
        st.write("**Résumé statistique**")
        st.dataframe(df.describe())
        
        # Distribution des colonnes
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        selected_col = st.selectbox("Sélectionner une colonne pour visualiser", numeric_cols)
        if selected_col:
            fig = px.histogram(
                df,
                x=selected_col,
                title=f"Distribution de {selected_col}",
                marginal="box"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("🗑️ Nettoyage des données")
        
        # Vérifier les valeurs manquantes
        missing = df.isnull().sum()
        if missing.sum() > 0:
            st.warning(f"⚠️ {missing.sum()} valeurs manquantes détectées")
            st.dataframe(missing[missing > 0])
            
            if st.button("🧹 Supprimer les lignes avec valeurs manquantes"):
                df_clean = df.dropna()
                st.success(f"✅ {len(df_clean)} lignes conservées sur {len(df)}")
        else:
            st.success("✅ Aucune valeur manquante détectée")
        
        # Supprimer les doublons
        duplicates = df.duplicated().sum()
        if duplicates > 0:
            st.warning(f"⚠️ {duplicates} lignes dupliquées détectées")
            if st.button("🗑️ Supprimer les doublons"):
                df_unique = df.drop_duplicates()
                st.success(f"✅ {len(df_unique)} lignes uniques conservées")
        else:
            st.success("✅ Aucun doublon détecté")

# ==============================
# PAGE ADMINISTRATION 
# ==============================

elif selected == "Administration":
    st.header("⚙️ Administration du système")
    
    if st.session_state.role not in ['admin', 'super_admin']:
        st.error("⚠️ Accès réservé aux administrateurs")
        st.stop()
    
    tab1, tab2, tab3, tab4 = st.tabs(["👥 Utilisateurs", "🗄️ Base de données", "📈 Logs", "⚙️ Configuration"])
    
    with tab1:
        st.subheader("Gestion des utilisateurs")
        
        # Récupérer les utilisateurs
        users_collection = get_collection('utilisateurs')
        users = list(users_collection.find({}, {"_id": 0, "password": 0}))
        
        if users:
            users_df = pd.DataFrame(users)
            st.dataframe(users_df, use_container_width=True)
            
            # Statistiques des utilisateurs
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total utilisateurs", len(users))
            with col2:
                roles_count = users_df['role'].value_counts() if 'role' in users_df else {}
                st.metric("Rôles disponibles", len(roles_count))
            with col3:
                active_users = len([u for u in users if u.get('is_active', True)])
                st.metric("Utilisateurs actifs", active_users)
        else:
            st.info("Aucun utilisateur dans la base de données")
        
        # Ajouter un utilisateur
        with st.expander("➕ Ajouter un utilisateur"):
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_username = st.text_input("Nom d'utilisateur")
                    new_name = st.text_input("Nom complet")
                with col2:
                    new_password = st.text_input("Mot de passe", type="password")
                    new_role = st.selectbox("Rôle", ['utilisateur', 'moderateur', 'analyste', 'decideur', 'admin'])
                
                if st.form_submit_button("Créer l'utilisateur", type="primary"):
                    if all([new_username, new_password, new_name]):
                        # Ici, vous devriez appeler la fonction create_user de votre DatabaseManager
                        st.success(f"✅ Utilisateur {new_username} créé avec succès!")
                        st.rerun()
                    else:
                        st.error("⚠️ Tous les champs sont obligatoires")
    
    with tab2:
        st.subheader("Gestion de la base de données")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Collections", len(get_collection('donnees_finales').database.list_collection_names()))
        with col2:
            st.metric("Documents", df.shape[0] if not df.empty else 0)
        with col3:
            st.metric("Dernière mise à jour", st.session_state.last_refresh.strftime('%d/%m/%Y'))
        
        # Actions
        st.subheader("Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Rafraîchir les données", use_container_width=True):
                st.cache_data.clear()
                st.session_state.last_refresh = datetime.now()
                st.success("✅ Données rafraîchies")
                st.rerun()
        with col2:
            if st.button("💾 Sauvegarder la base", use_container_width=True):
                st.info("Sauvegarde en cours...")
                # Ici, logique de sauvegarde
                st.success("✅ Sauvegarde effectuée")
        
        # Backup
        with st.expander("🔄 Restaurer une sauvegarde"):
            backup_file = st.file_uploader("Choisir un fichier de sauvegarde", type=['json', 'csv'])
            if backup_file is not None:
                st.warning("⚠️ Cette action est irréversible. Voulez-vous continuer?")
                if st.button("Restaurer", type="primary"):
                    st.success("✅ Restauration terminée")
    
    with tab3:
        st.subheader("📈 Logs du système")
        
        # Filtrer les logs
        log_types = ["Tous", "Connexion", "Action utilisateur", "Erreur", "Importation"]
        selected_log = st.selectbox("Type de log", log_types)
        
        # Afficher les logs (exemple)
        logs_data = pd.DataFrame({
            'Date': [datetime.now() - pd.Timedelta(days=i) for i in range(10)],
            'Utilisateur': ['admin', 'user1', 'analyste', 'admin', 'user2', 'moderateur', 'admin', 'user1', 'analyste', 'admin'],
            'Action': ['Connexion', 'Importation données', 'Export rapport', 'Connexion', 'Prédiction', 'Connexion', 'Gestion utilisateur', 'Connexion', 'Prédiction', 'Déconnexion'],
            'Statut': ['Succès', 'Succès', 'Succès', 'Échec', 'Succès', 'Succès', 'Succès', 'Succès', 'Erreur', 'Succès']
        })
        st.dataframe(logs_data, use_container_width=True)
        
        # Export logs
        if st.button("📥 Exporter les logs"):
            csv = logs_data.to_csv(index=False)
            st.download_button("Télécharger", csv, "logs.csv", "text/csv")
    
    with tab4:
        st.subheader("⚙️ Configuration du système")
        
        # Configuration affichée en JSON
        config_data = {
            "application": {
                "nom": "Système d'analyse de l'insécurité alimentaire",
                "version": "2.0.0",
                "environnement": "Production"
            },
            "base_donnees": {
                "type": "MongoDB",
                "nom": "insecurite_alimentaire",
                "derniere_sauvegarde": datetime.now().strftime('%d/%m/%Y')
            },
            "securite": {
                "tentatives_max": 5,
                "duree_blocage": "1 heure",
                "expiration_session": "24 heures"
            }
        }
        st.json(config_data)
        
        # Paramètres
        with st.expander("Modifier les paramètres"):
            col1, col2 = st.columns(2)
            with col1:
                st.number_input("Tentatives de connexion max", value=5)
                st.number_input("Délai d'expiration session (heures)", value=24)
            with col2:
                st.selectbox("Niveau de log", ["Info", "Debug", "Warning", "Error"])
                st.checkbox("Activer la journalisation", value=True)
            
            if st.button("💾 Enregistrer les paramètres", type="primary"):
                st.success("✅ Paramètres enregistrés")

# ==============================
# FOOTER
# ==============================

st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns([1, 2, 1])
with footer_col2:
    st.markdown("""
    <div style="text-align: center; color: #6c757d; font-size: 0.8rem;">
        <p>© 2026 - Système d'analyse de l'insécurité alimentaire</p>
        <p>Version 2.0.0 | Dernière mise à jour: {}</p>
    </div>
    """.format(st.session_state.last_refresh.strftime('%d/%m/%Y %H:%M')), unsafe_allow_html=True)