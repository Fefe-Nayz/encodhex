from diffie_hellman.utils import (
    generate_parameters, generate_private_key, generate_public_key, 
    compute_shared_key
)
from aes.encryption import encrypt

# Générer les paramètres DH
(p, q) = generate_parameters()
private_key_a = generate_private_key(p)
private_key_b = generate_private_key(p)

# Générer les clés publiques
public_key_a = generate_public_key(p, q, private_key_a)
public_key_b = generate_public_key(p, q, private_key_b)

# Calculer la clé partagée
shared_key_a = compute_shared_key(p, public_key_b, private_key_a)
shared_key_b = compute_shared_key(p, public_key_a, private_key_b)

print(f"Shared Key A: {shared_key_a}")
print(f"Shared Key B: {shared_key_b}")

# Chiffrer avec la clé normalisée
plaintext = "Hello, World!"
encrypted_text = encrypt(plaintext, shared_key_a)

print(f"Encrypted Text: {encrypted_text}")