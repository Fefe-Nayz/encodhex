import asyncio
import websockets
import socket
import json
import sys
from datetime import datetime
from utils import generate_parameters, generate_private_key, generate_public_key, compute_shared_key

# Variables globales pour gérer l'état de la connexion
active_connections = {}  # Dictionnaire pour stocker les connexions actives
in_waiting_mode = False  # Si nous sommes en mode attente ou non

# Variables pour le chiffrement Diffie-Hellman
dh_params = None  # (p, g) paramètres pour l'échange de clés
private_key = None  # Clé privée locale
public_key = None  # Clé publique locale
shared_key = None  # Clé partagée finale après l'échange
encryption_ready = False  # État du processus de chiffrement

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

# Envoyer les paramètres Diffie-Hellman
async def send_dh_params(uri, p, g):
    global port
    try:
        async with websockets.connect(uri) as ws:
            timestamp = datetime.now().strftime("%H:%M:%S")
            await ws.send(json.dumps({
                "type": "dh_params",
                "sender": username,
                "p": p,
                "g": g,
                "timestamp": timestamp,
                "sender_port": port
            }))
            print(f"\r[{timestamp}] Paramètres Diffie-Hellman envoyés")
            print("> ", end="", flush=True)
    except Exception as e:
        print(f"\nErreur d'envoi des paramètres DH: {e}")
        print("> ", end="", flush=True)

# Envoyer la clé publique Diffie-Hellman
async def send_dh_public_key(uri, pub_key):
    global port
    try:
        async with websockets.connect(uri) as ws:
            timestamp = datetime.now().strftime("%H:%M:%S")
            await ws.send(json.dumps({
                "type": "dh_public_key",
                "sender": username,
                "public_key": pub_key,
                "timestamp": timestamp,
                "sender_port": port
            }))
            print(f"\r[{timestamp}] Clé publique envoyée")
            print("> ", end="", flush=True)
    except Exception as e:
        print(f"\nErreur d'envoi de la clé publique: {e}")
        print("> ", end="", flush=True)

# Gestion des connexions entrantes
async def handle_connection(websocket): 
    global port, active_connections, dh_params, private_key, public_key, shared_key, encryption_ready
    try:
        # Extraire l'adresse IP du client qui se connecte
        remote_address = websocket.remote_address[0] if hasattr(websocket, 'remote_address') else None
        sender_port = None

        async for message in websocket:
            data = json.loads(message) # Charge le message reçu en tant que JSON
            timestamp = datetime.now().strftime("%H:%M:%S") # Créé un horodatage de l'heure de réception et le formatte en HH:MM:SS
            
            # Vérifier le type de message
            message_type = data.get('type', 'text')
            
            # Si c'est un message spécial pour l'échange de clés
            if message_type == 'dh_params':
                # Paramètres Diffie-Hellman reçus
                p, g = data['p'], data['g']
                print(f"\r[{timestamp}] Paramètres Diffie-Hellman reçus")
                
                # Stocker les paramètres
                dh_params = (p, g)
                
                # Générer la paire de clés
                private_key = generate_private_key(p)
                public_key = generate_public_key(p, g, private_key)
                
                # Envoyer notre clé publique en réponse
                asyncio.create_task(send_dh_public_key(
                    f"ws://{remote_address}:{data['sender_port']}",
                    public_key
                ))
                print("> ", end="", flush=True)
            elif message_type == 'dh_public_key':
                # Si c'est un message initial avec une clé publique vide (valeur 0)
                # et que nous sommes en mode actif, générons les paramètres
                if data['public_key'] == 0 and not in_waiting_mode:
                    print(f"\r[{timestamp}] Demande d'initialisation du chiffrement reçue")
                    
                    # Nous générons les paramètres
                    dh_params = generate_parameters()
                    private_key = generate_private_key(dh_params[0])
                    public_key = generate_public_key(dh_params[0], dh_params[1], private_key)
                    
                    # Envoyons nos paramètres
                    asyncio.create_task(send_dh_params(
                        f"ws://{remote_address}:{data['sender_port']}",
                        dh_params[0], dh_params[1]
                    ))
                    print("> ", end="", flush=True)
                    continue
                
                # Si nous n'avons pas encore de paramètres et que nous ne sommes pas
                # en mode attente, c'est anormal car on devrait avoir reçu les paramètres
                if dh_params is None:
                    print(f"\r[{timestamp}] Erreur: Clé publique reçue mais paramètres manquants")
                    print("> ", end="", flush=True)
                    continue
                
                # Clé publique du correspondant reçue
                other_public = data['public_key']
                print(f"\r[{timestamp}] Clé publique reçue")
                
                # Calculer la clé partagée
                p = dh_params[0]
                shared_key = compute_shared_key(p, other_public, private_key)
                encryption_ready = True
                
                print(f"\r[{timestamp}] Chiffrement établi avec succès!")
                print("> ", end="", flush=True)
                
            else:
                # C'est un message texte normal
                formatted_message = f"\r[{timestamp}] {data['sender']}: {data['message']}" 
                print(formatted_message)
                print("> ", end="", flush=True)
            
            # Traiter les informations de l'expéditeur si disponibles
            if remote_address and 'sender_port' in data:
                sender_port = int(data['sender_port'])
                connection_key = f"{remote_address}:{sender_port}"
                
                # Vérifier si cette connexion existe déjà dans notre registre
                is_new_connection = connection_key not in active_connections
                
                # Si c'est une nouvelle connexion, l'enregistrer
                if is_new_connection:
                    # Enregistrer cette connexion pour un usage futur
                    active_connections[connection_key] = {
                        "ip": remote_address,
                        "port": sender_port
                    }
                    
                    # Créer une tâche pour gérer les entrées utilisateur vers ce client
                    # seulement si nous sommes en mode attente
                    if in_waiting_mode:
                        asyncio.create_task(handle_user_input(remote_address, sender_port))
                        print(f"\rConnexion établie avec {remote_address}:{sender_port}")
                        
                        # En mode attente, initialiser l'échange de clés
                        if not encryption_ready:
                            # Générer les paramètres et les envoyer
                            dh_params = generate_parameters()
                            private_key = generate_private_key(dh_params[0])
                            public_key = generate_public_key(dh_params[0], dh_params[1], private_key)
                            
                            asyncio.create_task(send_dh_params(
                                f"ws://{remote_address}:{sender_port}",
                                dh_params[0], dh_params[1]
                            ))
                        
                        print("> ", end="", flush=True)
            
            # Envoyer une réponse de confirmation seulement pour les messages texte
            if message_type == 'text' or message_type == 'ack':
                await websocket.send(json.dumps({
                    "sender": username,
                    "message": "_Message reçu_",
                    "timestamp": timestamp,
                    "type": "ack",
                    "sender_port": port
                }))
    except websockets.exceptions.ConnectionClosed:
        print("\nL'autre personne s'est déconnectée.")
        print("> ", end="", flush=True)
    except Exception as e:
        print(f"\nErreur de connexion: {e}")
        print("> ", end="", flush=True)

