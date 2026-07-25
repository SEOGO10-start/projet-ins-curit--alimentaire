# generate_hashes.py
import bcrypt

def hash_password(password):
    """Génère un hash bcrypt pour un mot de passe"""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

# Définir les mots de passe que vous voulez utiliser
users = {
    "admin": "admin123",
    "analyste": "analyste123",
    "decideur": "decideur123"
}

print("=" * 50)
print("COPIEZ CES HACHAGES DANS auth_config.yaml")
print("=" * 50)
print()

for username, password in users.items():
    hashed = hash_password(password)
    print(f"{username}: {hashed}")