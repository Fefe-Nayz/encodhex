#!/usr/bin/env python3
# filepath: c:\Users\ferre\Codespace\Projects\encodhex\tui_app.py

import asyncio
import websockets
import socket
import json
import sys
import re
import os
import base64
from datetime import datetime
import threading
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Label, Static, Button, DirectoryTree
from textual.reactive import reactive
from textual.screen import ModalScreen
from rich.text import Text
from rich.panel import Panel
from textual.binding import Binding
from textual.message import Message
from PIL import Image, ImageOps
from rich_pixels import Pixels
from textual_slider import Slider
from aes.encryption import encrypt, decrypt
from diffie_hellman.diffie_hellman import (
    generate_parameters,
    generate_private_key,
    generate_public_key,
    compute_shared_key,
)

# ──────────────────────────── Data Classes ────────────────────────────
@dataclass
class PeerConnection:
    """Represents a connection to a peer."""
    ip: str
    port: int
    shared_key: Optional[str] = None
    public_key: Optional[int] = None
    encryption_ready: bool = False
    websocket: Optional[websockets.WebSocketServerProtocol] = None
    connection_established: bool = False

@dataclass 
class DHExchange:
    """Tracks Diffie-Hellman key exchange state."""
    dh_params: Optional[Tuple[int, int]] = None
    private_key: Optional[int] = None
    public_key: Optional[int] = None
    completed: bool = False

@dataclass
class AppState:
    """Central application state."""
    username: str = ""
    port: int = 8765
    local_ip: str = "127.0.0.1"
    in_waiting_mode: bool = False
    server_task: Optional[asyncio.Task] = None
    websocket_server: Optional[websockets.WebSocketServer] = None
    
    # Image quality settings - SIGNIFICANTLY IMPROVED + HIGHER RESOLUTION
    image_quality: int = 80  # Default to higher quality (was 70)
    max_image_width: int = 160  # Increased from 120 to 160
    max_image_height: int = 80  # Increased from 60 to 80
    
    # Mesh networking
    peers: Dict[str, PeerConnection] = field(default_factory=dict)
    dh_exchanges: Dict[str, DHExchange] = field(default_factory=dict)
    message_ids: Set[str] = field(default_factory=set)  # Prevent message loops
    
    # Connection state
    hello_done: Set[str] = field(default_factory=set)  # Track per-peer hello status
    
    def get_image_dimensions(self) -> Tuple[int, int]:
        """Get image dimensions based on quality setting - IMPROVED."""
        quality_factor = self.image_quality / 100.0
        # Higher base minimums for better quality
        width = int(self.max_image_width * quality_factor)
        height = int(self.max_image_height * quality_factor)
        return max(60, width), max(30, height)  # Higher minimums (was 40, 20)
    
    def get_peer_key(self, ip: str, port: int) -> str:
        """Generate a unique key for a peer."""
        return f"{ip}:{port}"
    
    def add_peer(self, ip: str, port: int, websocket: Optional[websockets.WebSocketServerProtocol] = None) -> PeerConnection:
        """Add a new peer connection."""
        key = self.get_peer_key(ip, port)
        peer = PeerConnection(ip=ip, port=port, websocket=websocket)
        self.peers[key] = peer
        self.dh_exchanges[key] = DHExchange()
        return peer
    
    def get_peer(self, ip: str, port: int) -> Optional[PeerConnection]:
        """Get a peer connection."""
        key = self.get_peer_key(ip, port)
        return self.peers.get(key)
    
    def remove_peer(self, ip: str, port: int):
        """Remove a peer connection."""
        key = self.get_peer_key(ip, port)
        self.peers.pop(key, None)
        self.dh_exchanges.pop(key, None)
        self.hello_done.discard(key)
    
    def get_ready_peers(self) -> List[PeerConnection]:
        """Get all peers with established encryption."""
        return [peer for peer in self.peers.values() if peer.encryption_ready and peer.connection_established]
    
    def get_connected_peer_count(self) -> int:
        """Get count of fully connected peers."""
        return len(self.get_ready_peers())

# Global app state
app_state = AppState()

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

def generate_message_id() -> str:
    """Generate a unique message ID - IMPROVED for better uniqueness."""
    import time
    import random
    timestamp = time.time_ns()  # Nanosecond precision
    random_part = random.randint(10000, 99999)
    return f"{app_state.username}_{timestamp}_{random_part}"

async def process_image_for_display_async(image_path: str) -> Union[Pixels, str]:
    """Convert an image to Rich Pixels with HIGH QUALITY - ASYNC version."""
    def _process_image():
        try:
            # Validate file size first (max 5MB)
            if os.path.getsize(image_path) > 5 * 1024 * 1024:
                return "[Image trop volumineuse (max 5MB)]"
            
            # Get quality-based dimensions (now much larger)
            max_width, max_height = app_state.get_image_dimensions()
            
            # Open and process image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate new size maintaining aspect ratio
                img_width, img_height = img.size
                aspect_ratio = img_width / img_height
                
                # IMPROVED: More aggressive sizing for better quality
                if aspect_ratio > max_width / max_height:
                    new_width = max_width  # Use full width available
                    new_height = int(new_width / aspect_ratio)
                else:
                    new_height = max_height  # Use full height available
                    new_width = int(new_height * aspect_ratio)
                
                # IMPROVED: Higher quality minimums based on setting
                quality_factor = app_state.image_quality / 100.0
                min_width = int(80 * quality_factor)  # Much higher minimums (was 60)
                min_height = int(40 * quality_factor)  # Much higher minimums (was 30)
                
                new_width = max(min_width, new_width)
                new_height = max(min_height, new_height)
                
                # IMPROVED: Always use highest quality resampling
                resampling = Image.Resampling.LANCZOS  # Always use best quality
                
                # IMPROVED: Multi-step resizing for better quality on large images
                if img_width > new_width * 3 or img_height > new_height * 3:
                    # First resize to 2x target, then to final size
                    intermediate_width = new_width * 2
                    intermediate_height = new_height * 2
                    img = img.resize((intermediate_width, intermediate_height), Image.Resampling.LANCZOS)
                
                resized_img = img.resize((new_width, new_height), resampling)
                
                # IMPROVED: Enhanced post-processing for terminal display
                if app_state.image_quality >= 60:
                    # Enhance contrast and sharpness
                    resized_img = ImageOps.autocontrast(resized_img, cutoff=0.5)
                    
                    # Optional: enhance colors for better terminal display
                    if app_state.image_quality >= 80:
                        # Boost saturation slightly for better terminal colors
                        from PIL import ImageEnhance
                        enhancer = ImageEnhance.Color(resized_img)
                        resized_img = enhancer.enhance(1.2)  # 20% more saturated
                
                # Create Rich Pixels object with optimized settings
                pixels = Pixels.from_image(resized_img)
                return pixels
                
        except Exception as e:
            return f"[Erreur d'affichage d'image: {e}]"
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_image)

