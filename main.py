import asyncio
import websockets
import socket
import json
import sys
from datetime import datetime
from aes.encryption import encrypt, decrypt
from diffie_hellman.diffie_hellman import generate_parameters, generate_private_key, generate_public_key, compute_shared_key

# Variables globales pour gérer l'état de la connexion
active_connections = {}  # Dictionnaire pour stocker les connexions actives
in_waiting_mode = False  # Si nous sommes en mode attente ou non

# Variables pour le chiffrement Diffie-Hellman
dh_params = None  # (p, g) paramètres pour l'échange de clés
private_key = None  # Clé privée locale
public_key = None  # Clé publique locale
shared_key = None  # Clé partagée finale après l'échange
encryption_ready = False  # État du processus de chiffrement
hello_done = False  # Flag pour suivre si le handshake hello a été effectué

# Fonction pour afficher des messages dans la console de manière cohérente
def console_print(message, with_prompt=True):
    """Affiche un message dans la console avec gestion cohérente du prompt."""
    print(f"\r{message}", flush=True)
    if with_prompt:
        print("> ", end="", flush=True)

# Obtenir l'adresse IP locale
def get_local_ip():
    try:
        # Création d'une connexion temporaire pour obtenir l'IP locale
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"  # Fallback sur localhost

# ───────────────────────── Helpers d'envoi ─────────────────────────
async def send_json(uri, payload):
    """Envoie un message JSON à l'URI spécifiée."""
    try:
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps(payload))
            return ws
    except Exception as e:
        console_print(f"Erreur d'envoi: {e}")
        return None

async def send_hello(uri, i_generate):
    """Envoie un message hello pour initier la connexion."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    await send_json(uri, {
        "type": "hello",
        "sender": username,
        "i_generate": i_generate,
        "timestamp": timestamp,
        "sender_port": port
    })
    console_print(f"[{timestamp}] Initialisation de la connexion...", False)

async def send_dh_params(uri, p, g):
    """Envoie les paramètres Diffie-Hellman."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    await send_json(uri, {
        "type": "dh_params",
        "sender": username,
        "p": p,
        "g": g,
        "timestamp": timestamp,
        "sender_port": port
    })
    console_print(f"[{timestamp}] Paramètres Diffie-Hellman envoyés", False)

