import asyncio
import websockets
import socket
import json
import sys
from datetime import datetime

# Variables globales pour gérer l'état de la connexion
active_connections = {}  # Dictionnaire pour stocker les connexions actives
in_waiting_mode = False  # Si nous sommes en mode attente ou non

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

# Gestion des connexions entrantes
async def handle_connection(websocket):  # Suppression du paramètre path qui n'est plus utilisé
    global port, active_connections  # S'assurer que les variables globales sont accessibles
    try:
        # Extraire l'adresse IP du client qui se connecte
        remote_address = websocket.remote_address[0] if hasattr(websocket, 'remote_address') else None
        sender_port = None

        async for message in websocket:
            data = json.loads(message)
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"\r[{timestamp}] {data['sender']}: {data['message']}"
            print(formatted_message)
            print("> ", end="", flush=True)            # Traiter les informations de l'expéditeur si disponibles
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
                        print("> ", end="", flush=True)
            
            # Envoyer une réponse de confirmation
            await websocket.send(json.dumps({
                "sender": username,
                "message": "_Message reçu_",
                "timestamp": timestamp,
                "type": "ack",
                "sender_port": port  # Inclure notre port d'écoute configuré
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
                "sender_port": port  # Envoyer notre port d'écoute configuré
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

# Fonction pour gérer les entrées utilisateur
async def handle_user_input(target_ip, port):
    target_uri = f"ws://{target_ip}:{port}"
    while True:
        message = await asyncio.get_event_loop().run_in_executor(None, lambda: input("> "))
        if message.lower() == "exit":
            print("Fermeture de l'application...")
            sys.exit(0)
        
        asyncio.create_task(send_message(target_uri, message))

# Fonction principale
async def main():
    global username, port, in_waiting_mode  # Définir les variables globales
    
    print("Chat P2P avec WebSockets")
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
    choice = input("\nVoulez-vous vous connecter à quelqu'un? (o/n): ").lower()
    
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