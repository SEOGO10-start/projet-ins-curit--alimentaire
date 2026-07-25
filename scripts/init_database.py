# scripts/init_database.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import DatabaseManager
from datetime import datetime
import bcrypt

def initialize_database():
    """Initialise la base de données avec les collections et utilisateurs par défaut."""
    
    print("🚀 Initialisation de la base de données MongoDB...")
    
    try:
        db_manager = DatabaseManager()
        print("✅ Connexion à MongoDB établie")
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return
    
    # ==============================
    # 1. CRÉATION DES COLLECTIONS
    # ==============================
    
    collections = [
        "utilisateurs",
        "donnees_finales",
        "sessions",
        "logs",
        "rapports",
        "parametres",
        "regions"
    ]
    
    print("\n📁 Création des collections...")
    for collection_name in collections:
        try:
            db_manager.get_collection(collection_name)
            print(f"   ✅ Collection '{collection_name}' vérifiée/créée")
        except Exception as e:
            print(f"   ❌ Erreur pour {collection_name}: {e}")
    
    # ==============================
    # 2. CRÉATION DES INDEX
    # ==============================
    
    print("\n🔍 Création des index...")
    
    try:
        # Index pour les utilisateurs
        users_collection = db_manager.get_collection("utilisateurs")
        users_collection.create_index("username", unique=True)
        users_collection.create_index("email", unique=True, sparse=True)
        users_collection.create_index("role")
        print("   ✅ Index utilisateurs créés")
        
        # Index pour les sessions
        sessions_collection = db_manager.get_collection("sessions")
        sessions_collection.create_index("expires_at", expireAfterSeconds=0)
        sessions_collection.create_index("username")
        print("   ✅ Index sessions créés")
        
        # Index pour les logs
        logs_collection = db_manager.get_collection("logs")
        logs_collection.create_index("username")
        logs_collection.create_index("timestamp")
        print("   ✅ Index logs créés")
        
        # Index pour les données finales
        donnees_collection = db_manager.get_collection("donnees_finales")
        donnees_collection.create_index("pays")
        donnees_collection.create_index("annee")
        donnees_collection.create_index([("pays", 1), ("annee", -1)])
        print("   ✅ Index données finales créés")
        
    except Exception as e:
        print(f"   ⚠️ Erreur lors de la création des index: {e}")
    
    # ==============================
    # 3. CRÉATION DES UTILISATEURS PAR DÉFAUT
    # ==============================
    
    print("\n👤 Création des utilisateurs par défaut...")
    
    # Liste des utilisateurs à créer
    default_users = [
        {
            "username": "admin",
            "password": "Admin123!",
            "name": "Administrateur",
            "role": "super_admin",
            "email": "admin@insecurite-alimentaire.com"
        },
        {
            "username": "moderateur",
            "password": "Moderator123!",
            "name": "Modérateur",
            "role": "moderateur",
            "email": "moderateur@insecurite-alimentaire.com"
        },
        {
            "username": "analyste",
            "password": "Analyste123!",
            "name": "Analyste",
            "role": "analyste",
            "email": "analyste@insecurite-alimentaire.com"
        },
        {
            "username": "decideur",
            "password": "Decideur123!",
            "name": "Décideur",
            "role": "decideur",
            "email": "decideur@insecurite-alimentaire.com"
        },
        {
            "username": "user",
            "password": "User123!",
            "name": "Utilisateur Standard",
            "role": "utilisateur",
            "email": "user@insecurite-alimentaire.com"
        }
    ]
    
    created_count = 0
    for user_data in default_users:
        try:
            # Vérifier si l'utilisateur existe déjà
            users_collection = db_manager.get_collection("utilisateurs")
            existing = users_collection.find_one({"username": user_data["username"]})
            
            if existing:
                print(f"   ℹ️ Utilisateur '{user_data['username']}' existe déjà")
                continue
            
            # Hasher le mot de passe
            hashed_password = bcrypt.hashpw(
                user_data["password"].encode('utf-8'),
                bcrypt.gensalt()
            )
            
            # Créer l'utilisateur
            user_doc = {
                "username": user_data["username"],
                "password": hashed_password.decode('utf-8'),
                "name": user_data["name"],
                "role": user_data["role"],
                "email": user_data["email"],
                "created_at": datetime.now(),
                "last_login": None,
                "is_active": True,
                "failed_attempts": 0,
                "locked_until": None
            }
            
            users_collection.insert_one(user_doc)
            created_count += 1
            print(f"   ✅ Utilisateur '{user_data['username']}' créé")
            
        except Exception as e:
            print(f"   ❌ Erreur pour {user_data['username']}: {e}")
    
    print(f"\n   📊 {created_count} nouveaux utilisateurs créés")
    
    # ==============================
    # 4. DONNÉES D'EXEMPLE
    # ==============================
    
    print("\n📊 Création des données d'exemple...")
    
    try:
        donnees_collection = db_manager.get_collection("donnees_finales")
        
        # Vérifier si la collection est vide
        if donnees_collection.count_documents({}) == 0:
            sample_data = create_sample_data()
            result = donnees_collection.insert_many(sample_data)
            print(f"   ✅ {len(result.inserted_ids)} documents d'exemple insérés")
        else:
            print("   ℹ️ La collection contient déjà des données")
            
    except Exception as e:
        print(f"   ❌ Erreur lors de l'insertion des données: {e}")
    
    # ==============================
    # 5. RÉSUMÉ
    # ==============================
    
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DE L'INITIALISATION")
    print("=" * 50)
    
    try:
        users_count = db_manager.get_collection("utilisateurs").count_documents({})
        print(f"👤 Utilisateurs : {users_count}")
        
        donnees_count = db_manager.get_collection("donnees_finales").count_documents({})
        print(f"📊 Données : {donnees_count}")
        
        logs_count = db_manager.get_collection("logs").count_documents({})
        print(f"📝 Logs : {logs_count}")
        
        sessions_count = db_manager.get_collection("sessions").count_documents({})
        print(f"🔑 Sessions : {sessions_count}")
        
    except Exception as e:
        print(f"⚠️ Erreur lors du comptage: {e}")
    
    print("=" * 50)
    print("\n✅ Base de données initialisée avec succès !")
    print("\n📝 Identifiants de connexion :")
    print("   👤 Admin: admin / Admin123!")
    print("   👤 Modérateur: moderateur / Moderator123!")
    print("   👤 Analyste: analyste / Analyste123!")
    print("   👤 Décideur: decideur / Decideur123!")
    print("   👤 Utilisateur: user / User123!")
    print("\n🔐 Veuillez changer les mots de passe par défaut lors de la première connexion !")

