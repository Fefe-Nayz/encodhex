import secrets

# Tester si un nombre est premier
def is_probable_prime(n, k=20):
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False

    r, d = 0, n - 1
    while d % 2 == 0:
        d //= 2
        r += 1

    for _ in range(k):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True

# Générer un nombre premier p = 2q+1 p et q premiers
def generate_safe_prime(bits=256):
    while True:
        # Nombre impairs aléatoirs 256 bits
        q = secrets.randbits(bits - 1) | 1
        if is_probable_prime(q):
            # Nombre sure
            p = 2 * q + 1
            # Verifier si il est premier
            if is_probable_prime(p):
                return p, q

# Trouver un générateur sur
def generate_generator(p, q):
    while True:
        g = secrets.randbelow(p - 2) + 2
        if pow(g, q, p) != 1:
            return g

# Générer une clé privée
def generate_private_key(p):
    return secrets.randbelow(p - 3) + 2

# Générer une clé publique
def generate_public_key(p, g, a):
    return pow(g, a, p)

# Calculer la clé finale
def compute_shared_key(p, other_public, private_key):
    return pow(other_public, private_key, p)

def generate_parameters(bits=256):
    (p, q) = generate_safe_prime(bits)
    g = generate_generator(p, q)
    return (p, g)