async def send_dh_public_key(uri, pub_key):
    """Envoie la clé publique Diffie-Hellman."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    await send_json(uri, {
        "type": "dh_public_key",
        "sender": username,
        "public_key": pub_key,
        "timestamp": timestamp,
        "sender_port": port
    })
    console_print(f"[{timestamp}] Clé publique envoyée", False)

async def send_message(uri, message_text):
    """Envoie un message texte."""
    try:
        async with websockets.connect(uri) as ws:
            timestamp = datetime.now().strftime("%H:%M:%S")
            await ws.send(json.dumps({
                "type": "text",
                "sender": username,
                "message": encrypt(message_text, shared_key),
                "timestamp": timestamp,
                "sender_port": port
            }))
            
            # Attendre la confirmation
            try:
                response = await ws.recv()
                data = json.loads(response)
                if data.get("type") != "ack":  # Si ce n'est pas une confirmation
                    console_print(f"[{data['timestamp']}] {data['sender']}: {decrypt(data['message'], shared_key)}")
            except Exception as e:
                # Ignorer les erreurs de réception - le message a peut-être été envoyé malgré tout
                pass
        
        # Ajouter un prompt après l'envoi
        print("> ", end="", flush=True)
    except Exception as e:
        console_print(f"Erreur d'envoi: {e}")

# Gestion des connexions entrantes
async def handle_connection(websocket): 
    global port, active_connections, dh_params, private_key, public_key, shared_key, encryption_ready, hello_done
    try:
        # Extraire l'adresse IP du client qui se connecte
        remote_ip = websocket.remote_address[0] if hasattr(websocket, 'remote_address') else None
        remote_port = None

        async for message in websocket:
            try:
                data = json.loads(message)
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Vérifier le type de message
                message_type = data.get('type', 'text')
                
                # ───────── hello ─────────
                if message_type == 'hello':
                    if hello_done and in_waiting_mode:
                        # Si déjà négocié en mode attente, on continue
                        continue
                    
                    hello_done = True
                    console_print(f"[{timestamp}] Demande de connexion reçue", False)
                    
                    if (not data["i_generate"]) and dh_params is None:  # c'est à moi de générer
                        p, g = generate_parameters()
                        dh_params = (p, g)
                        private_key = generate_private_key(p)
                        public_key = generate_public_key(p, g, private_key)
                        
                        console_print(f"[{timestamp}] Génération des paramètres de chiffrement...", False)
                        await send_dh_params(f"ws://{remote_ip}:{data['sender_port']}", p, g)
                        await send_dh_public_key(f"ws://{remote_ip}:{data['sender_port']}", public_key)
                    
                    print("> ", end="", flush=True)
                
                # ──────── (p,g) ──────────
                elif message_type == 'dh_params':
                    # Paramètres Diffie-Hellman reçus
                    p, g = data['p'], data['g']
                    console_print(f"[{timestamp}] Paramètres Diffie-Hellman reçus", False)
                    
                    # Stocker les paramètres
                    dh_params = (p, g)
                    
                    # Générer la paire de clés
                    private_key = generate_private_key(p)
                    public_key = generate_public_key(p, g, private_key)
                    
                    # Envoyer notre clé publique en réponse
                    await send_dh_public_key(f"ws://{remote_ip}:{data['sender_port']}", public_key)
                    print("> ", end="", flush=True)
                
                # ───── clé publique ──────
                elif message_type == 'dh_public_key':
                    if dh_params is None:
                        console_print(f"[{timestamp}] Erreur: Clé publique reçue mais paramètres manquants")
                        continue
                    
                    # Clé publique du correspondant reçue
                    other_public = data['public_key']
                    console_print(f"[{timestamp}] Clé publique reçue", False)
                    
                    # Calculer la clé partagée
                    p = dh_params[0]
                    shared_key = compute_shared_key(p, other_public, private_key)
                    encryption_ready = True
                    
                    console_print(f"[{timestamp}] Chiffrement établi avec succès! 🔒")
                
                # ───────── texte ─────────
                else:
                    # C'est un message texte normal
                    formatted_message = f"[{timestamp}] {data['sender']}: {decrypt(data['message'], shared_key)}" 
                    console_print(formatted_message)
                
                # Traiter les informations de l'expéditeur si disponibles
                if remote_ip and 'sender_port' in data:
                    remote_port = int(data['sender_port'])
                    connection_key = f"{remote_ip}:{remote_port}"
                    
                    # Vérifier si cette connexion existe déjà dans notre registre
                    is_new_connection = connection_key not in active_connections
                    
                    # Si c'est une nouvelle connexion, l'enregistrer
                    if is_new_connection:
                        # Enregistrer cette connexion pour un usage futur
                        active_connections[connection_key] = {
                            "ip": remote_ip,
                            "port": remote_port
                        }
                        
                        # Créer une tâche pour gérer les entrées utilisateur vers ce client
                        # seulement si nous sommes en mode attente et ce n'est pas un message de configuration
                        if in_waiting_mode and message_type not in ('hello', 'dh_params', 'dh_public_key'):
                            asyncio.create_task(handle_user_input(remote_ip, remote_port))
                            console_print(f"Connexion établie avec {remote_ip}:{remote_port}")
                
                # Envoyer une réponse de confirmation seulement pour les messages texte
                if message_type == 'text' or message_type == 'ack':
                    await websocket.send(json.dumps({
                        "type": "ack",
                        "sender": username,
                        "message": "_Message reçu_",
                        "timestamp": timestamp,
                        "sender_port": port
                    }))
            except json.JSONDecodeError:
                console_print(f"Erreur de décodage JSON: {message}")
                continue
    except websockets.exceptions.ConnectionClosed:
        console_print("L'autre personne s'est déconnectée.")
    except Exception as e:
        console_print(f"Erreur de connexion: {e}")

async def begin_handshake(target_ip, target_port):
    """Initialise le processus d'établissement de connexion et d'échange de clés."""
    global hello_done, dh_params, private_key, public_key
    
    if hello_done:
        return
    hello_done = True
    
    # Déterminer qui génère les paramètres basé sur les adresses IP et ports
    def _id(ip, p):
        return tuple(map(int, ip.split('.'))) + (p,)
    
    i_generate = _id(get_local_ip(), port) < _id(target_ip, target_port)
    
    # Si je génère, le faire avant tout envoi réseau
    if i_generate:
        p, g = generate_parameters()
        dh_params = (p, g)
        private_key = generate_private_key(p)
        public_key = generate_public_key(p, g, private_key)
        console_print("Génération des paramètres de chiffrement...", False)
    
    # Envoyer le hello avec mon rôle défini
    await send_hello(f"ws://{target_ip}:{target_port}", i_generate)
    
    # Si je suis générateur, envoyer (p,g) + ma clé publique
    if i_generate:
        await send_dh_params(f"ws://{target_ip}:{target_port}", p, g)
        await send_dh_public_key(f"ws://{target_ip}:{target_port}", public_key)
    
    console_print("", True)  # Afficher le prompt une seule fois à la fin

# Fonction pour gérer les entrées utilisateur
async def handle_user_input(target_ip, target_port):
    global encryption_ready
    target_uri = f"ws://{target_ip}:{target_port}"
    
    # Initialiser le handshake si en mode actif
    if not in_waiting_mode and not hello_done:
        await begin_handshake(target_ip, target_port)
    
    while True:
        message = await asyncio.get_event_loop().run_in_executor(None, lambda: input())
        if message.lower() == "exit":
            console_print("Fermeture de l'application...", False)
            sys.exit(0)
        
        asyncio.create_task(send_message(target_uri, message))

# Fonction principale
async def main():
    global username, port, in_waiting_mode  # Définir les variables globales
    
    print("Chat Peer-to-Peer chiffré avec Diffie-Hellman/AES-256 basé sur WebSocket")
    print("Version 1.0")
    print("Développé par Nino Belaoud & Ferréol DUBOIS COLI")
    print("-----------------------")
    
    # Demander le nom d'utilisateur
    username = input("Entrez votre nom d'utilisateur: ")
    if not username:
        username = f"User_{socket.gethostname()}"
        print(f"Nom d'utilisateur par défaut: {username}")
    
    # Demander le port
    port_str = input("Entrez le port à utiliser (défaut: 8765): ")
    port = 8765
    if port_str.strip():
        try:
            port = int(port_str)
        except ValueError:
            print("Port invalide, utilisation du port par défaut: 8765")
    
    # Afficher l'IP locale
    local_ip = get_local_ip()
    print(f"\nVotre adresse IP: {local_ip}:{port}")
    
    # Démarrer le serveur en arrière-plan
    server = await websockets.serve(handle_connection, "0.0.0.0", port)
    print(f"En attente de connexions sur {local_ip}:{port}")
    
    # Demander le mode de connexion
    choice = input("\nVoulez-vous vous connecter à quelqu'un? \nSi vous avez l'adresse de la personne à contacter, entrez 'o', sinon transmettez votre adresse IP à l'autre personne et entrez 'n' pour attendre une connexion. \n\nVotre réponse (o/n):  ").lower()

    if choice == 'o' or choice == 'oui':
        in_waiting_mode = False  # Mode connexion active
        target_ip = input("Entrez l'adresse IP de l'autre personne: ")
        target_port_str = input(f"Entrez le port de l'autre personne (défaut: {port}): ")
        target_port = port
        if target_port_str.strip():
            try:
                target_port = int(target_port_str)
            except ValueError:
                print(f"Port invalide, utilisation du port: {port}")
        
        print(f"\nConnexion à {target_ip}:{target_port}...")
        print("Tapez votre message et appuyez sur Entrée pour envoyer.")
        print("Tapez 'exit' pour quitter.")
        print("> ", end="", flush=True)
        
        await handle_user_input(target_ip, target_port)
    else:
        in_waiting_mode = True  # Mode attente de connexion
        print("\nEn attente que quelqu'un se connecte à vous...")
        print("Tapez 'exit' pour quitter.")
        print("Quand quelqu'un se connecte, vous pourrez lui répondre automatiquement.")
        print("> ", end="", flush=True)
        
        # En mode attente, permettre quand même à l'utilisateur de quitter
        while True:
            cmd = await asyncio.get_event_loop().run_in_executor(None, input)
            if cmd.lower() == "exit":
                console_print("Fermeture de l'application...", False)
                sys.exit(0)
            # Si nous avons une connexion active et que l'utilisateur tape quelque chose
            elif active_connections:
                # Prendre la première connexion active
                first_connection = list(active_connections.values())[0]
                asyncio.create_task(send_message(
                    f"ws://{first_connection['ip']}:{first_connection['port']}", 
                    cmd
                ))
    
    # Attendre indéfiniment (jusqu'à interruption)
    await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nFermeture de l'application...")
        sys.exit(0)