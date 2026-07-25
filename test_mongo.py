from pymongo import MongoClient

uri = "mongodb+srv://moussaseogo74_db_user:Mdp2025@ac-aktcpeq.6aedabw.mongodb.net/insecurite_alimentaire"

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ Connexion réussie !")
    db = client["insecurite_alimentaire"]
    print("Bases :", client.list_database_names())
except Exception as e:
    print("❌ Erreur :", e)