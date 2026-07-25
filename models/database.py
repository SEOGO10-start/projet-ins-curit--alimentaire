# models/database.py
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import bcrypt
from bson import ObjectId
import streamlit as st
import os

# ==============================
# CONFIGURATION MONGODB
# ==============================
MONGO_URI = "mongodb+srv://moussaseogo74_db_user:Mdp2025@ac-aktcpeq.6aedabw.mongodb.net/"
DATABASE_NAME = "insecurite_alimentaire"

# ==============================
# FONCTIONS DE COMPATIBILITÉ (pour app.py)
# ==============================

def connect_db():
    """
    Établit la connexion à MongoDB et retourne l'objet base de données.
    """
    client = MongoClient(MONGO_URI)
    return client[DATABASE_NAME]


def get_collection(collection_name):
    """
    Retourne une collection MongoDB à partir de son nom.
    """
    db = connect_db()
    return db[collection_name]


def get_aggregated_data():
    """
    Récupère toutes les données de la collection 'donnees_finales'
    et les retourne sous forme de DataFrame pandas.
    Si la collection est vide, tente de charger depuis le CSV.
    """
    collection = get_collection("donnees_finales")
    data = list(collection.find({}, {"_id": 0}))
    
    if not data:
        # Fallback : charger depuis le CSV
        csv_path = 'data/processed/final_data.csv'
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            collection.insert_many(df.to_dict('records'))
            print("✅ Données importées depuis CSV dans MongoDB.")
            return df
        else:
            print("⚠️ Aucune donnée trouvée ni dans MongoDB ni dans le CSV.")
            return pd.DataFrame()
    
    return pd.DataFrame(data)


# ==============================
# CLASSE DatabaseManager 
# ==============================