# ────────────────────────────── Custom Widgets ──────────────────────────
class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree that only shows directories and image files."""
    
    def filter_paths(self, paths):
        """Filter to show only directories and image files."""
        def is_image_file(path):
            return path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg'}
        
        def is_directory(path):
            return path.is_dir()
        
        # Return paths that are either directories or image files
        return [path for path in paths if is_directory(path) or is_image_file(path)]

# ────────────────────────────── Modal Screens ──────────────────────────
class FileBrowserModal(ModalScreen[Optional[str]]):
    """Modal for browsing and selecting image files."""
    
    CSS = """
    FileBrowserModal {
        align: center middle;
    }
    
    #browser_dialog {
        width: 80;
        height: 25;
        border: thick $primary 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #directory_tree {
        width: 100%;
        height: 15;
        border: solid $primary;
    }
    
    #browser_buttons {
        width: 100%;
        height: 3;
        align: center middle;
        margin: 1 0;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container(id="browser_dialog"):
            yield Label("📁 Navigateur de fichiers", id="browser_title")
            yield FilteredDirectoryTree("./", id="directory_tree")
            
            with Horizontal(id="browser_buttons"):
                yield Button("✅ Sélectionner", id="select_file_btn", variant="success")
                yield Button("❌ Annuler", id="cancel_browse_btn", variant="error")
    
    def on_mount(self) -> None:
        # Focus the directory tree
        self.query_one("#directory_tree").focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select_file_btn":
            tree = self.query_one("#directory_tree")
            if tree.cursor_node and tree.cursor_node.data:
                try:
                    # Handle different possible data types from DirectoryTree
                    node_data = tree.cursor_node.data
                    
                    # Check if it's a Path object or has a path attribute
                    if hasattr(node_data, 'path'):
                        file_path = str(node_data.path)
                        is_file = node_data.path.is_file() if hasattr(node_data.path, 'is_file') else False
                    elif hasattr(node_data, 'is_file') and callable(getattr(node_data, 'is_file')):
                        # Direct DirEntry or similar object
                        file_path = str(node_data)
                        is_file = node_data.is_file()
                    else:
                        # Fallback: treat as string path
                        file_path = str(node_data)
                        is_file = os.path.isfile(file_path)
                    
                    if is_file:
                        # Check if it's an image file
                        if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg')):
                            self.dismiss(file_path)
                        else:
                            self.notify("Veuillez sélectionner un fichier image (.png, .jpg, .jpeg, .gif, .bmp, .webp, .tiff, .svg)", severity="warning")
                    else:
                        self.notify("Veuillez sélectionner un fichier", severity="warning")
                        
                except Exception as e:
                    self.notify(f"Erreur lors de la sélection: {e}", severity="error")
            else:
                self.notify("Veuillez sélectionner un fichier", severity="warning")
        elif event.button.id == "cancel_browse_btn":
            self.dismiss(None)
    
    def on_directory_tree_file_selected(self, event) -> None:
        """Handle double-click on file."""
        try:
            if hasattr(event, 'path') and event.path:
                if event.path.is_file() and str(event.path).lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg')):
                    self.dismiss(str(event.path))
                elif event.path.is_file():
                    self.notify("Veuillez sélectionner un fichier image", severity="warning")
            else:
                # Fallback for different event types
                file_path = str(event)
                if os.path.isfile(file_path) and file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg')):
                    self.dismiss(file_path)
        except Exception as e:
            self.notify(f"Erreur de sélection: {e}", severity="error")

class ImageSelectorModal(ModalScreen[Optional[str]]):
    """Modal for selecting images with quality settings."""
    
    DEFAULT_CSS = """
    ImageSelectorModal {
        align: center middle;
    }
    
    #image_dialog {
        width: 70;
        height: 20;
        border: thick $primary 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #image_path_input {
        width: 100%;
        margin: 1 0;
    }
    
    #quality_container {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    
    #button_container {
        width: 100%;
        height: 3;
        align: center middle;
        margin: 1 0;
    }
    
    #button_container Button {
        width: 12;
        margin: 0 1;
        min-height: 3;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container(id="image_dialog"):
            yield Label("📸 Sélection d'image", id="title")
            yield Input(
                placeholder="Entrez le chemin de l'image...",
                id="image_path_input"
            )
            
            with Container(id="quality_container"):
                yield Label(f"Qualité: {app_state.image_quality}%")
                yield Slider(
                    min=50,
                    max=100,
                    value=app_state.image_quality,
                    step=10,
                    id="quality_slider"
                )
            
            with Horizontal(id="button_container"):
                yield Button("📁 Parcourir", id="browse_btn", variant="primary")
                yield Button("✅ Envoyer", id="send_btn", variant="success")
                yield Button("❌ Annuler", id="cancel_btn", variant="error")
    
    def on_mount(self) -> None:
        # Set focus to the input initially, but ensure buttons can be focused
        input_field = self.query_one("#image_path_input")
        input_field.focus()
        
        # Ensure all buttons are enabled and focusable
        for button in self.query("Button"):
            button.disabled = False
    
    def on_slider_changed(self, event: Slider.Changed) -> None:
        """Update quality setting when slider changes."""
        app_state.image_quality = int(event.value)
        self.query_one("#quality_container Label").update(f"Qualité: {app_state.image_quality}%")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Stop event propagation to ensure we handle it
        event.stop()
        
        button_id = event.button.id
        
        # Add debug notification to see which button was pressed
        self.notify(f"Modal button pressed: {button_id}", severity="information")
        
        if button_id == "send_btn":
            path = self.query_one("#image_path_input").value.strip()
            self.notify(f"Attempting to send: {path}", severity="information")
            if path and os.path.isfile(path):
                # Check if it's an image file
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg')):
                    self.dismiss(path)
                else:
                    self.notify("Veuillez sélectionner un fichier image valide", severity="error")
            else:
                self.notify("Fichier non trouvé!", severity="error")
        elif button_id == "browse_btn":
            # Open the file browser modal
            def handle_file_selection(file_path):
                if file_path:
                    self.on_file_selected(file_path)
            
            self.app.push_screen(FileBrowserModal(), handle_file_selection)
        elif button_id == "cancel_btn":
            self.dismiss(None)
    
    def on_file_selected(self, file_path: Optional[str]) -> None:
        """Handle file selection from the browser."""
        if file_path:
            self.query_one("#image_path_input").value = file_path
            self.notify(f"Fichier sélectionné: {os.path.basename(file_path)}", severity="information")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter key in input field."""
        if event.input.id == "image_path_input":
            path = event.input.value.strip()
            if path and os.path.isfile(path):
                self.dismiss(path)
            else:
                self.notify("Fichier non trouvé!", severity="error")

