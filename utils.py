import secrets


# Générateur de nombre premier
def generate_prime_number(bits=256):
    while True:
        q = secrets.randbits(bits) | 1  # q doit être impair
        print("Generating prime number")
        print(q)
        if is_probable_prime(q):
            p = 2 * q + 1
            print(p)
            if is_probable_prime(p):
                print("Found", p)
                return (p, q)  # p est un safe prime

def is_prime(n):
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True

def is_probable_prime(n, k=10):  # k = nombre d'itérations
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False

    # Écrit n−1 comme 2^r * d
    r, d = 0, n - 1
    while d % 2 == 0:
        d //= 2
        r += 1

    # Test de primalité
    for _ in range(k):
        a = secrets.randbelow(n - 3) + 2  # 2 <= a <= n−2
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

# Nombre générateur
def prime_factors(n):
    factors = set()
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.add(d)
            n //= d
        d += 1
    if n > 1:
        factors.add(n)
    return factors

def generate_generator(p, q):
    print("Generating generator g...")
    g = 2
    while True:
      print(g)
      if pow(g, q, p) == 1:
          g += 3
      else:
          print("Found", g)
          return g

def generate_private_key(p):
    a = secrets.randbelow(p-3)+2
    print(a)
    print("Found")
    return a

def generate_public_key(p, g, a):
  return pow(g, a, p)

def generate_final_key(p, a, B):
    return pow(B, a, p)

(p, q) = generate_prime_number()
g = generate_generator(p, q)

a = generate_private_key(p)
b = generate_private_key(p)

A = generate_public_key(p, g, a)
B = generate_public_key(p, g, b)

k1 = generate_final_key(p, a, B)
k2 = generate_final_key(p, b, A)

print(k1 == k2)
print("Key: ", k1)