class DatabaseManager:
    def __init__(self):
        """Initialise la connexion à MongoDB."""
        try:
            self.client = MongoClient(MONGO_URI)
            print(f"🔍 MONGO_URI (début) : {MONGO_URI[:30]}...")  
            self.db = self.client[DATABASE_NAME]
            # Tester la connexion
            self.client.admin.command('ping')
            print("✅ Connexion à MongoDB réussie")
        except Exception as e:
            print(f"❌ Erreur de connexion à MongoDB: {e}")
            raise
    
    def get_collection(self, collection_name):
        """Retourne une collection MongoDB."""
        return self.db[collection_name]
    
    def get_aggregated_data(self):
        """Récupère toutes les données de la collection 'donnees_finales'."""
        collection = self.get_collection("donnees_finales")
        data = list(collection.find({}, {"_id": 0}))
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    # ==============================
    # GESTION DES UTILISATEURS
    # ==============================
    
    def create_user(self, username, password, name, role="utilisateur", email=None, **kwargs):
        """Crée un nouvel utilisateur dans la base de données."""
        collection = self.get_collection("utilisateurs")
        
        # Vérifier si l'utilisateur existe déjà
        if collection.find_one({"username": username}):
            return {"success": False, "message": "Cet utilisateur existe déjà"}
        
        # Hasher le mot de passe
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Créer le document utilisateur
        user_data = {
            "username": username,
            "password": hashed_password.decode('utf-8'),
            "name": name,
            "role": role,
            "email": email,
            "created_at": datetime.now(),
            "last_login": None,
            "is_active": True,
            "failed_attempts": 0,
            "locked_until": None,
            **kwargs
        }
        
        try:
            result = collection.insert_one(user_data)
            return {
                "success": True, 
                "message": f"Utilisateur {username} créé avec succès",
                "user_id": str(result.inserted_id)
            }
        except Exception as e:
            return {"success": False, "message": f"Erreur: {str(e)}"}
    
    def verify_credentials(self, username, password):
        """Vérifie les identifiants d'un utilisateur."""
        collection = self.get_collection("utilisateurs")
        
        # Chercher l'utilisateur
        user = collection.find_one({"username": username})
        if not user:
            return None
        
        # Vérifier si le compte est verrouillé
        if user.get("locked_until") and user["locked_until"] > datetime.now():
            return None
        
        # Vérifier le mot de passe
        stored_hash = user["password"]
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            # Mettre à jour last_login et réinitialiser les tentatives échouées
            collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "last_login": datetime.now(),
                        "failed_attempts": 0,
                        "locked_until": None
                    }
                }
            )
            
            # Retourner les données de l'utilisateur (sans le mot de passe)
            user_data = {
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "email": user.get("email"),
                "created_at": user.get("created_at")
            }
            return user_data
        else:
            # Incrémenter les tentatives échouées
            failed_attempts = user.get("failed_attempts", 0) + 1
            update_data = {"failed_attempts": failed_attempts}
            
            # Verrouiller le compte après 5 tentatives échouées
            if failed_attempts >= 5:
                update_data["locked_until"] = datetime.now().replace(
                    hour=datetime.now().hour + 1
                )  # Verrouillé pour 1 heure
            
            collection.update_one({"_id": user["_id"]}, {"$set": update_data})
            return None
    
    def get_user_by_username(self, username):
        """Récupère les données d'un utilisateur par son nom d'utilisateur."""
        collection = self.get_collection("utilisateurs")
        user = collection.find_one({"username": username})
        if user:
            # Supprimer le mot de passe pour des raisons de sécurité
            user.pop("password", None)
            user["_id"] = str(user["_id"])
        return user
    
    def update_user(self, username, update_data):
        """Met à jour les données d'un utilisateur."""
        collection = self.get_collection("utilisateurs")
        
        # Ne pas autoriser la mise à jour du mot de passe via cette méthode
        if "password" in update_data:
            del update_data["password"]
        
        result = collection.update_one(
            {"username": username},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    def change_password(self, username, old_password, new_password):
        """Change le mot de passe d'un utilisateur."""
        collection = self.get_collection("utilisateurs")
        
        user = collection.find_one({"username": username})
        if not user:
            return {"success": False, "message": "Utilisateur non trouvé"}
        
        # Vérifier l'ancien mot de passe
        if not bcrypt.checkpw(old_password.encode('utf-8'), user["password"].encode('utf-8')):
            return {"success": False, "message": "Ancien mot de passe incorrect"}
        
        # Hasher le nouveau mot de passe
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        collection.update_one(
            {"username": username},
            {"$set": {"password": hashed_password.decode('utf-8')}}
        )
        
        return {"success": True, "message": "Mot de passe modifié avec succès"}
    
    def delete_user(self, username):
        """Supprime un utilisateur."""
        collection = self.get_collection("utilisateurs")
        result = collection.delete_one({"username": username})
        return result.deleted_count > 0
    
    def get_all_users(self):
        """Récupère tous les utilisateurs (sans les mots de passe)."""
        collection = self.get_collection("utilisateurs")
        users = list(collection.find({}, {"password": 0}))
        for user in users:
            user["_id"] = str(user["_id"])
        return users
    
    def get_user_count(self):
        """Retourne le nombre total d'utilisateurs."""
        collection = self.get_collection("utilisateurs")
        return collection.count_documents({})
    
    # ==============================
    # GESTION DES SESSIONS
    # ==============================
    
    def create_session(self, username, session_data=None):
        """Crée une session utilisateur."""
        collection = self.get_collection("sessions")
        
        session = {
            "username": username,
            "created_at": datetime.now(),
            "expires_at": datetime.now().replace(
                hour=datetime.now().hour + 24
            ),  # Expire dans 24h
            "data": session_data or {},
            "is_active": True
        }
        
        result = collection.insert_one(session)
        return str(result.inserted_id)
    
    def get_session(self, session_id):
        """Récupère une session."""
        collection = self.get_collection("sessions")
        session = collection.find_one({
            "_id": ObjectId(session_id),
            "is_active": True,
            "expires_at": {"$gt": datetime.now()}
        })
        if session:
            session["_id"] = str(session["_id"])
        return session
    
    def end_session(self, session_id):
        """Termine une session."""
        collection = self.get_collection("sessions")
        result = collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"is_active": False}}
        )
        return result.modified_count > 0
    
    def cleanup_expired_sessions(self):
        """Supprime les sessions expirées."""
        collection = self.get_collection("sessions")
        result = collection.delete_many({
            "$or": [
                {"expires_at": {"$lt": datetime.now()}},
                {"is_active": False}
            ]
        })
        return result.deleted_count

    # ==============================
    # GESTION DES PERMISSIONS
    # ==============================
    
    def check_permission(self, username, required_role):
        """Vérifie si un utilisateur a le rôle requis."""
        user = self.get_user_by_username(username)
        if not user:
            return False
        
        roles_hierarchy = {
            "utilisateur": 1,
            "moderateur": 2,
            "admin": 3,
            "super_admin": 4
        }
        
        user_role_level = roles_hierarchy.get(user.get("role", "utilisateur"), 0)
        required_level = roles_hierarchy.get(required_role, 0)
        
        return user_role_level >= required_level
    
    # ==============================
    # GESTION DES LOGS
    # ==============================
    
    def log_action(self, username, action, details=None):
        """Enregistre une action utilisateur dans les logs."""
        collection = self.get_collection("logs")
        
        log_entry = {
            "username": username,
            "action": action,
            "details": details or {},
            "timestamp": datetime.now(),
            "ip_address": None  # À définir si disponible
        }
        
        collection.insert_one(log_entry)
    
    def get_user_logs(self, username, limit=50):
        """Récupère les logs d'un utilisateur."""
        collection = self.get_collection("logs")
        logs = list(collection.find(
            {"username": username},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit))
        return logs


