#!/usr/bin/env python3
# filepath: c:\Users\ferre\Codespace\Projects\encodhex\tui_app.py

import asyncio
import websockets
import socket
import json
import sys
import re
from datetime import datetime
import threading
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, Input, Label, Static
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from textual.binding import Binding
from textual.message import Message
from aes.encryption import encrypt, decrypt
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


def is_valid_ip(ip):
    """Valide une adresse IP."""
    pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    if not re.match(pattern, ip):
        return False
    
    # Vérifier que chaque octet est entre 0 et 255
    octets = ip.split('.')
    for octet in octets:
        if int(octet) < 0 or int(octet) > 255:
            return False
    
    return True


def is_valid_port(port_str):
    """Valide un numéro de port."""
    try:
        port_num = int(port_str)
        return 1 <= port_num <= 65535
    except ValueError:
        return False


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
        elif sender == "Système":
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold blue")  # Style distinct pour les messages système
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
        background: $surface;
        layout: horizontal;
        padding: 0 2;
    }
    
    .focused-bg {
        background-tint: $foreground 5%;
    }

    Input {
        width: 1fr;
        background: $surface;
        color: $text;
        border: wide $primary round;
        padding: 0 1;
    }
    
    /* The Input:focus styling is handled by Textual's default CSS */

    #input-label {
        width: auto;
        color: $text;
        background: $surface;
        padding: 1 1 0 0;
    }
    
    /* Remove the previous focus selectors */

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

    .error-message {
        color: $error;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quitter"),
        Binding("ctrl+q", "quit", "Quitter"),
        Binding("ctrl+r", "reset_config", "Config"),
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
        input_field = self.query_one("#user-input")
        input_field.focus()
        
        # Set timer to periodically check focus and update styling
        self.set_interval(0.01, self.update_input_container_styling)
        
        self.query_one("#header").title = (
            "Chat Peer-to-Peer chiffré avec Diffie-Hellman/AES-256"
        )
    
    def update_input_container_styling(self) -> None:
        """Update input container and label styling based on input focus."""
        input_field = self.query_one("#user-input")
        container = self.query_one("#input-container")
        label = self.query_one("#input-label")
        
        if input_field.has_focus:
            # Apply focused class when input is focused
            container.add_class("focused-bg")
            label.add_class("focused-bg")
        else:
            # Remove focused class when input is not focused
            container.remove_class("focused-bg")
            label.remove_class("focused-bg")

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

        global username, port, local_ip, in_waiting_mode, target_ip, target_port
        status = f"{username} | {local_ip}:{port} | Mode: {'Attente' if in_waiting_mode else 'Actif'}"
        if encryption_ready:
            status += " | 🔒 Chiffré"
        status_bar.update(status)

        # Mettre à jour le titre de la fenêtre avec les informations de connexion
        if in_waiting_mode:
            self.title = f"EncodHex - {username} - {local_ip}:{port} - En attente"
        else:
            if target_ip and target_port:
                self.title = f"EncodHex - {username} - {local_ip}:{port} - Connecté à {target_ip}:{target_port}"
            else:
                self.title = f"EncodHex - {username} - {local_ip}:{port} - Mode Actif"

        self.app_state = "conversation"
        self.input_label = "> "

    def update_status(self, status):
        self.query_one("#status-bar").update(status)
        
    def show_error_in_config(self, error_message):
        """Affiche un message d'erreur dans le conteneur de configuration."""
        config_container = self.welcome_container.query_one(".configuration-container")
        
        # Chercher si un message d'erreur existe déjà
        error_widget = config_container.query(".error-message")
        if error_widget:
            error_widget.remove()
            
        # Ajouter le nouveau message d'erreur
        config_container.mount(Static(error_message, classes="error-message"))
        
        # Également afficher une notification
        self.notify(error_message, severity="error", timeout=5)

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
        
        # Générer un timestamp unique pour les IDs
        unique_id_suffix = str(int(datetime.now().timestamp()))
        
        # Create a container with border styling
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        
        # First mount the container
        self.welcome_container.mount(config_container)
        
        # Then add the configuration message
        config_message = Static(
            "Configuration du chat...", 
            id=f"setup-start-content-{unique_id_suffix}", 
            classes="content-text"
        )
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
        
        # Recréer le conteneur de configuration
        old_container = self.welcome_container.query_one(".configuration-container")
        old_container.remove()
        
        # Créer un nouveau conteneur
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        self.welcome_container.mount(config_container)
        
        # Générer un timestamp unique pour les IDs
        unique_id_suffix = str(int(datetime.now().timestamp()))
        
        # Update container with configuration information
        config_container.mount(Static(
            f"Nom d'utilisateur: {username}\n"
            f"Configuration du port...", 
            id=f"setup-username-content-{unique_id_suffix}", 
            classes="content-text"
        ))

    async def setup_port(self, value, input_box):
        global port, local_ip
        
        # Définir le port
        if value.strip():
            if not is_valid_port(value):
                self.show_error_in_config("Port invalide! Veuillez entrer un nombre entre 1 et 65535.")
                return
                
            port = int(value)
        else:
            port = 8765
        
        # Obtenir l'adresse IP locale
        local_ip = get_local_ip()
        
        # Démarrer le serveur WebSocket avec tentative sur plusieurs ports
        if not self.server_started:
            port_success = await self.try_start_server(port)
            if not port_success:
                self.show_error_in_config(f"Impossible de démarrer le serveur sur aucun port disponible.")
                return
        
        # Passer à la sélection du mode
        self.app_state = "setup_mode"
        self.input_label = "Vous connecter (o) ou attendre (n)? "
        input_box.placeholder = "o/n"
        
        # Recréer le conteneur de configuration
        old_container = self.welcome_container.query_one(".configuration-container")
        old_container.remove()
        
        # Créer un nouveau conteneur
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        self.welcome_container.mount(config_container)
        
        # Générer un timestamp unique pour les IDs
        unique_id_suffix = str(int(datetime.now().timestamp()))
        
        # Update container with configuration information
        config_container.mount(Static(
            f"Nom d'utilisateur: {username}\n"
            f"Port: {port}\n"
            f"Adresse IP: {local_ip}\n\n"
            f"Voulez-vous vous connecter à quelqu'un (o) ou attendre une connexion (n)?", 
            id=f"setup-port-content-{unique_id_suffix}",
            classes="content-text"
        ))

    async def try_start_server(self, start_port):
        """Essaie de démarrer le serveur sur un port, ou tente les ports suivants."""
        global port
        max_attempts = 10
        current_port = start_port
        
        for _ in range(max_attempts):
            try:
                await self.start_websocket_server(current_port)
                self.server_started = True
                if current_port != start_port:
                    self.chat_view.add_message("Système", f"Port {start_port} déjà utilisé, serveur démarré sur le port {current_port} à la place")
                port = current_port  # Mettre à jour le port si un différent a été utilisé
                self.notify(f"Serveur démarré sur le port {port}", severity="information")
                return True
            except OSError as e:
                if e.errno == 10048:  # Port déjà utilisé
                    self.notify(f"Port {current_port} déjà utilisé, essai du port {current_port+1}", severity="warning")
                    current_port += 1
                else:
                    error_msg = f"Erreur lors du démarrage du serveur: {e}"
                    self.show_error_in_config(error_msg)
                    self.chat_view.add_message("Système", error_msg)
                    return False
            except Exception as e:
                error_msg = f"Erreur inattendue: {e}"
                self.show_error_in_config(error_msg)
                self.chat_view.add_message("Système", error_msg)
                return False
        
        return False  # Échec après plusieurs tentatives

    async def start_websocket_server(self, server_port=None):
        """Démarrer le serveur WebSocket sur le port spécifié."""
        if server_port is None:
            server_port = port
            
        # Démarrer le serveur WebSocket
        try:
            server = await websockets.serve(self.handle_connection, "0.0.0.0", server_port)
            self.websocket_server = server
            self.notify(f"Serveur démarré sur {local_ip}:{server_port}")
            return server
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur lors du démarrage du serveur: {e}")
            raise  # Re-raise l'exception pour que try_start_server puisse la gérer

    async def handle_connection(self, websocket):
        global port, active_connections, dh_params, private_key, public_key, shared_key
        global encryption_ready, username, hello_done
        
        try:
            # Extraire l'adresse IP et le port du client qui se connecte
            remote_ip = websocket.remote_address[0] if hasattr(websocket, 'remote_address') else None
            remote_port = None
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    self.chat_view.add_message("Système", "Message reçu invalide (format JSON incorrect)")
                    continue
                    
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Vérifier le type de message
                message_type = data.get('type', 'text')
                
                # ───────── hello ─────────
                if message_type == 'hello':
                    if hello_done:
                        continue  # déjà négocié
                    
                    hello_done = True
                    self.chat_view.add_message("Système", "Demande de connexion reçue")
                    
                    if (not data.get("i_generate", False)) and dh_params is None:  # c'est à moi de générer
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
                    p, g = data.get('p'), data.get('g')
                    
                    if p is None or g is None:
                        self.chat_view.add_message("Système", "Erreur: Paramètres Diffie-Hellman incomplets")
                        continue
                        
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
                    other_public = data.get('public_key')
                    
                    if other_public is None:
                        self.chat_view.add_message("Système", "Erreur: Clé publique manquante")
                        continue
                        
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
                elif message_type == 'text':
                    # C'est un message texte normal
                    if 'message' not in data:
                        self.chat_view.add_message("Système", "Erreur: Message reçu sans contenu")
                        continue
                        
                    if not encryption_ready or shared_key is None:
                        self.chat_view.add_message("Système", "Erreur: Message reçu mais chiffrement non établi")
                        continue
                        
                    try:
                        decrypted_message = decrypt(data['message'], shared_key)
                        self.chat_view.add_message(data.get('sender', 'Inconnu'), decrypted_message, data.get('timestamp'))
                    except Exception as e:
                        self.chat_view.add_message("Système", f"Erreur de déchiffrement: {e}")
                
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
        except json.JSONDecodeError:
            self.chat_view.add_message("Système", "Erreur: Message reçu invalide")
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur de connexion: {e}")

    async def send_json(self, uri, payload):
        """Envoie un message JSON à l'URI spécifiée."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.chat_view.add_message("Système", f"Tentative de connexion à {uri} ({attempt+1}/{max_retries})")
                async with websockets.connect(uri, ping_timeout=5, close_timeout=5) as ws:
                    json_payload = json.dumps(payload)
                    await ws.send(json_payload)
                    self.chat_view.add_message("Système", f"Message envoyé avec succès à {uri}")
                    return ws
            except ConnectionRefusedError:
                self.chat_view.add_message("Système", f"Connexion refusée à {uri}. Vérifiez que le serveur est en marche.")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(1)
            except websockets.exceptions.InvalidURI:
                self.chat_view.add_message("Système", f"URI invalide: {uri}")
                return None
            except (OSError, websockets.exceptions.WebSocketException) as e:
                self.chat_view.add_message("Système", f"Erreur d'envoi: {e}")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(1)
        return None

    async def send_hello(self, uri, i_generate):
        """Envoie un message hello pour initier la connexion."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        result = await self.send_json(uri, {
            "type": "hello",
            "sender": username,
            "i_generate": i_generate,
            "timestamp": timestamp,
            "sender_port": port
        })
        
        if result:
            self.chat_view.add_message("Système", f"Initialisation de la connexion...")
            return True
        else:
            error_msg = f"Échec de connexion à {uri}. Veuillez vérifier l'adresse et le port."
            self.chat_view.add_message("Système", error_msg)
            self.notify(error_msg, severity="error", timeout=5)
            return False

    async def send_dh_params(self, uri, p, g):
        """Envoie les paramètres Diffie-Hellman."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        result = await self.send_json(uri, {
            "type": "dh_params",
            "sender": username,
            "p": p,
            "g": g,
            "timestamp": timestamp,
            "sender_port": port
        })
        
        if result:
            self.chat_view.add_message("Système", "Paramètres Diffie-Hellman envoyés")
            return True
        return False

    async def send_dh_public_key(self, uri, pub_key):
        """Envoie la clé publique Diffie-Hellman."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        result = await self.send_json(uri, {
            "type": "dh_public_key",
            "sender": username,
            "public_key": pub_key,
            "timestamp": timestamp,
            "sender_port": port
        })
        
        if result:
            self.chat_view.add_message("Système", "Clé publique envoyée")
            return True
        return False

    async def send_message_to(self, uri, message_text):
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
                response = await ws.recv()
                data = json.loads(response)
                if data.get("type") != "ack":
                    self.chat_view.add_message(data['sender'], decrypt(data['message'], shared_key), data.get('timestamp'))
        except ConnectionRefusedError:
            self.chat_view.add_message("Système", f"Impossible de se connecter à {uri}. La connexion est peut-être perdue.")
            await self.reset_to_connection_setup("Connexion perdue. Veuillez réessayer.")
        except (OSError, websockets.exceptions.WebSocketException) as e:
            self.chat_view.add_message("Système", f"Erreur d'envoi: {e}")
            await self.reset_to_connection_setup("Erreur de connexion. Veuillez réessayer.")

    async def reset_to_connection_setup(self, message=None):
        """Réinitialise l'application pour permettre une nouvelle connexion"""
        global hello_done, target_ip, target_port, encryption_ready, shared_key, in_waiting_mode
        
        # Réinitialiser les variables de connexion
        hello_done = False
        encryption_ready = False
        shared_key = None
        
        # Pour tous les états, configurer l'interface de base
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        self.welcome_container.query("*").remove()
        self.welcome_container.mount(config_container)
        
        # Si nous étions en conversation, afficher l'écran de configuration
        if self.app_state == "conversation":
            self.welcome_container.styles.display = "block"
            self.chat_view.styles.display = "none"
            self.query_one("#chat-pad").styles.display = "none"
            self.query_one("#status-bar").styles.display = "none"
            
            # En mode attente, retourner à la configuration du mode
            if in_waiting_mode:
                self.app_state = "setup_mode"
                self.input_label = "Vous connecter (o) ou attendre (n)? "
                self.query_one("#user-input").placeholder = "o/n"
                
                config_message = Static(
                    f"Nom d'utilisateur: {username}\n"
                    f"Port: {port}\n"
                    f"Adresse IP: {local_ip}\n\n"
                    f"Voulez-vous vous connecter à quelqu'un (o) ou attendre une connexion (n)?", 
                    id="setup-mode-content",
                    classes="content-text"
                )
                config_container.mount(config_message)
            else:
                # En mode actif, retourner à la saisie de l'IP
                self.app_state = "setup_target_ip"
                self.input_label = "Entrez l'adresse IP de l'autre personne: "
                self.query_one("#user-input").placeholder = "Adresse IP"
                
                config_message = Static(
                    f"Mode: Connexion active\n"
                    f"Entrez l'adresse IP de l'autre personne:", 
                    id="setup-target-ip-content",
                    classes="content-text"
                )
                config_container.mount(config_message)
        # Si nous étions dans un autre état
        elif self.app_state != "welcome":
            # Revenir à la configuration du mode
            self.app_state = "setup_mode"
            self.input_label = "Vous connecter (o) ou attendre (n)? "
            self.query_one("#user-input").placeholder = "o/n"
            
            config_message = Static(
                f"Nom d'utilisateur: {username}\n"
                f"Port: {port}\n"
                f"Adresse IP: {local_ip}\n\n"
                f"Voulez-vous vous connecter à quelqu'un (o) ou attendre une connexion (n)?", 
                id="setup-mode-content",
                classes="content-text"
            )
            config_container.mount(config_message)
        
        # Afficher un message d'erreur/info si fourni
        if message:
            config_container.mount(Static(message, classes="error-message"))
            self.notify(message, severity="error", timeout=5)

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
            
            # Recréer le conteneur de configuration
            old_container = self.welcome_container.query_one(".configuration-container")
            old_container.remove()
            
            # Créer un nouveau conteneur
            config_container = Container(classes="configuration-container")
            config_container.border_title = "Configuration"
            self.welcome_container.mount(config_container)
            
            # Générer un timestamp unique pour les IDs
            unique_id_suffix = str(int(datetime.now().timestamp()))
            
            # Update container with configuration information
            config_container.mount(Static(
                f"Mode: Connexion active\n"
                f"Entrez l'adresse IP de l'autre personne:", 
                id=f"setup-mode-active-content-{unique_id_suffix}",
                classes="content-text"
            ))
            
        elif choice in ('n', 'non'):
            in_waiting_mode = True
            
            # Passer directement au mode conversation
            self.app_state = "conversation"
            self.show_conversation()
            
            # Ajouter un message d'information
            self.chat_view.add_message("Système", "En attente d'une connexion entrante...")
            self.chat_view.add_message("Système", f"Votre adresse IP: {local_ip}:{port}")
            self.chat_view.add_message("Système", "Partagez ces informations avec l'autre personne.")
        else:
            error_msg = "Veuillez entrer 'o' pour vous connecter ou 'n' pour attendre une connexion."
            self.show_error_in_config(error_msg)

    async def setup_target_ip(self, value, input_box):
        global target_ip
        
        # Définir l'IP cible
        if value.strip():
            if not is_valid_ip(value):
                self.show_error_in_config("Adresse IP invalide. Veuillez entrer une adresse IP valide (ex: 192.168.1.1).")
                return
                
            target_ip = value
            
            # Passer à la saisie du port cible
            self.app_state = "setup_target_port"
            self.input_label = "Entrez le port de l'autre personne: "
            input_box.placeholder = f"Port (défaut: {port})"
            
            # Recréer le conteneur de configuration au lieu de le vider
            old_container = self.welcome_container.query_one(".configuration-container")
            old_container.remove()
            
            # Créer un nouveau conteneur
            config_container = Container(classes="configuration-container")
            config_container.border_title = "Configuration"
            self.welcome_container.mount(config_container)
            
            # Générer un timestamp unique pour les IDs
            unique_id_suffix = str(int(datetime.now().timestamp()))
            
            # Update container with configuration information
            config_container.mount(Static(
                f"Mode: Connexion active\n"
                f"Adresse IP cible: {target_ip}\n"
                f"Entrez le port de l'autre personne:", 
                id=f"setup-target-port-content-{unique_id_suffix}",
                classes="content-text"
            ))
        else:
            self.show_error_in_config("L'adresse IP est requise.")

    async def setup_target_port(self, value, input_box):
        global target_port, port
        
        # Définir le port cible
        if value.strip():
            if not is_valid_port(value):
                self.show_error_in_config("Port invalide! Veuillez entrer un nombre entre 1 et 65535.")
                return
                
            target_port = int(value)
        else:
            target_port = port
        
        # Passer au mode conversation
        self.app_state = "conversation"
        self.show_conversation()
        
        # Ajouter un message d'information
        self.chat_view.add_message("Système", f"Connexion à {target_ip}:{target_port}...")
        
        # Démarrer le handshake dans une tâche séparée
        if not hello_done:
            # Utiliser create_task pour démarrer sans attendre
            connect_task = asyncio.create_task(self.begin_handshake(target_ip, target_port))
            
            # Créer un gestionnaire d'erreurs pour la tâche
            def handle_connect_error(task):
                try:
                    # Récupérer le résultat pour voir s'il y a une exception
                    task.result()
                except Exception as e:
                    self.chat_view.add_message("Système", f"Erreur de connexion: {e}")
                    asyncio.create_task(self.reset_to_connection_setup(f"Erreur lors de la connexion: {e}"))
            
            # Attacher le gestionnaire
            connect_task.add_done_callback(handle_connect_error)

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
        
        # Afficher des informations de diagnostic
        self.chat_view.add_message("Système", f"Tentative de connexion à {target_ip}:{target_port}")
        self.chat_view.add_message("Système", f"Notre adresse: {local_ip}:{port}")
        
        # Si je génère, le faire avant tout envoi réseau
        if i_generate:
            self.chat_view.add_message("Système", "Génération des paramètres de chiffrement...")
            p, g = generate_parameters()
            dh_params = (p, g)
            private_key = generate_private_key(p)
            public_key = generate_public_key(p, g, private_key)
        
        # Envoyer le hello avec mon rôle défini
        uri = f"ws://{target_ip}:{target_port}"
        self.chat_view.add_message("Système", f"Envoi du hello à {uri}")
        
        for attempt in range(3):  # Essayer 3 fois
            try:
                success = await self.send_hello(uri, i_generate)
                if success:
                    break
                await asyncio.sleep(1)  # Attendre un peu avant de réessayer
            except Exception as e:
                self.chat_view.add_message("Système", f"Tentative {attempt+1} échouée: {e}")
                if attempt == 2:  # Dernière tentative
                    hello_done = False
                    await self.reset_to_connection_setup("Échec de la connexion après plusieurs tentatives.")
                    return
                await asyncio.sleep(1)
        
        if not success:
            # Réinitialiser pour permettre de réessayer
            hello_done = False
            await self.reset_to_connection_setup("Échec de la connexion. Veuillez vérifier l'adresse et le port.")
            return
        
        # Si je suis générateur, envoyer (p,g) + ma clé publique
        if i_generate:
            if not await self.send_dh_params(uri, p, g):
                hello_done = False
                await self.reset_to_connection_setup("Échec de l'envoi des paramètres de chiffrement.")
                return
                
            if not await self.send_dh_public_key(uri, public_key):
                hello_done = False
                await self.reset_to_connection_setup("Échec de l'envoi de la clé publique.")
                return

    # ────────────────────── actions ────────────────────────
    async def action_reset_config(self) -> None:
        """Action pour retourner à l'écran de configuration ou à l'étape précédente."""
        # Si déjà dans la configuration, retourner à l'étape précédente
        if self.app_state.startswith("setup_"):
            await self.go_to_previous_config_step()
        # Si en mode conversation, revenir à la configuration
        elif self.app_state == "conversation":
            self.chat_view.add_message("Système", "Retour à l'écran de configuration...")
            await self.reset_to_connection_setup("Retour à la configuration demandé par l'utilisateur.")
        else:
            # Pas encore en conversation ou configuration
            await self.reset_to_connection_setup()
            
    async def go_to_previous_config_step(self):
        """Navigue vers l'étape de configuration précédente."""
        input_box = self.query_one("#user-input")
        
        # Recréer le conteneur de configuration au lieu de le vider
        old_container = self.welcome_container.query_one(".configuration-container")
        old_container.remove()
        
        # Créer un nouveau conteneur
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        self.welcome_container.mount(config_container)
        
        # Générer un timestamp unique pour les IDs
        unique_id_suffix = str(int(datetime.now().timestamp()))
        
        # Déterminer l'étape précédente selon l'étape actuelle
        match self.app_state:
            case "setup_target_port":
                # Retour à la saisie de l'IP
                self.app_state = "setup_target_ip"
                self.input_label = "Entrez l'adresse IP de l'autre personne: "
                input_box.placeholder = "Adresse IP"
                
                config_message = Static(
                    f"Mode: Connexion active\n"
                    f"Entrez l'adresse IP de l'autre personne:", 
                    id=f"setup-target-ip-content-{unique_id_suffix}",
                    classes="content-text"
                )
                config_container.mount(config_message)
                self.notify("Retour à la saisie de l'adresse IP", severity="information")
                
            case "setup_target_ip":
                # Retour à la sélection du mode
                self.app_state = "setup_mode"
                self.input_label = "Vous connecter (o) ou attendre (n)? "
                input_box.placeholder = "o/n"
                
                config_message = Static(
                    f"Nom d'utilisateur: {username}\n"
                    f"Port: {port}\n"
                    f"Adresse IP: {local_ip}\n\n"
                    f"Voulez-vous vous connecter à quelqu'un (o) ou attendre une connexion (n)?", 
                    id=f"setup-mode-content-{unique_id_suffix}",
                    classes="content-text"
                )
                config_container.mount(config_message)
                self.notify("Retour à la sélection du mode", severity="information")
                
            case "setup_mode":
                # Retour à la configuration du port
                self.app_state = "setup_port"
                self.input_label = "Entrez le port à utiliser: "
                input_box.placeholder = "Port (par défaut: 8765)"
                
                config_message = Static(
                    f"Nom d'utilisateur: {username}\n"
                    f"Configuration du port...", 
                    id=f"setup-username-content-{unique_id_suffix}", 
                    classes="content-text"
                )
                config_container.mount(config_message)
                self.notify("Retour à la configuration du port", severity="information")
                
            case "setup_port":
                # Retour à la saisie du nom d'utilisateur
                self.app_state = "setup_username"
                self.input_label = "Entrez votre nom d'utilisateur: "
                input_box.placeholder = "Votre nom (par défaut: User_xxx)"
                
                config_message = Static(
                    "Configuration du chat...", 
                    id=f"setup-start-content-{unique_id_suffix}", 
                    classes="content-text"
                )
                config_container.mount(config_message)
                self.notify("Retour à la saisie du nom d'utilisateur", severity="information")
                
            case _:
                # Par défaut, rester à la même étape
                self.notify("Impossible de revenir à une étape précédente", severity="warning")

# Point d'entrée principal
if __name__ == "__main__":
    # Lancer l'application Textual
    app = EncodHexApp()
    app.run()
