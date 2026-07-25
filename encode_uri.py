from urllib.parse import quote_plus

# Vos identifiants bruts
username = "moussaseogo74_db_user"
password = "VOTRE_MOT_DE_PASSE_AVEC_CARACTERES_SPECIAUX"  # <-- remplacez

# Encodage
encoded_user = quote_plus(username)
encoded_pass = quote_plus(password)

# Construction de l'URI (format +srv recommandé)
uri = f"mongodb+srv://{encoded_user}:{encoded_pass}@ac-aktcpeq.6aedabw.mongodb.net/"

print("URI à copier dans les secrets :")
print(uri)