# ==============================
# FONCTIONS D'AUTHENTIFICATION POUR STREAMLIT
# ==============================

def verify_credentials_streamlit(username, password):
    """Version Streamlit de la vérification des identifiants."""
    try:
        db = DatabaseManager()
        user = db.verify_credentials(username, password)
        
        if user:
            # Log de la connexion réussie
            db.log_action(username, "login_success")
            return user
        else:
            # Log de la tentative échouée
            db.log_action(username, "login_failed", {"reason": "invalid_credentials"})
            return None
    except Exception as e:
        print(f"Erreur lors de la vérification des identifiants: {e}")
        return None


def login_widget():
    """Affiche le formulaire de connexion et gère la session."""
    # Initialiser les variables de session
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.name = None
        st.session_state.user_id = None

    if not st.session_state.authenticated:
        st.sidebar.subheader("🔐 Connexion")
        username = st.sidebar.text_input("Nom d'utilisateur")
        password = st.sidebar.text_input("Mot de passe", type="password")
        
        if st.sidebar.button("Se connecter"):
            user = verify_credentials_streamlit(username, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = user.get('role', 'utilisateur')
                st.session_state.name = user.get('name', username)
                st.session_state.user_id = user.get('_id')
                
                st.sidebar.success(f"Bienvenue {user.get('name', username)} !")
                st.rerun()
            else:
                st.sidebar.error("Identifiants incorrects ou compte verrouillé")
        return False
    else:
        # Afficher les informations de l'utilisateur connecté
        st.sidebar.write(f"👤 **{st.session_state.name}**")
        st.sidebar.write(f"📋 Rôle : **{st.session_state.role}**")
        
        if st.sidebar.button("Se déconnecter"):
            # Log de la déconnexion
            try:
                db = DatabaseManager()
                db.log_action(st.session_state.username, "logout")
            except:
                pass
            
            # Réinitialiser la session
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.role = None
            st.session_state.name = None
            st.session_state.user_id = None
            st.rerun()
        return True


def require_role(required_role):
    """Décorateur pour vérifier qu'un utilisateur a le rôle requis."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not st.session_state.get('authenticated', False):
                st.error("Veuillez vous connecter")
                return None
            
            if st.session_state.get('role') != required_role and st.session_state.get('role') != 'super_admin':
                st.error(f"Accès refusé. Rôle '{required_role}' requis")
                return None
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ==============================
# INSTANCE GLOBALE DU GESTIONNAIRE
# ==============================

db_manager = DatabaseManager()


# ==============================
# CRÉER UN ADMIN AUTOMATIQUEMENT
# ==============================

def ensure_admin_exists():
    """
    Fonction de secours qui crée automatiquement un compte admin
    si aucun n'existe dans la base de données.
    """
    try:
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        
        # S'assurer que la collection existe
        if "utilisateurs" not in db.list_collection_names():
            db.create_collection("utilisateurs")
            print("✅ Collection 'utilisateurs' créée")
        
        users = db["utilisateurs"]
        
        # Vérifier si des utilisateurs existent
        if users.count_documents({}) == 0:
            print("🔧 Aucun utilisateur trouvé - Création automatique...")
            
            # Créer admin
            hashed = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt())
            admin_doc = {
                "username": "admin",
                "password": hashed.decode('utf-8'),
                "name": "Administrateur",
                "role": "super_admin",
                "email": "admin@insecurite-alimentaire.com",
                "created_at": datetime.now(),
                "last_login": None,
                "is_active": True,
                "failed_attempts": 0,
                "locked_until": None
            }
            users.insert_one(admin_doc)
            
            # Créer utilisateur standard
            hashed_user = bcrypt.hashpw("user".encode('utf-8'), bcrypt.gensalt())
            user_doc = {
                "username": "user",
                "password": hashed_user.decode('utf-8'),
                "name": "Utilisateur Standard",
                "role": "utilisateur",
                "email": "user@insecurite-alimentaire.com",
                "created_at": datetime.now(),
                "last_login": None,
                "is_active": True,
                "failed_attempts": 0,
                "locked_until": None
            }
            users.insert_one(user_doc)
            
            # Créer analyste
            hashed_analyste = bcrypt.hashpw("analyste".encode('utf-8'), bcrypt.gensalt())
            analyste_doc = {
                "username": "analyste",
                "password": hashed_analyste.decode('utf-8'),
                "name": "Analyste",
                "role": "analyste",
                "email": "analyste@insecurite-alimentaire.com",
                "created_at": datetime.now(),
                "last_login": None,
                "is_active": True,
                "failed_attempts": 0,
                "locked_until": None
            }
            users.insert_one(analyste_doc)
            
            # Créer decideur
            hashed_decideur = bcrypt.hashpw("decideur".encode('utf-8'), bcrypt.gensalt())
            decideur_doc = {
                "username": "decideur",
                "password": hashed_decideur.decode('utf-8'),
                "name": "Décideur",
                "role": "decideur",
                "email": "decideur@insecurite-alimentaire.com",
                "created_at": datetime.now(),
                "last_login": None,
                "is_active": True,
                "failed_attempts": 0,
                "locked_until": None
            }
            users.insert_one(decideur_doc)
            
            print("\n" + "=" * 50)
            print("✅ UTILISATEURS CRÉÉS AUTOMATIQUEMENT !")
            print("=" * 50)
            print("🔑 IDENTIFIANTS DE CONNEXION:")
            print("   👤 admin / admin (super_admin)")
            print("   👤 user / user (utilisateur)")
            print("   👤 analyste / analyste (analyste)")
            print("   👤 decideur / decideur (decideur)")
            print("=" * 50)
            return True
            
        # Si des utilisateurs existent mais pas admin
        elif not users.find_one({"username": "admin"}):
            print("🔧 Admin manquant - Création automatique...")
            hashed = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt())
            admin_doc = {
                "username": "admin",
                "password": hashed.decode('utf-8'),
                "name": "Administrateur",
                "role": "super_admin",
                "email": "admin@insecurite-alimentaire.com",
                "created_at": datetime.now(),
                "last_login": None,
                "is_active": True,
                "failed_attempts": 0,
                "locked_until": None
            }
            users.insert_one(admin_doc)
            print("✅ Admin créé avec succès! (admin/admin)")
            return True
            
        return False
            
    except Exception as e:
        print(f"⚠️ Erreur lors de la création automatique: {e}")
        return False


# ==============================
# APPEL AUTOMATIQUE AU CHARGEMENT
# ==============================

print("🔧 Vérification de la base de données...")
ensure_admin_exists()