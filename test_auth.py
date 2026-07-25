# test_auth.py
import bcrypt
import yaml

with open('auth_config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

users = config['credentials']['usernames']
test_passwords = {
    "admin": "admin123",
    "analyste": "analyste123",
    "decideur": "decideur123"
}

print("🔍 Test de correspondance des mots de passe")
print("-" * 40)

for username, plain_password in test_passwords.items():
    if username not in users:
        print(f"❌ Utilisateur '{username}' non trouvé")
        continue
    stored_hash = users[username]['password']
    is_valid = bcrypt.checkpw(plain_password.encode('utf-8'), stored_hash.encode('utf-8'))
    if is_valid:
        print(f"✅ {username}: Mot de passe CORRECT")
    else:
        print(f"❌ {username}: Mot de passe INCORRECT")