# ────────────────────────────── widgets ──────────────────────────────
class ChatView(ScrollableContainer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def add_message(self, sender, message, timestamp=None, is_image=False):
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M:%S")

        if sender == app_state.username:
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold green")
            if is_image:
                msg.append("[Image envoyée]", style="italic")
            else:
                msg.append(message)
        elif sender == "Système":
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold blue")
            msg.append(message)
        else:
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold yellow")
            if is_image:
                msg.append("[Image reçue]", style="italic")
            else:
                msg.append(message)

        self.messages.append(msg)
        
        # If it's an image, add a placeholder for the image content
        if is_image and not sender == "Système":
            if sender == app_state.username:
                # For sent images, show processing message
                placeholder = Text("[Traitement de l'image...]", style="dim")
            else:
                # For received images, show processing message
                placeholder = Text("[Traitement de l'image reçue...]", style="dim")
            
            self.messages.append(placeholder)
        
        self.update_messages()
        self.scroll_end()

    def update_image_display(self, display_content: Union[Pixels, str]):
        """Update the last image message with processed content (now supports Rich Pixels!)."""
        if self.messages and len(self.messages) >= 2:
            # Replace the last message (which should be the image placeholder)
            if isinstance(display_content, Pixels):
                # Rich Pixels object - can be rendered directly!
                self.messages[-1] = display_content
            else:
                # String fallback (error messages)
                self.messages[-1] = Text(str(display_content), style="red")
            
            self.update_messages()
            self.scroll_end()

    def update_messages(self):
        self.query("*").remove()
        for msg in self.messages:
            if isinstance(msg, Pixels):
                # Rich Pixels can be rendered directly in Textual
                self.mount(Static(msg))
            else:
                # Text and other Rich objects
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

    #input-label {
        width: auto;
        color: $text;
        background: $surface;
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

    .error-message {
        color: $error;
        text-style: bold;
    }

    #image-btn {
        width: 4;
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quitter"),
        Binding("ctrl+q", "quit", "Quitter"),
        Binding("ctrl+r", "reset_config", "Config"),
        Binding("f5", "select_image", "📸 Image", show=True),
    ]

    app_state_ui = reactive("welcome")
    status_text = reactive("")
    input_label = reactive("> ")

    def __init__(self):
        super().__init__()
        self.chat_view = ChatView(id="chat-view")
        self.welcome_container = Container(id="welcome-message")
        app_state.local_ip = get_local_ip()

    # ────────────────────────── lifecycle ──────────────────────────
    async def on_mount(self) -> None:
        await self.show_welcome()
        input_field = self.query_one("#user-input")
        input_field.focus()
        
        self.set_interval(0.01, self.update_input_container_styling)
        self.set_interval(1.0, self.update_ui_status)  # Regular status updates
        
        self.query_one("#header").title = (
            "Chat Peer-to-Peer chiffré avec Diffie-Hellman/AES-256 - Mesh Network"
        )
    
    def update_input_container_styling(self) -> None:
        """Update input container and label styling based on input focus."""
        input_field = self.query_one("#user-input")
        container = self.query_one("#input-container")
        label = self.query_one("#input-label")
        
        if input_field.has_focus:
            container.add_class("focused-bg")
            label.add_class("focused-bg")
        else:
            container.remove_class("focused-bg")
            label.remove_class("focused-bg")

    def update_ui_status(self) -> None:
        """Periodic update of UI status and peer count."""
        if self.app_state_ui == "conversation":
            peer_count = app_state.get_connected_peer_count()
            
            # Update status bar
            status = f"{app_state.username} | {app_state.local_ip}:{app_state.port} | Peers: {peer_count}"
            if peer_count > 0:
                status += " | 🔒 Chiffré"
                # Switch from waiting mode if we have connections
                if app_state.in_waiting_mode and peer_count > 0:
                    app_state.in_waiting_mode = False
            self.update_status(status)
            
            # Update window title
            if peer_count == 0:
                if app_state.in_waiting_mode:
                    self.title = f"EncodHex Mesh - {app_state.username} - En attente"
                else:
                    self.title = f"EncodHex Mesh - {app_state.username} - Aucune connexion"
            else:
                self.title = f"EncodHex Mesh - {app_state.username} - {peer_count} peer(s)"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, id="header")

        with Container(id="main-container"):
            yield Static("", id="status-bar")
            yield self.welcome_container

            with Container(id="chat-pad"):
                yield self.chat_view

        with Container(id="input-container"):
            yield Label(self.input_label, id="input-label")
            # Start with welcome placeholder, will be updated when entering conversation
            yield Input(placeholder="Appuyez sur Entrée pour continuer...", id="user-input")

        yield Footer()

    # ─────────────────────────── vues ────────────────────────────
    async def show_welcome(self):
        self.welcome_container.styles.display = "block"
        self.chat_view.styles.display = "none"
        self.query_one("#chat-pad").styles.display = "none"

        self.title = "Chat Peer-to-Peer chiffré avec Diffie-Hellman/AES-256 - Mesh Network"
        self.welcome_container.query("*").remove()

        welcome_text = (
            "Bienvenue dans EncodHex - Chat P2P Chiffré Mesh\n\n"
            "Version 2.3 - Enhanced UX & Performance Edition\n"
            "Développé par Nino Belaoud & Ferréol DUBOIS COLI\n\n"
            "✨ Nouvelles fonctionnalités v2.3:\n"
            "• Ctrl+I pour sélection d'images avec aperçu\n"
            "• Slider de qualité d'image (30-100%)\n"
            "• Envoi concurrent vers tous les peers\n"
            "• Traitement parallèle des images reçues\n\n"
            "Fonctionnalités existantes:\n"
            "• Conversations de groupe (mesh network)\n"
            "• Images COULEUR haute qualité\n"
            "• Chiffrement bout-à-bout sécurisé\n\n"
            "Appuyez sur Entrée pour commencer"
        )

        welcome_box = Container(classes="conversation-welcome")
        welcome_box.border_title = "EncodHex Mesh v2.3 - Enhanced UX"
        self.welcome_container.mount(welcome_box)
        welcome_box.mount(Static(welcome_text, classes="content-text"))

        self.welcome_container.styles.content_align_horizontal = "center"
        self.welcome_container.styles.content_align_vertical = "middle"

        self.app_state_ui = "welcome"
        self.input_label = "> "

    def show_conversation(self):
        self.welcome_container.styles.display = "none"
        self.query_one("#chat-pad").styles.display = "block"
        self.chat_view.styles.display = "block"

        status_bar = self.query_one("#status-bar")
        status_bar.styles.display = "block"
        
        # Update input placeholder and add image button for conversation mode
        input_field = self.query_one("#user-input")
        input_field.placeholder = "Tapez votre message ou F5 pour images..."
        
        # Add image button if not already present
        input_container = self.query_one("#input-container")
        existing_button = input_container.query("#image-btn")
        if not existing_button:
            input_container.mount(Button("📸", id="image-btn", variant="primary"))

        self.chat_view.border_title = "Chat Mesh"

        self.app_state_ui = "conversation"
        self.input_label = "> "

    def update_status(self, status):
        self.query_one("#status-bar").update(status)
        
    def show_error_in_config(self, error_message):
        """Affiche un message d'erreur dans le conteneur de configuration."""
        config_container = self.welcome_container.query_one(".configuration-container")
        
        error_widget = config_container.query(".error-message")
        if error_widget:
            error_widget.remove()
            
        config_container.mount(Static(error_message, classes="error-message"))
        self.notify(error_message, severity="error", timeout=5)

    # ───────────────────────── gestion input ──────────────────────
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        box = event.input
        box.value = ""

        match self.app_state_ui:
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
        self.app_state_ui = "setup_username"
        self.input_label = "Entrez votre nom d'utilisateur: "
        input_box.placeholder = "Votre nom (par défaut: User_xxx)"
        
        self.welcome_container.query("*").remove()
        
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        self.welcome_container.mount(config_container)
        
        config_message = Static("Configuration du chat mesh...", classes="content-text")
        config_container.mount(config_message)

    async def setup_username(self, value, input_box):
        if value:
            app_state.username = value
        else:
            app_state.username = f"User_{socket.gethostname()}"
        
        self.app_state_ui = "setup_port"
        self.input_label = "Entrez le port à utiliser: "
        input_box.placeholder = "Port (par défaut: 8765)"
        
        old_container = self.welcome_container.query_one(".configuration-container")
        old_container.remove()
        
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        self.welcome_container.mount(config_container)
        
        config_container.mount(Static(
            f"Nom d'utilisateur: {app_state.username}\n"
            f"Configuration du port...", 
            classes="content-text"
        ))

    async def setup_port(self, value, input_box):
        if value.strip():
            if not is_valid_port(value):
                self.show_error_in_config("Port invalide! Veuillez entrer un nombre entre 1 et 65535.")
                return
            app_state.port = int(value)
        else:
            app_state.port = 8765
        
        # Start WebSocket server
        port_success = await self.try_start_server(app_state.port)
        if not port_success:
            self.show_error_in_config(f"Impossible de démarrer le serveur sur aucun port disponible.")
            return
        
        self.app_state_ui = "setup_mode"
        self.input_label = "Vous connecter (o) ou attendre (n)? "
        input_box.placeholder = "o/n"
        
        old_container = self.welcome_container.query_one(".configuration-container")
        old_container.remove()
        
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        self.welcome_container.mount(config_container)
        
        config_container.mount(Static(
            f"Nom d'utilisateur: {app_state.username}\n"
            f"Port: {app_state.port}\n"
            f"Adresse IP: {app_state.local_ip}\n\n"
            f"Mode mesh: Connectez-vous à un peer ou attendez des connexions", 
            classes="content-text"
        ))

    async def try_start_server(self, start_port):
        """Essaie de démarrer le serveur sur un port, ou tente les ports suivants."""
        max_attempts = 10
        current_port = start_port
        
        for _ in range(max_attempts):
            try:
                await self.start_websocket_server(current_port)
                if current_port != start_port:
                    self.chat_view.add_message("Système", f"Port {start_port} déjà utilisé, serveur démarré sur le port {current_port} à la place")
                app_state.port = current_port
                self.notify(f"Serveur démarré sur le port {app_state.port}", severity="information")
                return True
            except OSError as e:
                if e.errno == 10048:
                    self.notify(f"Port {current_port} déjà utilisé, essai du port {current_port+1}", severity="warning")
                    current_port += 1
                else:
                    error_msg = f"Erreur lors du démarrage du serveur: {e}"
                    self.show_error_in_config(error_msg)
                    return False
            except Exception as e:
                error_msg = f"Erreur inattendue: {e}"
                self.show_error_in_config(error_msg)
                return False
        
        return False

    async def start_websocket_server(self, server_port=None):
        """Démarrer le serveur WebSocket sur le port spécifié."""
        if server_port is None:
            server_port = app_state.port
            
        try:
            server = await websockets.serve(self.handle_connection, "0.0.0.0", server_port)
            app_state.websocket_server = server
            self.notify(f"Serveur démarré sur {app_state.local_ip}:{server_port}")
            return server
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur lors du démarrage du serveur: {e}")
            raise

    async def handle_connection(self, websocket):
        """Handle incoming WebSocket connections with mesh networking support."""
        try:
            remote_ip = websocket.remote_address[0] if hasattr(websocket, 'remote_address') else None
            remote_port = None
            peer_key = None
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    self.chat_view.add_message("Système", "Message reçu invalide (format JSON incorrect)")
                    continue
                    
                timestamp = datetime.now().strftime("%H:%M:%S")
                message_type = data.get('type', 'text')
                
                # Extract sender info for peer tracking
                if 'sender_port' in data and remote_ip:
                    remote_port = int(data['sender_port'])
                    peer_key = app_state.get_peer_key(remote_ip, remote_port)
                
                # Handle different message types
                await self.handle_message_type(data, message_type, websocket, remote_ip, remote_port, peer_key)
                
        except websockets.exceptions.ConnectionClosed:
            if peer_key:
                app_state.remove_peer(remote_ip, remote_port)
                self.chat_view.add_message("Système", f"Peer {remote_ip}:{remote_port} disconnected")
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur de connexion: {e}")

    async def handle_message_type(self, data, message_type, websocket, remote_ip, remote_port, peer_key):
        """Handle different types of messages in the mesh network."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if message_type == 'hello':
            await self.handle_hello_message(data, remote_ip, remote_port, peer_key, websocket)
        
        elif message_type == 'peer_list':
            await self.handle_peer_list_message(data, remote_ip, remote_port)
        
        elif message_type == 'dh_params':
            await self.handle_dh_params_message(data, remote_ip, remote_port, peer_key)
        
        elif message_type == 'dh_public_key':
            await self.handle_dh_public_key_message(data, remote_ip, remote_port, peer_key)
        
        elif message_type == 'text':
            await self.handle_text_message(data, peer_key)
        
        elif message_type == 'image':
            await self.handle_image_message(data, peer_key)
        
        elif message_type == 'ack':
            # Acknowledgment messages don't need special handling
            pass

    async def handle_hello_message(self, data, remote_ip, remote_port, peer_key, websocket):
        """Handle hello messages for mesh network setup."""
        if peer_key in app_state.hello_done:
            return
        
        app_state.hello_done.add(peer_key)
        self.chat_view.add_message("Système", f"Nouvelle connexion de {remote_ip}:{remote_port}")
        
        # Add peer to our network
        peer = app_state.add_peer(remote_ip, remote_port, websocket)
        peer.connection_established = True
        
        # Send list of existing peers to the new peer
        existing_peers = [(p.ip, p.port) for p in app_state.peers.values() 
                         if (p.ip != remote_ip or p.port != remote_port) and p.connection_established]
        
        if existing_peers:
            await self.send_json_to_peer(remote_ip, remote_port, {
                "type": "peer_list",
                "peers": existing_peers,
                "sender": app_state.username,
                "sender_port": app_state.port,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
        
        # Start DH key exchange
        await self.initiate_dh_exchange(remote_ip, remote_port, peer_key, data.get("i_generate", False))

    async def handle_peer_list_message(self, data, remote_ip, remote_port):
        """Handle peer list messages to connect to other mesh nodes."""
        peers = data.get('peers', [])
        self.chat_view.add_message("Système", f"Découverte de {len(peers)} peers dans le mesh")
        
        # Connect to each peer in the list
        for peer_ip, peer_port in peers:
            if not app_state.get_peer(peer_ip, peer_port):
                self.chat_view.add_message("Système", f"Connexion au peer {peer_ip}:{peer_port}")
                # Use a task to avoid blocking
                asyncio.create_task(self.establish_full_peer_connection(peer_ip, peer_port))

    async def establish_full_peer_connection(self, target_ip, target_port):
        """Establish a complete peer connection with DH key exchange."""
        peer_key = app_state.get_peer_key(target_ip, target_port)
        
        if peer_key in app_state.hello_done:
            return  # Already connected
        
        try:
            # Add peer first
            peer = app_state.add_peer(target_ip, target_port)
            
            # Attempt connection with retries
            uri = f"ws://{target_ip}:{target_port}"
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    async with websockets.connect(uri, ping_timeout=10, close_timeout=5) as websocket:
                        # Mark as hello done
                        app_state.hello_done.add(peer_key)
                        peer.connection_established = True
                        
                        # Send hello
                        await websocket.send(json.dumps({
                            "type": "hello",
                            "sender": app_state.username,
                            "i_generate": False,  # Let the other peer generate if needed
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "sender_port": app_state.port
                        }))
                        
                        # Wait for DH exchange to complete
                        timeout_counter = 0
                        while not peer.encryption_ready and timeout_counter < 30:  # 30 second timeout
                            try:
                                response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                                data = json.loads(response)
                                await self.handle_message_type(data, data.get('type'), websocket, target_ip, target_port, peer_key)
                            except asyncio.TimeoutError:
                                timeout_counter += 1
                                continue
                        
                        if peer.encryption_ready:
                            self.chat_view.add_message("Système", f"✅ Connexion sécurisée établie avec {target_ip}:{target_port}")
                            return
                        else:
                            self.chat_view.add_message("Système", f"⚠️ Timeout lors de l'échange de clés avec {target_ip}:{target_port}")
                            break
                            
                except Exception as e:
                    if attempt == max_retries - 1:
                        self.chat_view.add_message("Système", f"❌ Échec de connexion à {target_ip}:{target_port}: {e}")
                    else:
                        await asyncio.sleep(1)  # Wait before retry
                        
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur lors de la connexion à {target_ip}:{target_port}: {e}")
        finally:
            # Clean up on failure
            if not app_state.get_peer(target_ip, target_port) or not app_state.get_peer(target_ip, target_port).encryption_ready:
                app_state.remove_peer(target_ip, target_port)

    async def handle_dh_params_message(self, data, remote_ip, remote_port, peer_key):
        """Handle Diffie-Hellman parameter messages."""
        p, g = data.get('p'), data.get('g')
        
        if p is None or g is None or peer_key not in app_state.dh_exchanges:
            self.chat_view.add_message("Système", "Erreur: Paramètres Diffie-Hellman incomplets")
            return
            
        self.chat_view.add_message("Système", f"Paramètres DH reçus de {remote_ip}:{remote_port}")
        
        dh_exchange = app_state.dh_exchanges[peer_key]
        dh_exchange.dh_params = (p, g)
        dh_exchange.private_key = generate_private_key(p)
        dh_exchange.public_key = generate_public_key(p, g, dh_exchange.private_key)
        
        # Send our public key
        await self.send_dh_public_key_to_peer(remote_ip, remote_port, dh_exchange.public_key)

    async def handle_dh_public_key_message(self, data, remote_ip, remote_port, peer_key):
        """Handle Diffie-Hellman public key messages."""
        if peer_key not in app_state.dh_exchanges:
            self.chat_view.add_message("Système", "Erreur: Exchange DH non trouvé")
            return
        
        dh_exchange = app_state.dh_exchanges[peer_key]
        peer = app_state.get_peer(remote_ip, remote_port)
        
        if not dh_exchange.dh_params or not peer:
            self.chat_view.add_message("Système", "Erreur: Paramètres DH ou peer manquant")
            return
            
        other_public = data.get('public_key')
        if other_public is None:
            self.chat_view.add_message("Système", "Erreur: Clé publique manquante")
            return
            
        self.chat_view.add_message("Système", f"Clé publique reçue de {remote_ip}:{remote_port}")
        
        # Compute shared key
        p = dh_exchange.dh_params[0]
        shared_key = compute_shared_key(p, other_public, dh_exchange.private_key)
        peer.shared_key = str(shared_key)
        peer.encryption_ready = True
        
        self.chat_view.add_message("Système", f"🔒 Chiffrement établi avec {remote_ip}:{remote_port}!")

    async def handle_text_message(self, data, peer_key):
        """Handle encrypted text messages with proper mesh forwarding."""
        if 'message' not in data:
            self.chat_view.add_message("Système", "Erreur: Message reçu sans contenu")
            return
        
        peer = app_state.peers.get(peer_key)
        if not peer or not peer.encryption_ready or not peer.shared_key:
            self.chat_view.add_message("Système", "Erreur: Message reçu mais chiffrement non établi")
            return
        
        # Check for message loop prevention
        message_id = data.get('message_id', '')
        if message_id in app_state.message_ids:
            return  # Already processed this message
        
        app_state.message_ids.add(message_id)
        
        try:
            decrypted_message = decrypt(data['message'], peer.shared_key)
            self.chat_view.add_message(data.get('sender', 'Inconnu'), decrypted_message, data.get('timestamp'))
            
            # Forward to other peers (FIXED: re-encrypt for each peer)
            await self.forward_decrypted_message_to_peers(
                sender=data.get('sender', 'Inconnu'),
                message=decrypted_message,
                message_id=message_id,
                timestamp=data.get('timestamp'),
                exclude_peer=peer_key
            )
            
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur de déchiffrement: {e}")

    async def handle_image_message(self, data, peer_key):
        """Handle encrypted image messages with PARALLEL processing to prevent freezes."""
        if 'image_data' not in data:
            self.chat_view.add_message("Système", "Erreur: Image reçue sans données")
            return
        
        peer = app_state.peers.get(peer_key)
        if not peer or not peer.encryption_ready or not peer.shared_key:
            self.chat_view.add_message("Système", "Erreur: Image reçue mais chiffrement non établi")
            return
        
        # Check for message loop prevention
        message_id = data.get('message_id', '')
        if message_id in app_state.message_ids:
            return
        
        app_state.message_ids.add(message_id)
        
        # Display placeholder immediately
        self.chat_view.add_message(data.get('sender', 'Inconnu'), "[Image reçue - Traitement en cours...]", 
                                 data.get('timestamp'), is_image=True)
        
        # Process image in parallel without blocking the UI
        asyncio.create_task(self._process_received_image_parallel(
            data, peer, message_id
        ))
        
        # Forward to other peers immediately (don't wait for processing)
        try:
            decrypted_b64 = decrypt(data['image_data'], peer.shared_key)
            await self.forward_image_to_peers(
                sender=data.get('sender', 'Inconnu'),
                image_b64=decrypted_b64,
                message_id=message_id,
                timestamp=data.get('timestamp'),
                exclude_peer=peer_key
            )
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur de forwarding d'image: {e}")
    
    async def _process_received_image_parallel(self, data, peer, message_id):
        """Process received image in parallel using thread pool."""
        try:
            # Decrypt in thread pool to avoid blocking
            def decrypt_image():
                return decrypt(data['image_data'], peer.shared_key)
            
            loop = asyncio.get_event_loop()
            decrypted_b64 = await loop.run_in_executor(None, decrypt_image)
            
            # Decode and save to temp file in thread pool
            def save_temp_image():
                image_bytes = base64.b64decode(decrypted_b64)
                temp_path = f"temp_image_{message_id}.png"
                with open(temp_path, 'wb') as f:
                    f.write(image_bytes)
                return temp_path
            
            temp_path = await loop.run_in_executor(None, save_temp_image)
            
            # Process for display with quality settings
            display_content = await process_image_for_display_async(temp_path)
            
            # Update the display on main thread
            self.chat_view.update_image_display(display_content)
            
            # Clean up temp file in thread pool
            def cleanup():
                try:
                    os.remove(temp_path)
                except:
                    pass
            
            await loop.run_in_executor(None, cleanup)
            
        except Exception as e:
            self.chat_view.update_image_display(f"[Erreur de traitement: {e}]")

    async def forward_decrypted_message_to_peers(self, sender, message, message_id, timestamp, exclude_peer=None):
        """Forward a decrypted message to all other peers (re-encrypted for each)."""
        ready_peers = app_state.get_ready_peers()
        
        for peer in ready_peers:
            peer_key = app_state.get_peer_key(peer.ip, peer.port)
            if peer_key != exclude_peer:
                try:
                    # Re-encrypt with this peer's key
                    encrypted_message = encrypt(message, peer.shared_key)
                    await self.send_json_to_peer(peer.ip, peer.port, {
                        "type": "text",
                        "sender": sender,
                        "message": encrypted_message,
                        "message_id": message_id,
                        "timestamp": timestamp,
                        "sender_port": app_state.port
                    })
                except Exception as e:
                    self.chat_view.add_message("Système", f"Erreur forwarding vers {peer.ip}:{peer.port}: {e}")

    async def forward_image_to_peers(self, sender, image_b64, message_id, timestamp, exclude_peer=None):
        """Forward a decrypted image to all other peers (re-encrypted for each)."""
        ready_peers = app_state.get_ready_peers()
        
        for peer in ready_peers:
            peer_key = app_state.get_peer_key(peer.ip, peer.port)
            if peer_key != exclude_peer:
                try:
                    # Re-encrypt with this peer's key
                    encrypted_image = encrypt(image_b64, peer.shared_key)
                    await self.send_json_to_peer(peer.ip, peer.port, {
                        "type": "image",
                        "sender": sender,
                        "image_data": encrypted_image,
                        "message_id": message_id,
                        "timestamp": timestamp,
                        "sender_port": app_state.port
                    })
                except Exception as e:
                    self.chat_view.add_message("Système", f"Erreur forwarding image vers {peer.ip}:{peer.port}: {e}")

    async def initiate_dh_exchange(self, remote_ip, remote_port, peer_key, they_generate):
        """Initiate Diffie-Hellman key exchange."""
        if peer_key not in app_state.dh_exchanges:
            return
        
        dh_exchange = app_state.dh_exchanges[peer_key]
        
        # Determine who generates parameters
        def _id(ip, p):
            return tuple(map(int, ip.split('.'))) + (p,)
        
        i_generate = _id(app_state.local_ip, app_state.port) < _id(remote_ip, remote_port)
        
        if i_generate and not they_generate:
            self.chat_view.add_message("Système", f"Génération des paramètres DH pour {remote_ip}:{remote_port}")
            p, g = generate_parameters()
            dh_exchange.dh_params = (p, g)
            dh_exchange.private_key = generate_private_key(p)
            dh_exchange.public_key = generate_public_key(p, g, dh_exchange.private_key)
            
            await self.send_dh_params_to_peer(remote_ip, remote_port, p, g)
            await self.send_dh_public_key_to_peer(remote_ip, remote_port, dh_exchange.public_key)

    async def send_json_to_peer(self, target_ip, target_port, payload):
        """Send JSON to a specific peer with retry logic."""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                uri = f"ws://{target_ip}:{target_port}"
                async with websockets.connect(uri, ping_timeout=5, close_timeout=3) as ws:
                    await ws.send(json.dumps(payload))
                    return True
            except Exception as e:
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(0.5)
        return False

    async def send_hello(self, uri, i_generate):
        """Envoie un message hello pour initier la connexion."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            async with websockets.connect(uri, ping_timeout=5, close_timeout=5) as ws:
                await ws.send(json.dumps({
                    "type": "hello",
                    "sender": app_state.username,
                    "i_generate": i_generate,
                    "timestamp": timestamp,
                    "sender_port": app_state.port
                }))
                return True
        except Exception as e:
            self.chat_view.add_message("Système", f"Échec de connexion à {uri}")
            return False

    async def send_dh_params_to_peer(self, target_ip, target_port, p, g):
        """Envoie les paramètres Diffie-Hellman à un peer spécifique."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        success = await self.send_json_to_peer(target_ip, target_port, {
            "type": "dh_params",
            "sender": app_state.username,
            "p": p,
            "g": g,
            "timestamp": timestamp,
            "sender_port": app_state.port
        })
        
        if success:
            self.chat_view.add_message("Système", f"Paramètres DH envoyés à {target_ip}:{target_port}")
        return success

    async def send_dh_public_key_to_peer(self, target_ip, target_port, pub_key):
        """Envoie la clé publique Diffie-Hellman à un peer spécifique."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        success = await self.send_json_to_peer(target_ip, target_port, {
            "type": "dh_public_key",
            "sender": app_state.username,
            "public_key": pub_key,
            "timestamp": timestamp,
            "sender_port": app_state.port
        })
        
        if success:
            self.chat_view.add_message("Système", f"Clé publique envoyée à {target_ip}:{target_port}")
        return success

    async def broadcast_message_to_peers(self, message_text=None, image_path=None):
        """Broadcast a message or image to all connected peers CONCURRENTLY."""
        ready_peers = app_state.get_ready_peers()
        if not ready_peers:
            self.chat_view.add_message("Système", "Aucun peer connecté pour recevoir le message")
            return
        
        message_id = generate_message_id()
        app_state.message_ids.add(message_id)  # Prevent echo
        
        # Prepare tasks for concurrent sending
        send_tasks = []
        
        for peer in ready_peers:
            if message_text is not None:
                # Text message task
                task = self._send_text_to_peer(peer, message_text, message_id)
            elif image_path is not None:
                # Image message task
                task = self._send_image_to_peer(peer, image_path, message_id)
            else:
                continue
            
            send_tasks.append(task)
        
        # Send to all peers concurrently
        if send_tasks:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            
            # Check for any failures
            failures = [result for result in results if isinstance(result, Exception)]
            if failures:
                self.chat_view.add_message("Système", f"Erreurs d'envoi: {len(failures)}/{len(send_tasks)} échecs")
    
    async def _send_text_to_peer(self, peer: PeerConnection, message_text: str, message_id: str):
        """Send a text message to a specific peer."""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            encrypted_message = encrypt(message_text, peer.shared_key)
            
            await self.send_json_to_peer(peer.ip, peer.port, {
                "type": "text",
                "sender": app_state.username,
                "message": encrypted_message,
                "message_id": message_id,
                "timestamp": timestamp,
                "sender_port": app_state.port
            })
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur d'envoi vers {peer.ip}:{peer.port}: {e}")
            raise e
    
    async def _send_image_to_peer(self, peer: PeerConnection, image_path: str, message_id: str):
        """Send an image to a specific peer."""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Read and encode image
            with open(image_path, 'rb') as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            encrypted_image = encrypt(image_data, peer.shared_key)
            
            await self.send_json_to_peer(peer.ip, peer.port, {
                "type": "image",
                "sender": app_state.username,
                "image_data": encrypted_image,
                "message_id": message_id,
                "timestamp": timestamp,
                "sender_port": app_state.port
            })
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur d'envoi d'image vers {peer.ip}:{peer.port}: {e}")
            raise e

    async def setup_mode(self, value, input_box):
        choice = value.lower()
        if choice in ('o', 'oui'):
            app_state.in_waiting_mode = False
            
            self.app_state_ui = "setup_target_ip"
            self.input_label = "Entrez l'adresse IP d'un peer: "
            input_box.placeholder = "Adresse IP"
            
            old_container = self.welcome_container.query_one(".configuration-container")
            old_container.remove()
            
            config_container = Container(classes="configuration-container")
            config_container.border_title = "Configuration"
            self.welcome_container.mount(config_container)
            
            config_container.mount(Static(
                f"Mode: Connexion à un mesh\n"
                f"Entrez l'adresse IP d'un peer du réseau:", 
                classes="content-text"
            ))
            
        elif choice in ('n', 'non'):
            app_state.in_waiting_mode = True
            
            self.app_state_ui = "conversation"
            self.show_conversation()
            
            self.chat_view.add_message("Système", "Mode mesh démarré - En attente de connexions...")
            self.chat_view.add_message("Système", f"Votre adresse: {app_state.local_ip}:{app_state.port}")
            self.chat_view.add_message("Système", "Partagez ces informations pour rejoindre votre mesh.")
        else:
            error_msg = "Veuillez entrer 'o' pour vous connecter ou 'n' pour attendre."
            self.show_error_in_config(error_msg)

    async def setup_target_ip(self, value, input_box):
        if value.strip():
            if not is_valid_ip(value):
                self.show_error_in_config("Adresse IP invalide.")
                return
                
            self.target_ip = value
            
            self.app_state_ui = "setup_target_port"
            self.input_label = "Entrez le port du peer: "
            input_box.placeholder = f"Port (défaut: {app_state.port})"
            
            old_container = self.welcome_container.query_one(".configuration-container")
            old_container.remove()
            
            config_container = Container(classes="configuration-container")
            config_container.border_title = "Configuration"
            self.welcome_container.mount(config_container)
            
            config_container.mount(Static(
                f"Mode: Connexion au mesh\n"
                f"Peer IP: {self.target_ip}\n"
                f"Entrez le port du peer:", 
                classes="content-text"
            ))
        else:
            self.show_error_in_config("L'adresse IP est requise.")

    async def setup_target_port(self, value, input_box):
        if value.strip():
            if not is_valid_port(value):
                self.show_error_in_config("Port invalide!")
                return
            self.target_port = int(value)
        else:
            self.target_port = app_state.port
        
        self.app_state_ui = "conversation"
        self.show_conversation()
        
        self.chat_view.add_message("Système", f"Connexion au mesh via {self.target_ip}:{self.target_port}...")
        
        # Connect to the mesh
        asyncio.create_task(self.establish_full_peer_connection(self.target_ip, self.target_port))

    async def handle_message(self, message):
        if not message:
            return
        
        if message.lower() == "exit":
            await self.action_quit()
            return
        
        # Check if it's a file path for image
        if os.path.isfile(message) and message.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg')):
            try:
                # Validate file size
                if os.path.getsize(message) > 5 * 1024 * 1024:  # 5MB limit
                    self.chat_view.add_message("Système", "Image trop volumineuse (max 5MB)")
                    return
                
                # Display locally first with placeholder
                self.chat_view.add_message(app_state.username, "[Image envoyée]", is_image=True)
                
                # Process image asynchronously with rich-pixels for full color
                display_content = await process_image_for_display_async(message)
                self.chat_view.update_image_display(display_content)
                
                # Send to peers
                await self.broadcast_message_to_peers(image_path=message)
                
            except Exception as e:
                self.chat_view.add_message("Système", f"Erreur d'envoi d'image: {e}")
        else:
            # Send text message
            self.chat_view.add_message(app_state.username, message)
            await self.broadcast_message_to_peers(message_text=message)

    # ────────────────────── actions ────────────────────────
    async def action_select_image(self) -> None:
        """Open image selector modal (F5)."""
        if self.app_state_ui != "conversation":
            self.notify("Images disponibles uniquement en conversation", severity="warning")
            return
        
        try:
            # Open the image selector modal using the correct pattern
            def handle_image_result(result):
                if result:  # User selected an image
                    # Create a task to send the image
                    asyncio.create_task(self.send_selected_image(result))
                else:
                    self.notify("Sélection d'image annulée", severity="information")
            
            # Use push_screen with callback instead of push_screen_wait
            self.push_screen(ImageSelectorModal(), handle_image_result)
            
        except Exception as e:
            self.notify(f"Erreur lors de l'ouverture du sélecteur d'image: {e}", severity="error")
    
    async def send_selected_image(self, image_path: str):
        """Send the selected image with current quality settings - IMPROVED."""
        try:
            # Validate file size
            if os.path.getsize(image_path) > 5 * 1024 * 1024:  # 5MB limit
                self.chat_view.add_message("Système", "Image trop volumineuse (max 5MB)")
                return
            
            # Show quality info immediately
            width, height = app_state.get_image_dimensions()
            self.notify(f"Envoi image (qualité {app_state.image_quality}%, {width}x{height})...", 
                       severity="information")
            
            # Display locally first with placeholder
            self.chat_view.add_message(app_state.username, "[Image en cours d'envoi...]", is_image=True)
            
            # Process image asynchronously with current quality settings
            display_content = await process_image_for_display_async(image_path)
            self.chat_view.update_image_display(display_content)
            
            # Send to peers concurrently (ensure fresh message ID each time)
            await self.broadcast_message_to_peers(image_path=image_path)
            
            # Success notification
            self.notify(f"✅ Image envoyée avec succès!", severity="information")
            
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur d'envoi d'image: {e}")
            self.notify(f"❌ Erreur d'envoi: {e}", severity="error")

    async def action_reset_config(self) -> None:
        """Reset to configuration screen."""
        if self.app_state_ui == "conversation":
            self.chat_view.add_message("Système", "Retour à l'écran de configuration...")
            await self.reset_to_connection_setup("Configuration reset requested")
        else:
            await self.reset_to_connection_setup()

    async def reset_to_connection_setup(self, message=None):
        """Reset the application for new connection setup."""
        # Reset state
        app_state.hello_done.clear()
        app_state.peers.clear()
        app_state.dh_exchanges.clear()
        app_state.message_ids.clear()
        app_state.in_waiting_mode = False
        
        # Return to setup mode selection
        config_container = Container(classes="configuration-container")
        config_container.border_title = "Configuration"
        self.welcome_container.query("*").remove()
        self.welcome_container.mount(config_container)
        
        if self.app_state_ui == "conversation":
            self.welcome_container.styles.display = "block"
            self.chat_view.styles.display = "none"
            self.query_one("#chat-pad").styles.display = "none"
            self.query_one("#status-bar").styles.display = "none"
        
        self.app_state_ui = "setup_mode"
        self.input_label = "Vous connecter (o) ou attendre (n)? "
        self.query_one("#user-input").placeholder = "o/n"
        
        config_message = Static(
            f"Nom d'utilisateur: {app_state.username}\n"
            f"Port: {app_state.port}\n"
            f"Adresse IP: {app_state.local_ip}\n\n"
            f"Mode mesh: Connectez-vous à un peer ou attendez des connexions", 
            classes="content-text"
        )
        config_container.mount(config_message)
        
        if message:
            config_container.mount(Static(message, classes="error-message"))
            self.notify(message, severity="error", timeout=5)

    async def action_quit(self):
        """Clean shutdown of the application."""
        # Close all peer connections
        for peer in app_state.peers.values():
            if peer.websocket:
                try:
                    await peer.websocket.close()
                except:
                    pass
        
        # Close server
        if app_state.websocket_server:
            app_state.websocket_server.close()
            await app_state.websocket_server.wait_closed()
        
        self.exit()

    async def on_key(self, event) -> None:
        """Debug: Check if F5 is being captured and handle it directly."""
        if str(event.key) == "f5":
            self.notify("Raw F5 key detected!", severity="information")
            # Directly call the action as fallback
            await self.action_select_image()
        # Don't call super() since App doesn't have on_key method

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "image-btn":
            # Alternative way to open image selector
            await self.action_select_image()

# Point d'entrée principal
if __name__ == "__main__":
    # Lancer l'application Textual
    app = EncodHexApp()
    app.run()
