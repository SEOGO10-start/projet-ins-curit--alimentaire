# auth.py
import bcrypt
import yaml
import streamlit as st

def load_config():
    with open('auth_config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def verify_credentials(username, password):
    config = load_config()
    users = config['credentials']['usernames']
    if username not in users:
        return None
    stored_hash = users[username]['password']
    if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
        return users[username]
    return None

def login_widget():
    """Affiche le formulaire de connexion et gère la session."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.name = None

    if not st.session_state.authenticated:
        st.sidebar.subheader("🔐 Connexion")
        username = st.sidebar.text_input("Nom d'utilisateur")
        password = st.sidebar.text_input("Mot de passe", type="password")
        if st.sidebar.button("Se connecter"):
            user = verify_credentials(username, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = user['role']
                st.session_state.name = user['name']
                st.sidebar.success(f"Bienvenue {user['name']} !")
                st.rerun()
            else:
                st.sidebar.error("Identifiants incorrects")
        return False
    else:
        st.sidebar.write(f"👤 **{st.session_state.name}**")
        st.sidebar.write(f"📋 Rôle : **{st.session_state.role}**")
        if st.sidebar.button("Se déconnecter"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.role = None
            st.session_state.name = None
            st.rerun()
        return True