# Envoyer un message à l'autre client
async def send_message(uri, message_text):
    global port  # S'assurer que la variable port est accessible
    try:
        async with websockets.connect(uri) as ws:
            timestamp = datetime.now().strftime("%H:%M:%S")
            await ws.send(json.dumps({
                "sender": username,
                "message": message_text,
                "timestamp": timestamp,
                "sender_port": port,  # Envoyer notre port d'écoute configuré
                "type": "text"  # Spécifier explicitement que c'est un message texte
            }))
            
            # Attendre la confirmation
            response = await ws.recv()
            data = json.loads(response)
            if data.get("type") != "ack":  # Si ce n'est pas une confirmation
                print(f"\r[{data['timestamp']}] {data['sender']}: {data['message']}")
                print("> ", end="", flush=True)
    except Exception as e:
        print(f"\nErreur d'envoi: {e}")
        print("> ", end="", flush=True)

# Initialisation de l'échange de clés en mode actif
async def initialize_encryption(target_ip, port):
    global dh_params, private_key, public_key, encryption_ready
    
    # Générer les paramètres Diffie-Hellman
    if dh_params is None:
        print("\rInitialisation du chiffrement...")
        # Utiliser un critère déterministe pour décider qui génère les paramètres
        # Comparer les adresses IP et ports pour décider
        local_ip = get_local_ip()
        connection_id = f"{local_ip}:{port}"
        remote_id = f"{target_ip}:{port}"
        
        should_generate = connection_id < remote_id
        
        if should_generate:
            # Nous générons les paramètres
            print("\rGénération des paramètres Diffie-Hellman...")
            dh_params = generate_parameters()
            private_key = generate_private_key(dh_params[0])
            public_key = generate_public_key(dh_params[0], dh_params[1], private_key)
            
            # Envoyer les paramètres à l'autre client
            await send_dh_params(f"ws://{target_ip}:{port}", dh_params[0], dh_params[1])
        else:
            # Nous envoyons juste notre clé publique pour signaler que nous sommes prêts
            # L'autre client générera les paramètres en recevant ceci
            print("\rAttente des paramètres Diffie-Hellman...")
            timestamp = datetime.now().strftime("%H:%M:%S")
            # On envoie une clé vide pour signaler notre présence
            await send_dh_public_key(f"ws://{target_ip}:{port}", 0)

# Fonction pour gérer les entrées utilisateur
async def handle_user_input(target_ip, port):
    global encryption_ready
    target_uri = f"ws://{target_ip}:{port}"
    
    # Initialiser le chiffrement si en mode actif
    if not in_waiting_mode and not encryption_ready:
        await initialize_encryption(target_ip, port)
    
    while True:
        message = await asyncio.get_event_loop().run_in_executor(None, lambda: input("> "))
        if message.lower() == "exit":
            print("Fermeture de l'application...")
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
        
        await handle_user_input(target_ip, target_port)
    else:
        in_waiting_mode = True  # Mode attente de connexion
        print("\nEn attente que quelqu'un se connecte à vous...")
        print("Tapez 'exit' pour quitter.")
        print("Quand quelqu'un se connecte, vous pourrez lui répondre automatiquement.")
        
        # En mode attente, permettre quand même à l'utilisateur de quitter
        while True:
            cmd = await asyncio.get_event_loop().run_in_executor(None, input)
            if cmd.lower() == "exit":
                print("Fermeture de l'application...")
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
    # Configurer la boucle d'événements
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Utiliser asyncio.run() qui gère proprement la boucle d'événements
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nFermeture de l'application...")
        sys.exit(0)