def create_sample_data():
    """Crée des données d'exemple."""
    return [
        {
            "pays": "Niger",
            "region": "Niger",
            "annee": 2023,
            "production": 2.8,
            "pluviometrie": 450,
            "superficie": 1.2,
            "prix": 250,
            "population_affectee": 2800000,
            "pourcentage_population": 11.5,
            "niveau_insecurite": "Élevé",
            "causes": ["Sécheresse", "Conflits", "Pauvreté"],
            "coordonnees": {"type": "Point", "coordinates": [8.0, 17.6]},
            "indicateurs": {
                "malnutrition_enfants": 42.3,
                "acces_eau_potable": 52.4,
                "production_alimentaire": 65.8
            },
            "date_mise_a_jour": datetime.now()
        },
        {
            "pays": "Madagascar",
            "region": "Madagascar",
            "annee": 2023,
            "production": 1.9,
            "pluviometrie": 350,
            "superficie": 1.0,
            "prix": 300,
            "population_affectee": 1900000,
            "pourcentage_population": 7.8,
            "niveau_insecurite": "Critique",
            "causes": ["Cyclones", "Sécheresse"],
            "coordonnees": {"type": "Point", "coordinates": [47.0, -18.8]},
            "indicateurs": {
                "malnutrition_enfants": 38.5,
                "acces_eau_potable": 56.7,
                "production_alimentaire": 58.2
            },
            "date_mise_a_jour": datetime.now()
        },
        {
            "pays": "Soudan",
            "region": "Soudan",
            "annee": 2023,
            "production": 3.2,
            "pluviometrie": 500,
            "superficie": 1.5,
            "prix": 280,
            "population_affectee": 3200000,
            "pourcentage_population": 13.2,
            "niveau_insecurite": "Élevé",
            "causes": ["Conflits", "Instabilité politique"],
            "coordonnees": {"type": "Point", "coordinates": [30.0, 15.0]},
            "indicateurs": {
                "malnutrition_enfants": 44.8,
                "acces_eau_potable": 48.3,
                "production_alimentaire": 55.1
            },
            "date_mise_a_jour": datetime.now()
        },
        {
            "pays": "Mali",
            "region": "Mali",
            "annee": 2023,
            "production": 1.4,
            "pluviometrie": 400,
            "superficie": 0.8,
            "prix": 220,
            "population_affectee": 1400000,
            "pourcentage_population": 5.7,
            "niveau_insecurite": "Modéré",
            "causes": ["Sécheresse", "Conflits"],
            "coordonnees": {"type": "Point", "coordinates": [-4.0, 17.5]},
            "indicateurs": {
                "malnutrition_enfants": 35.2,
                "acces_eau_potable": 61.4,
                "production_alimentaire": 72.3
            },
            "date_mise_a_jour": datetime.now()
        },
        {
            "pays": "Burkina Faso",
            "region": "Burkina Faso",
            "annee": 2023,
            "production": 0.98,
            "pluviometrie": 380,
            "superficie": 0.6,
            "prix": 240,
            "population_affectee": 980000,
            "pourcentage_population": 4.2,
            "niveau_insecurite": "Modéré",
            "causes": ["Conflits", "Sécheresse"],
            "coordonnees": {"type": "Point", "coordinates": [-2.0, 12.3]},
            "indicateurs": {
                "malnutrition_enfants": 32.7,
                "acces_eau_potable": 64.8,
                "production_alimentaire": 75.6
            },
            "date_mise_a_jour": datetime.now()
        }
    ]

if __name__ == "__main__":
    initialize_database()