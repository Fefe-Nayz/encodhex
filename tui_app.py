#!/usr/bin/env python3
# filepath: c:\Users\ferre\Codespace\Projects\encodhex\tui_app.py

import asyncio
import websockets
import socket
import json
import sys
from datetime import datetime
import threading
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, Input, Label, Static
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from textual.binding import Binding
from aes.encryption import encrypt
from diffie_hellman.diffie_hellman import (
    generate_parameters,
    generate_private_key,
    generate_public_key,
    compute_shared_key,
)

# ──────────────────────────── état global ────────────────────────────
active_connections = {}
in_waiting_mode = False

dh_params = None
private_key = None
public_key = None
shared_key = None
encryption_ready = False
hello_done = False  # Flag pour suivre si le handshake hello a été effectué

username = ""
port = 8765
target_ip = None
target_port = None
server_task = None
local_ip = "127.0.0.1"


def get_local_ip():
    """Retourne l'IP locale (fallback : 127.0.0.1)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ────────────────────────────── widgets ──────────────────────────────
class ChatView(ScrollableContainer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def add_message(self, sender, message, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M:%S")

        if sender == username:
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold green")
            msg.append(message)
        else:
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold yellow")
            msg.append(message)

        self.messages.append(msg)
        self.update_messages()
        self.scroll_end()

    def update_messages(self):
        self.query("*").remove()
        for msg in self.messages:
            self.mount(Static(msg))

    def compose(self) -> ComposeResult:
        yield Static("La conversation apparaîtra ici")


# ─────────────────────────── application ────────────────────────────
class EncodHexApp(App):
    CSS = """
    #header {
        dock: top;
        height: 3;
        background: $boost;
        color: $text;
        text-align: center;
        padding: 0 1;
        content-align: center middle;
    }
    HeaderIcon { display: none; }
    HeaderTitle { width: 100%; }

    #main-container {
        width: 100%;
        height: 100%;
    }

    #status-bar {
        width: 100%;
        height: auto;
        background: $surface;
        color: $text-muted;
        text-align: left;
        padding: 0 2;
        border-bottom: solid $primary-darken-1;
        display: none;
    }

    Screen { background: $background; padding: 0; }

    #chat-pad {
        width: 100%;
        height: 1fr;
        padding: 1 2;
        background: $surface;
    }
    #chat-view {
        width: 100%;
        height: 100%;
        border: wide $primary-darken-1 round;
        border-title-color: $primary;
        border-title-align: center;
        background: $surface;
        padding: 1 2;
    }

    #welcome-message {
        width: 100%;
        height: 1fr;
        background: $surface;
        content-align: center middle;
        padding: 2;
    }

    #input-container {
        dock: bottom;
        height: 3;
        margin-bottom: 1;
        background: #272727;
        layout: horizontal;
        padding: 0 2;
    }

    Input {
        width: 1fr;
        background: $surface;
        color: $text;
        border: wide $primary round;
        padding: 0 1;
    }

    #input-label {
        width: auto;
        color: $text;
        background: #272727;
        padding: 1 1 0 0;
    }

    .conversation-welcome {
        width: 100%;
        height: 100%;
        text-align: center;
        background: $surface;
        padding: 2 4;
        border: wide green round;
        border-title-color: green;
        border-title-align: center;
    }

    .configuration-container {
        width: 100%;
        height: 100%;
        text-align: center;
        background: $surface;
        padding: 2 4;
        border: wide blue round;
        border-title-color: blue;
        border-title-align: center;
    }

    .content-text {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quitter"),
        Binding("ctrl+q", "quit", "Quitter"),
    ]

    app_state = reactive("welcome")
    status_text = reactive("")
    input_label = reactive("> ")

    def __init__(self):
        super().__init__()
        self.chat_view = ChatView(id="chat-view")
        self.welcome_container = Container(id="welcome-message")
        self.server_started = False
        self.websocket_server = None

    # ────────────────────────── lifecycle ──────────────────────────
    async def on_mount(self) -> None:
        await self.show_welcome()
        self.query_one("#user-input").focus()
        self.query_one("#header").title = (
            "Chat Peer-to-Peer chiffré avec Diffie-Hellman/AES-256"
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, id="header")

        with Container(id="main-container"):
            yield Static("", id="status-bar")
            yield self.welcome_container

            # chat wrapper with padding
            with Container(id="chat-pad"):
                yield self.chat_view

        with Container(id="input-container"):
            yield Label(self.input_label, id="input-label")
            yield Input(placeholder="Appuyez sur Entrée pour commencer...", id="user-input")

        yield Footer()

    # ─────────────────────────── vues ────────────────────────────
    async def show_welcome(self):
        self.welcome_container.styles.display = "block"
        self.chat_view.styles.display = "none"
        self.query_one("#chat-pad").styles.display = "none"

        self.title = "Chat Peer-to-Peer chiffré avec Diffie-Hellman/AES-256"
        self.welcome_container.query("*").remove()

        welcome_text = (
            "Bienvenue dans EncodHex - Chat P2P Chiffré\n\n"
            "Version 1.0\n"
            "Développé par Nino Belaoud & Ferréol DUBOIS COLI\n\n"
            "Appuyez sur Entrée pour commencer"
        )

        welcome_box = Container(classes="conversation-welcome")
        welcome_box.border_title = "EncodHex"
        self.welcome_container.mount(welcome_box)
        welcome_box.mount(Static(welcome_text, classes="content-text"))

        self.welcome_container.styles.content_align_horizontal = "center"
        self.welcome_container.styles.content_align_vertical = "middle"

        self.app_state = "welcome"
        self.input_label = "> "

    def show_conversation(self):
        self.welcome_container.styles.display = "none"
        self.query_one("#chat-pad").styles.display = "block"
        self.chat_view.styles.display = "block"

        status_bar = self.query_one("#status-bar")
        status_bar.styles.display = "block"
        self.query_one("#user-input").placeholder = "Tapez votre message..."

        self.chat_view.border_title = "Chat"

        global username, port, local_ip, in_waiting_mode
        status = f"{username} | {local_ip}:{port} | Mode: {'Attente' if in_waiting_mode else 'Actif'}"
        if encryption_ready:
            status += " | 🔒 Chiffré"
        status_bar.update(status)

        self.app_state = "conversation"
        self.input_label = "> "

    def update_status(self, status):
        self.query_one("#status-bar").update(status)

    # ───────────────────────── gestion input ──────────────────────
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        box = event.input
        box.value = ""

        match self.app_state:
            case "welcome":
                await self.start_setup(box)
            case "setup_username":
                await self.setup_username(value, box)
            case "setup_port":
                await self.setup_port(value, box)
            case "setup_mode":
                await self.setup_mode(value, box)
            case "setup_target_ip":
                await self.setup_target_ip(value, box)
            case "setup_target_port":
                await self.setup_target_port(value, box)
            case "conversation":
                await self.handle_message(value)

    async def start_setup(self, input_box):
        # Commencer la configuration
        self.app_state = "setup_username"
        self.input_label = "Entrez votre nom d'utilisateur: "
        input_box.placeholder = "Votre nom (par défaut: User_xxx)"
        
        # Supprimer le message de bienvenue
        self.welcome_container.query("*").remove()
        
        # Create a container with border styling
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        
        # First mount the container
        self.welcome_container.mount(config_container)
        
        # Then add the configuration message
        config_message = Static("Configuration du chat...", id="setup-start-content", classes="content-text")
        config_container.mount(config_message)

    async def setup_username(self, value, input_box):
        global username
        
        # Définir le nom d'utilisateur
        if value:
            username = value
        else:
            username = f"User_{socket.gethostname()}"
        
        # Passer à la configuration du port
        self.app_state = "setup_port"
        self.input_label = "Entrez le port à utiliser: "
        input_box.placeholder = "Port (par défaut: 8765)"
        
        # Update container with configuration information
        config_container = self.welcome_container.query_one(".configuration-container")
        config_container.query("*").remove()
        config_container.mount(Static(
            f"Nom d'utilisateur: {username}\nConfiguration du port...", 
            id="setup-username-content", 
            classes="content-text"
        ))

    async def setup_port(self, value, input_box):
        global port, local_ip
        
        # Définir le port
        if value.strip():
            try:
                port = int(value)
            except ValueError:
                self.notify("Port invalide, utilisation du port par défaut: 8765", severity="error")
                port = 8765
        else:
            port = 8765
        
        # Obtenir l'adresse IP locale
        local_ip = get_local_ip()
        
        # Démarrer le serveur WebSocket
        if not self.server_started:
            await self.start_websocket_server()
            self.server_started = True
        
        # Passer à la sélection du mode
        self.app_state = "setup_mode"
        self.input_label = "Vous connecter (o) ou attendre (n)? "
        input_box.placeholder = "o/n"
        
        # Update container with configuration information
        config_container = self.welcome_container.query_one(".configuration-container")
        config_container.query("*").remove()
        config_container.mount(Static(
            f"Nom d'utilisateur: {username}\n"
            f"Port: {port}\n"
            f"Adresse IP: {local_ip}\n\n"
            f"Voulez-vous vous connecter à quelqu'un (o) ou attendre une connexion (n)?", 
            id="setup-port-content",
            classes="content-text"
        ))

    async def setup_mode(self, value, input_box):
        global in_waiting_mode
        
        # Définir le mode
        choice = value.lower()
        if choice in ('o', 'oui'):
            in_waiting_mode = False
            
            # Passer à la saisie de l'IP cible
            self.app_state = "setup_target_ip"
            self.input_label = "Entrez l'adresse IP de l'autre personne: "
            input_box.placeholder = "Adresse IP"
            
            # Update container with configuration information
            config_container = self.welcome_container.query_one(".configuration-container")
            config_container.query("*").remove()
            config_container.mount(Static(
                f"Mode: Connexion active\n"
                f"Entrez l'adresse IP de l'autre personne:", 
                id="setup-mode-active-content",
                classes="content-text"
            ))
            
        else:
            in_waiting_mode = True
            
            # Passer directement au mode conversation
            self.app_state = "conversation"
            self.show_conversation()
            
            # Ajouter un message d'information
            self.chat_view.add_message("Système", "En attente d'une connexion entrante...")
            self.chat_view.add_message("Système", f"Votre adresse IP: {local_ip}:{port}")
            self.chat_view.add_message("Système", "Partagez ces informations avec l'autre personne.")

    async def setup_target_ip(self, value, input_box):
        global target_ip
        
        # Définir l'IP cible
        if value.strip():
            target_ip = value
            
            # Passer à la saisie du port cible
            self.app_state = "setup_target_port"
            self.input_label = "Entrez le port de l'autre personne: "
            input_box.placeholder = f"Port (défaut: {port})"
            
            # Update container with configuration information
            config_container = self.welcome_container.query_one(".configuration-container")
            config_container.query("*").remove()
            config_container.mount(Static(
                f"Mode: Connexion active\n"
                f"Adresse IP cible: {target_ip}\n"
                f"Entrez le port de l'autre personne:", 
                id="setup-target-ip-content",
                classes="content-text"
            ))
        else:
            self.notify("L'adresse IP est requise", severity="error")

    async def setup_target_port(self, value, input_box):
        global target_port, port
        
        # Définir le port cible
        if value.strip():
            try:
                target_port = int(value)
            except ValueError:
                self.notify("Port invalide, utilisation du port par défaut", severity="error")
                target_port = port
        else:
            target_port = port
        
        # Passer au mode conversation
        self.app_state = "conversation"
        self.show_conversation()
        
        # Ajouter un message d'information
        self.chat_view.add_message("Système", f"Connexion à {target_ip}:{target_port}...")
        
        # Démarrer le handshake
        if not hello_done:
            asyncio.create_task(self.begin_handshake(target_ip, target_port))

    async def handle_message(self, message):
        global target_ip, target_port
        
        if not message:
            return
        
        if message.lower() == "exit":
            await self.action_quit()
            return
        
        # Ajouter le message à la vue
        self.chat_view.add_message(username, message)
        
        # Envoyer le message
        if in_waiting_mode and active_connections:
            # En mode attente, utiliser la première connexion active
            first_connection = list(active_connections.values())[0]
            asyncio.create_task(self.send_message_to(
                f"ws://{first_connection['ip']}:{first_connection['port']}", 
                message
            ))
        elif not in_waiting_mode and target_ip and target_port:
            # En mode actif, utiliser la cible configurée
            asyncio.create_task(self.send_message_to(
                f"ws://{target_ip}:{target_port}", 
                message
            ))

    # ───────────────────── Nouveaux helpers WebSocket ────────────────────
    async def send_json(self, uri, payload):
        """Envoie un message JSON à l'URI spécifiée."""
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps(payload))
                return ws
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur d'envoi: {e}")
            return None

    async def send_hello(self, uri, i_generate):
        """Envoie un message hello pour initier la connexion."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        await self.send_json(uri, {
            "type": "hello",
            "sender": username,
            "i_generate": i_generate,
            "timestamp": timestamp,
            "sender_port": port
        })
        self.chat_view.add_message("Système", f"Initialisation de la connexion...")

    async def send_dh_params(self, uri, p, g):
        """Envoie les paramètres Diffie-Hellman."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        await self.send_json(uri, {
            "type": "dh_params",
            "sender": username,
            "p": p,
            "g": g,
            "timestamp": timestamp,
            "sender_port": port
        })
        self.chat_view.add_message("Système", "Paramètres Diffie-Hellman envoyés")

    async def send_dh_public_key(self, uri, pub_key):
        """Envoie la clé publique Diffie-Hellman."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        await self.send_json(uri, {
            "type": "dh_public_key",
            "sender": username,
            "public_key": pub_key,
            "timestamp": timestamp,
            "sender_port": port
        })
        self.chat_view.add_message("Système", "Clé publique envoyée")

    async def send_message_to(self, uri, message_text):
        """Envoie un message texte."""
        try:
            async with websockets.connect(uri) as ws:
                timestamp = datetime.now().strftime("%H:%M:%S")
                await ws.send(json.dumps({
                    "type": "text",
                    "sender": username,
                    "message": message_text,
                    "timestamp": timestamp,
                    "sender_port": port
                }))
                
                # Attendre la confirmation
                response = await ws.recv()
                data = json.loads(response)
                if data.get("type") != "ack":
                    self.chat_view.add_message(data['sender'], data['message'], data.get('timestamp'))
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur d'envoi: {e}")

    async def begin_handshake(self, target_ip, target_port):
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
            self.chat_view.add_message("Système", "Génération des paramètres de chiffrement...")
        
        # Envoyer le hello avec mon rôle défini
        await self.send_hello(f"ws://{target_ip}:{target_port}", i_generate)
        
        # Si je suis générateur, envoyer (p,g) + ma clé publique
        if i_generate:
            await self.send_dh_params(f"ws://{target_ip}:{target_port}", p, g)
            await self.send_dh_public_key(f"ws://{target_ip}:{target_port}", public_key)

    async def start_websocket_server(self):
        # Démarrer le serveur WebSocket
        server = await websockets.serve(self.handle_connection, "0.0.0.0", port)
        self.websocket_server = server
        self.notify(f"Serveur démarré sur {local_ip}:{port}")

    async def handle_connection(self, websocket):
        global port, active_connections, dh_params, private_key, public_key, shared_key
        global encryption_ready, username, hello_done
        
        try:
            # Extraire l'adresse IP et le port du client qui se connecte
            remote_ip = websocket.remote_address[0] if hasattr(websocket, 'remote_address') else None
            remote_port = None
            
            async for message in websocket:
                data = json.loads(message)
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Vérifier le type de message
                message_type = data.get('type', 'text')
                
                # ───────── hello ─────────
                if message_type == 'hello':
                    if hello_done:
                        continue  # déjà négocié
                    
                    hello_done = True
                    self.chat_view.add_message("Système", "Demande de connexion reçue")
                    
                    if (not data["i_generate"]) and dh_params is None:  # c'est à moi de générer
                        p, g = generate_parameters()
                        dh_params = (p, g)
                        private_key = generate_private_key(p)
                        public_key = generate_public_key(p, g, private_key)
                        
                        self.chat_view.add_message("Système", "Génération des paramètres de chiffrement...")
                        await self.send_dh_params(f"ws://{remote_ip}:{data['sender_port']}", p, g)
                        await self.send_dh_public_key(f"ws://{remote_ip}:{data['sender_port']}", public_key)
                
                # ──────── (p,g) ──────────
                elif message_type == 'dh_params':
                    # Paramètres Diffie-Hellman reçus
                    p, g = data['p'], data['g']
                    self.chat_view.add_message("Système", "Paramètres Diffie-Hellman reçus")
                    
                    # Stocker les paramètres
                    dh_params = (p, g)
                    
                    # Générer la paire de clés
                    private_key = generate_private_key(p)
                    public_key = generate_public_key(p, g, private_key)
                    
                    # Envoyer notre clé publique en réponse
                    await self.send_dh_public_key(f"ws://{remote_ip}:{data['sender_port']}", public_key)
                
                # ───── clé publique ──────
                elif message_type == 'dh_public_key':
                    if dh_params is None:
                        self.chat_view.add_message("Système", "Erreur: Clé publique reçue mais paramètres manquants")
                        continue
                    
                    # Clé publique du correspondant reçue
                    other_public = data['public_key']
                    self.chat_view.add_message("Système", "Clé publique reçue")
                    
                    # Calculer la clé partagée
                    p = dh_params[0]
                    shared_key = compute_shared_key(p, other_public, private_key)
                    encryption_ready = True
                    
                    self.chat_view.add_message("Système", "🔒 Chiffrement établi avec succès!")
                    
                    # Mettre à jour le statut
                    status = f"{username} | {local_ip}:{port} | Mode: {'Attente' if in_waiting_mode else 'Actif'} | 🔒 Chiffré"
                    self.update_status(status)
                
                # ───────── texte ─────────
                else:
                    # C'est un message texte normal
                    self.chat_view.add_message(data['sender'], data['message'], data.get('timestamp'))
                
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
                        
                        if in_waiting_mode and message_type != 'hello' and message_type != 'dh_params' and message_type != 'dh_public_key':
                            self.chat_view.add_message("Système", f"Connexion établie avec {remote_ip}:{remote_port}")
                
                # Envoyer une réponse de confirmation seulement pour les messages texte
                if message_type == 'text' or message_type == 'ack':
                    await websocket.send(json.dumps({
                        "type": "ack",
                        "sender": username,
                        "timestamp": timestamp,
                        "sender_port": port
                    }))
        
        except websockets.exceptions.ConnectionClosed:
            self.chat_view.add_message("Système", "L'autre personne s'est déconnectée.")
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur de connexion: {e}")

# Point d'entrée principal
if __name__ == "__main__":
    # Lancer l'application Textual
    app = EncodHexApp()
    app.run()
