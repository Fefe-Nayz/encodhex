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
import hashlib
import mimetypes
import shutil
from datetime import datetime
import threading
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from dataclasses import dataclass, field
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Label, Static, Button, DirectoryTree, DataTable
from textual.reactive import reactive
from textual.screen import ModalScreen
from rich.text import Text
from rich.panel import Panel
from textual.binding import Binding
from textual.message import Message
from PIL import Image, ImageOps
from rich_pixels import Pixels
# from textual_slider import Slider  # Not available, use regular Input instead
from aes.encryption import encrypt, decrypt
from diffie_hellman.diffie_hellman import (
    generate_parameters,
    generate_private_key,
    generate_public_key,
    compute_shared_key,
)

# ──────────────────────────── Data Classes ────────────────────────────
@dataclass
class Contact:
    """Represents a saved contact."""
    name: str
    ip: str
    port: int
    last_connected: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "last_connected": self.last_connected,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Contact":
        return cls(**data)

@dataclass
class Group:
    """Represents a group chat with multiple contacts."""
    name: str
    contacts: List[str]  # Contact names
    created: str
    description: str = ""
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "contacts": self.contacts,
            "created": self.created,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Group":
        return cls(**data)

@dataclass
class FileMessage:
    """Represents a file message for conversation storage."""
    sender: str
    filename: str
    file_size: int
    file_type: str
    file_hash: str
    timestamp: str
    download_available: bool = True
    
    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "filename": self.filename,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "file_hash": self.file_hash,
            "timestamp": self.timestamp,
            "download_available": self.download_available
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FileMessage":
        return cls(**data)

@dataclass
class ConversationMessage:
    """Represents a message in conversation history."""
    sender: str
    content: str
    timestamp: str
    message_type: str = "text"  # text, file, system
    file_info: Optional[FileMessage] = None
    
    def to_dict(self) -> dict:
        result = {
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_type": self.message_type
        }
        if self.file_info:
            result["file_info"] = self.file_info.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConversationMessage":
        file_info = None
        if "file_info" in data and data["file_info"]:
            file_info = FileMessage.from_dict(data["file_info"])
        return cls(
            sender=data["sender"],
            content=data["content"],
            timestamp=data["timestamp"],
            message_type=data.get("message_type", "text"),
            file_info=file_info
        )

@dataclass
class PeerConnection:
    """Represents a connection to a peer."""
    ip: str
    port: int
    shared_key: Optional[str] = None
    public_key: Optional[int] = None
    encryption_ready: bool = False
    websocket: Optional[Any] = None
    connection_established: bool = False
    contact_name: Optional[str] = None  # Associated contact name

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
    websocket_server: Optional[Any] = None
    
    # File sharing settings
    max_file_size: int = 50 * 1024 * 1024  # 50MB default
    downloads_folder: str = "downloads"
    temp_folder: str = "temp"
    
    # Image quality settings (for preview only now)
    image_quality: int = 80
    max_image_width: int = 120  # Reduced since it's just preview
    max_image_height: int = 60  # Reduced since it's just preview
    
    # Mesh networking
    peers: Dict[str, PeerConnection] = field(default_factory=dict)
    dh_exchanges: Dict[str, DHExchange] = field(default_factory=dict)
    message_ids: Set[str] = field(default_factory=set)
    
    # Connection state
    hello_done: Set[str] = field(default_factory=set)
    
    # Contact and conversation management
    contacts: Dict[str, Contact] = field(default_factory=dict)
    groups: Dict[str, Group] = field(default_factory=dict)
    current_conversation: List[ConversationMessage] = field(default_factory=list)
    current_group: Optional[str] = None
    
    def __post_init__(self):
        """Initialize folders and load data."""
        self.ensure_folders()
        self.load_contacts()
        self.load_groups()
    
    def ensure_folders(self):
        """Create necessary folders."""
        os.makedirs(self.downloads_folder, exist_ok=True)
        os.makedirs(self.temp_folder, exist_ok=True)
        os.makedirs("data", exist_ok=True)
        os.makedirs("conversations", exist_ok=True)
    
    def get_image_dimensions(self) -> Tuple[int, int]:
        """Get image dimensions for preview (smaller now)."""
        quality_factor = self.image_quality / 100.0
        width = int(self.max_image_width * quality_factor)
        height = int(self.max_image_height * quality_factor)
        return max(40, width), max(20, height)
    
    def get_peer_key(self, ip: str, port: int) -> str:
        """Generate a unique key for a peer."""
        return f"{ip}:{port}"
    
    def add_peer(self, ip: str, port: int, websocket: Optional[Any] = None) -> PeerConnection:
        """Add a new peer connection."""
        key = self.get_peer_key(ip, port)
        
        # Check if this peer matches a known contact
        contact_name = None
        for name, contact in self.contacts.items():
            if contact.ip == ip and contact.port == port:
                contact_name = name
                contact.last_connected = datetime.now().isoformat()
                break
        
        peer = PeerConnection(ip=ip, port=port, websocket=websocket, contact_name=contact_name)
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
    
    # Contact management
    def save_contacts(self):
        """Save contacts to file."""
        try:
            data = {name: contact.to_dict() for name, contact in self.contacts.items()}
            with open("data/contacts.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving contacts: {e}")
    
    def load_contacts(self):
        """Load contacts from file."""
        try:
            if os.path.exists("data/contacts.json"):
                with open("data/contacts.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.contacts = {name: Contact.from_dict(info) for name, info in data.items()}
        except Exception as e:
            print(f"Error loading contacts: {e}")
    
    def add_contact(self, contact: Contact) -> bool:
        """Add a new contact."""
        if contact.name in self.contacts:
            return False
        self.contacts[contact.name] = contact
        self.save_contacts()
        return True
    
    def update_contact(self, name: str, contact: Contact) -> bool:
        """Update an existing contact."""
        if name not in self.contacts:
            return False
        # Remove old contact and add new one (handles name changes)
        del self.contacts[name]
        self.contacts[contact.name] = contact
        self.save_contacts()
        return True
    
    def remove_contact(self, name: str) -> bool:
        """Remove a contact."""
        if name not in self.contacts:
            return False
        del self.contacts[name]
        self.save_contacts()
        return True
    
    # Group management
    def save_groups(self):
        """Save groups to file."""
        try:
            data = {name: group.to_dict() for name, group in self.groups.items()}
            with open("data/groups.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving groups: {e}")
    
    def load_groups(self):
        """Load groups from file."""
        try:
            if os.path.exists("data/groups.json"):
                with open("data/groups.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.groups = {name: Group.from_dict(info) for name, info in data.items()}
        except Exception as e:
            print(f"Error loading groups: {e}")
    
    def add_group(self, group: Group) -> bool:
        """Add a new group."""
        if group.name in self.groups:
            return False
        self.groups[group.name] = group
        self.save_groups()
        return True
    
    # Conversation management
    def save_conversation(self, identifier: str):
        """Save current conversation to file."""
        try:
            filename = f"conversations/{identifier.replace('/', '_').replace(':', '_')}.json"
            data = [msg.to_dict() for msg in self.current_conversation]
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving conversation: {e}")
    
    def load_conversation(self, identifier: str) -> bool:
        """Load conversation from file."""
        try:
            filename = f"conversations/{identifier.replace('/', '_').replace(':', '_')}.json"
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.current_conversation = [ConversationMessage.from_dict(msg) for msg in data]
                return True
        except Exception as e:
            print(f"Error loading conversation: {e}")
        return False
    
    def add_message_to_conversation(self, message: ConversationMessage):
        """Add a message to current conversation."""
        self.current_conversation.append(message)
        # Auto-save every 10 messages or if it's a file
        if len(self.current_conversation) % 10 == 0 or message.message_type == "file":
            if self.current_group:
                self.save_conversation(f"group_{self.current_group}")
            else:
                # Save with peer info if available
                peers = self.get_ready_peers()
                if peers:
                    peer_names = [p.contact_name or f"{p.ip}_{p.port}" for p in peers]
                    identifier = "_".join(sorted(peer_names))
                    self.save_conversation(identifier)

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
    """Generate a unique message ID."""
    import time
    import random
    timestamp = time.time_ns()
    random_part = random.randint(10000, 99999)
    return f"{app_state.username}_{timestamp}_{random_part}"

def get_file_info(file_path: str) -> Tuple[str, int, str, str]:
    """Get file information: name, size, type, hash."""
    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    file_type, _ = mimetypes.guess_type(file_path)
    if not file_type:
        file_type = "application/octet-stream"
    
    # Calculate hash for integrity
    with open(file_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    return filename, file_size, file_type, file_hash

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def is_image_file(filename: str) -> bool:
    """Check if file is an image."""
    return filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg'))

async def process_image_for_display_async(image_path: str) -> Union[Pixels, str]:
    """Convert an image to Rich Pixels for PREVIEW (smaller size)."""
    def _process_image():
        try:
            # Validate file size first
            if os.path.getsize(image_path) > app_state.max_file_size:
                return f"[Image trop volumineuse (max {format_file_size(app_state.max_file_size)})]"
            
            # Get preview dimensions (smaller than before)
            max_width, max_height = app_state.get_image_dimensions()
            
            # Open and process image
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate new size maintaining aspect ratio
                img_width, img_height = img.size
                aspect_ratio = img_width / img_height
                
                if aspect_ratio > max_width / max_height:
                    new_width = max_width
                    new_height = int(new_width / aspect_ratio)
                else:
                    new_height = max_height
                    new_width = int(new_height * aspect_ratio)
                
                new_width = max(30, new_width)
                new_height = max(15, new_height)
                
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                pixels = Pixels.from_image(resized_img)
                return pixels
                
        except Exception as e:
            return f"[Erreur d'affichage: {e}]"
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_image)

# ────────────────────────────── Custom Widgets ──────────────────────────
class ChatInput(Input):
    """Custom Input widget that inherits app bindings for footer display."""
    
    inherit_bindings = True  # Let the footer merge app bindings
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class UniversalDirectoryTree(DirectoryTree):
    """DirectoryTree that shows all files and directories."""
    
    def filter_paths(self, paths):
        """Show all files and directories."""
        return list(paths)  # Show everything

# ────────────────────────────── Modal Screens ──────────────────────────
class FilteredDirectoryTree(DirectoryTree):
    """Enhanced DirectoryTree with search and filter capabilities."""
    
    def __init__(self, path, search_term="", image_filter=False, **kwargs):
        super().__init__(path, **kwargs)
        self.search_term = search_term.lower()
        self.image_filter = image_filter
    
    def filter_paths(self, paths):
        """Filter paths based on search term and image filter."""
        filtered = []
        
        for path in paths:
            # Always show directories for navigation
            if path.is_dir():
                # Apply search filter to directory names
                if not self.search_term or self.search_term in path.name.lower():
                    filtered.append(path)
            else:
                # For files, apply both search and image filters
                include_file = True
                
                # Search filter
                if self.search_term and self.search_term not in path.name.lower():
                    include_file = False
                
                # Image filter
                if self.image_filter and not is_image_file(path.name):
                    include_file = False
                
                if include_file:
                    filtered.append(path)
        
        return filtered
    
    def update_filters(self, search_term="", image_filter=False):
        """Update search and filter settings and refresh the tree."""
        self.search_term = search_term.lower()
        self.image_filter = image_filter
        self.reload()

class FileBrowserModal(ModalScreen[Optional[str]]):
    """Enhanced file browser with search, filtering, and GIF animation."""
    
    CSS = """
    FileBrowserModal {
        align: center middle;
    }
    
    #browser_dialog {
        width: 95%;
        height: 90%;
        max-width: 120;
        max-height: 40;
        border: thick $primary 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #search_container {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    
    #directory_tree {
        width: 65%;
        height: 20;
        border: solid $primary;
    }
    
    #preview_container {
        width: 35%;
        height: 20;
        border: solid $secondary;
        margin-left: 1;
        padding: 1;
    }
    
    #file_info {
        width: 100%;
        height: 3;
        border: solid $secondary;
        margin: 1 0;
        padding: 0 1;
    }
    
    #browser_buttons {
        width: 100%;
        height: auto;
        layout: horizontal;
        content-align: center middle;
        margin: 1 0;
        padding: 0 1;
    }
    
    #main_browser_area {
        width: 100%;
        height: 20;
        layout: horizontal;
    }
    
    .preview_text {
        width: 100%;
        height: 100%;
        overflow-y: auto;
    }
    
    Button {
        min-width: 14;
        height: 3;
        margin-left: 1;
    }
    
    Button:first-child {
        margin-left: 0;
    }
    
    #filter_images_btn, #show_all_btn {
        min-width: 16;
        width: auto;
    }
    """
    
    def __init__(self, title: str = "📁 Sélectionner un fichier"):
        super().__init__()
        self.dialog_title = title
        self.selected_file = None
        self.current_preview = None
        self.gif_frames = []
        self.gif_frame_index = 0
        self.gif_timer = None
    
    def compose(self) -> ComposeResult:
        with Container(id="browser_dialog"):
            yield Label(self.dialog_title, id="browser_title")
            
            # Search and filter controls
            with Horizontal(id="search_container"):
                yield Input(placeholder="🔍 Rechercher...", id="search_input")
                yield Button("🌄 Images", id="filter_images_btn", variant="primary")
                yield Button("📁 Tous", id="show_all_btn", variant="default")
            
            # Main browser area with tree and preview
            with Horizontal(id="main_browser_area"):
                yield FilteredDirectoryTree("./", id="directory_tree")
                
                with Container(id="preview_container"):
                    yield Label("🔍 Aperçu", id="preview_title")
                    yield ScrollableContainer(
                        Static("Sélectionnez un fichier pour voir l'aperçu", id="preview_content"),
                        classes="preview_text"
                    )
            
            yield Static("Aucun fichier sélectionné", id="file_info")
            
            with Horizontal(id="browser_buttons"):
                yield Button("📍 Sélectionner", id="select_file_btn", variant="primary")
                yield Button("✅ Confirmer", id="confirm_file_btn", variant="success")
                yield Button("❌ Annuler", id="cancel_browse_btn", variant="error")
    
    def on_mount(self) -> None:
        self.query_one("#directory_tree").focus()
    
    def on_key(self, event) -> None:
        """Handle key presses in file browser."""
        if event.key == "escape":
            self.dismiss(None)
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search_input":
            search_term = event.input.value
            tree = self.query_one("#directory_tree")
            
            # Get current filter state
            filter_images_btn = self.query_one("#filter_images_btn")
            image_filter = filter_images_btn.variant == "success"
            
            tree.update_filters(search_term, image_filter)
    
    def on_directory_tree_file_selected(self, event) -> None:
        """Handle file/directory selection."""
        try:
            if hasattr(event, 'path') and event.path:
                path = event.path
                if path.is_file():
                    self.update_file_info(str(path))
                    self.update_preview(str(path))
                    self.selected_file = str(path)
                elif path.is_dir():
                    self.query_one("#file_info").update("📁 Dossier sélectionné")
                    self.clear_preview()
                    self.selected_file = None
        except Exception as e:
            self.notify(f"Erreur de sélection: {e}", severity="error")
    
    def update_file_info(self, file_path: str):
        """Update file information display."""
        try:
            filename, file_size, file_type, _ = get_file_info(file_path)
            size_str = format_file_size(file_size)
            
            # Get file icon based on type
            if is_image_file(filename):
                icon = "🖼️"
            elif file_type.startswith("text/"):
                icon = "📄"
            elif file_type.startswith("video/"):
                icon = "🎥"
            elif file_type.startswith("audio/"):
                icon = "🎵"
            else:
                icon = "📎"
            
            info_text = f"{icon} {filename} ({size_str}) - {file_type}"
            self.query_one("#file_info").update(info_text)
            
        except Exception as e:
            self.query_one("#file_info").update(f"❌ Erreur: {e}")
    
    def update_preview(self, file_path: str):
        """Update file preview with support for images and GIFs."""
        preview_content = self.query_one("#preview_content")
        
        try:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # Stop any existing GIF animation
            self.stop_gif_animation()
            
            if is_image_file(filename):
                # Handle image preview
                if filename.lower().endswith('.gif'):
                    self.preview_gif(file_path, preview_content)
                else:
                    self.preview_image(file_path, preview_content)
            elif file_path.endswith(('.txt', '.py', '.md', '.json', '.yaml', '.yml', '.xml', '.html', '.css', '.js')):
                # Text file preview
                self.preview_text_file(file_path, preview_content)
            else:
                # Generic file info
                size_str = format_file_size(file_size)
                preview_content.update(f"📎 {filename}\n📏 Taille: {size_str}\n\n⚠️ Aperçu non disponible pour ce type de fichier")
                
        except Exception as e:
            preview_content.update(f"❌ Erreur d'aperçu: {e}")
    
    def preview_image(self, file_path: str, preview_content):
        """Preview static image."""
        try:
            # Create a smaller preview image
            with Image.open(file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Small preview size for browser
                preview_width, preview_height = 25, 15
                img_width, img_height = img.size
                aspect_ratio = img_width / img_height
                
                if aspect_ratio > preview_width / preview_height:
                    new_width = preview_width
                    new_height = int(new_width / aspect_ratio)
                else:
                    new_height = preview_height
                    new_width = int(new_height * aspect_ratio)
                
                preview_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                pixels = Pixels.from_image(preview_img)
                
                # Add image info
                size_str = format_file_size(os.path.getsize(file_path))
                info_text = f"🖼️ {os.path.basename(file_path)}\n📏 {size_str} - {img_width}x{img_height}\n\n"
                
                preview_content.update(info_text)
                # Note: In a real implementation, we'd need to handle Pixels objects differently
                # For now, show text description
                
        except Exception as e:
            preview_content.update(f"🖼️ Image\n❌ Erreur d'aperçu: {e}")
    
    def preview_gif(self, file_path: str, preview_content):
        """Preview animated GIF with frame cycling."""
        try:
            with Image.open(file_path) as img:
                if not getattr(img, 'is_animated', False):
                    # Not animated, treat as regular image
                    self.preview_image(file_path, preview_content)
                    return
                
                # Extract all frames
                self.gif_frames = []
                frame_count = getattr(img, 'n_frames', 1)
                
                for frame_num in range(min(frame_count, 10)):  # Limit to 10 frames for performance
                    img.seek(frame_num)
                    frame = img.copy()
                    if frame.mode != 'RGB':
                        frame = frame.convert('RGB')
                    
                    # Small preview size
                    preview_width, preview_height = 25, 15
                    img_width, img_height = frame.size
                    aspect_ratio = img_width / img_height
                    
                    if aspect_ratio > preview_width / preview_height:
                        new_width = preview_width
                        new_height = int(new_width / aspect_ratio)
                    else:
                        new_height = preview_height
                        new_width = int(new_height * aspect_ratio)
                    
                    preview_frame = frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    self.gif_frames.append(preview_frame)
                
                # Show info and start animation
                size_str = format_file_size(os.path.getsize(file_path))
                info_text = f"🎬 GIF Animé\n📏 {size_str} - {frame_count} frames\n⏯️ Animation en cours...\n\n"
                preview_content.update(info_text)
                
                # Start frame cycling
                self.gif_frame_index = 0
                self.start_gif_animation(preview_content)
                
        except Exception as e:
            preview_content.update(f"🎬 GIF\n❌ Erreur d'aperçu: {e}")
    
    def start_gif_animation(self, preview_content):
        """Start GIF frame animation."""
        if self.gif_frames:
            self.gif_timer = self.set_interval(0.5, self.animate_gif_frame, preview_content)
    
    def animate_gif_frame(self, preview_content):
        """Animate to next GIF frame."""
        if not self.gif_frames:
            return
        
        current_frame = self.gif_frames[self.gif_frame_index]
        
        # Create ASCII representation of the frame
        ascii_frame = self.image_to_ascii(current_frame)
        
        size_str = format_file_size(os.path.getsize(self.selected_file)) if self.selected_file else "N/A"
        frame_info = f"🎬 GIF Animé (Frame {self.gif_frame_index + 1}/{len(self.gif_frames)})\n📏 {size_str}\n\n"
        
        preview_content.update(frame_info + ascii_frame)
        
        # Move to next frame
        self.gif_frame_index = (self.gif_frame_index + 1) % len(self.gif_frames)
    
    def image_to_ascii(self, img):
        """Convert image to ASCII representation (simple version)."""
        # Simple ASCII conversion for preview
        ascii_chars = "@%#*+=-:. "
        width, height = img.size
        
        # Further reduce size for ASCII
        width = min(width, 40)
        height = min(height, 20)
        img = img.resize((width, height))
        
        pixels = img.getdata()
        ascii_str = ""
        
        for i, pixel in enumerate(pixels):
            if i % width == 0 and i != 0:
                ascii_str += "\n"
            
            # Convert RGB to grayscale
            gray = int(0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2])
            ascii_str += ascii_chars[gray * (len(ascii_chars) - 1) // 255]
        
        return ascii_str
    
    def stop_gif_animation(self):
        """Stop GIF animation timer."""
        if self.gif_timer:
            self.gif_timer.stop()
            self.gif_timer = None
        self.gif_frames = []
        self.gif_frame_index = 0
    
    def preview_text_file(self, file_path: str, preview_content):
        """Preview text file content."""
        try:
            file_size = os.path.getsize(file_path)
            size_str = format_file_size(file_size)
            
            if file_size > 1024 * 50:  # 50KB limit for preview
                preview_content.update(f"📄 Fichier texte\n📏 {size_str}\n\n⚠️ Fichier trop volumineux pour l'aperçu")
                return
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # First 1000 characters
                
            preview_text = f"📄 {os.path.basename(file_path)}\n📏 {size_str}\n\n{content}"
            if len(content) >= 1000:
                preview_text += "\n\n... (tronqué)"
                
            preview_content.update(preview_text)
            
        except Exception as e:
            preview_content.update(f"📄 Fichier texte\n❌ Erreur de lecture: {e}")
    
    def clear_preview(self):
        """Clear the preview area."""
        self.stop_gif_animation()
        preview_content = self.query_one("#preview_content")
        preview_content.update("Sélectionnez un fichier pour voir l'aperçu")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        
        if button_id == "select_file_btn":
            if self.selected_file and os.path.isfile(self.selected_file):
                self.stop_gif_animation()  # Clean up before closing
                # Don't close automatically, let user decide
                self.notify(f"Fichier sélectionné: {os.path.basename(self.selected_file)}", severity="success")
            else:
                self.notify("Veuillez sélectionner un fichier valide", severity="warning")
        elif button_id == "confirm_file_btn":
            if self.selected_file and os.path.isfile(self.selected_file):
                self.stop_gif_animation()
                self.dismiss(self.selected_file)
            else:
                self.notify("Aucun fichier sélectionné", severity="warning")
        elif button_id == "cancel_browse_btn":
            self.stop_gif_animation()  # Clean up before closing
            self.dismiss(None)
        elif button_id == "filter_images_btn":
            # Toggle image filter
            tree = self.query_one("#directory_tree")
            search_input = self.query_one("#search_input")
            
            # Toggle button state
            if event.button.variant == "primary":
                event.button.variant = "success"
                event.button.label = "🌄 Images "
                image_filter = True
            else:
                event.button.variant = "primary"
                event.button.label = "🌄 Images "
                image_filter = False
            
            # Update show all button
            show_all_btn = self.query_one("#show_all_btn")
            show_all_btn.variant = "default" if image_filter else "success"
            
            tree.update_filters(search_input.value, image_filter)
        elif button_id == "show_all_btn":
            # Show all files
            tree = self.query_one("#directory_tree")
            search_input = self.query_one("#search_input")
            
            # Reset buttons
            filter_btn = self.query_one("#filter_images_btn")
            filter_btn.variant = "primary"
            filter_btn.label = "🌄 Images "
            
            event.button.variant = "success"
            
            tree.update_filters(search_input.value, False)

class ContactManagerModal(ModalScreen[None]):
    """Enhanced modal for managing contacts and groups with quick connect."""
    
    CSS = """
    ContactManagerModal {
        align: center middle;
    }
    
    #contact_dialog {
        width: 95%;
        height: 1fr;
        max-width: 120;
        max-height: 50;
        border: thick $primary 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #tabs_container {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    
    #content_area {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        overflow-y: auto;
    }
    
    #form_area {
        width: 100%;
        height: auto;
        border: solid $secondary;
        padding: 1;
        margin: 1 0;
        layout: vertical;
    }
    
    .form_row {
        width: 100%;
        height: 3;
        layout: horizontal;
        margin: 0 0 1 0;
    }
    
    .form_label {
        width: 20%;
        height: 3;
        content-align: center middle;
    }
    
    .form_input {
        width: 80%;
        height: 3;
        margin-left: 1;
    }
    
    #button_area {
        width: 100%;
        height: auto;
        layout: horizontal;
        content-align: center middle;
        padding: 0 1;
    }
    
    .tab_button {
        width: 25%;
        margin: 0 1;
        min-width: 18;
    }
    
    .tab_active {
        background: $primary;
        color: $text;
    }
    
    .quick_connect_item {
        width: 100%;
        height: 3;
        padding: 1;
        margin: 0 0 1 0;
        border: solid $secondary;
        background: $surface;
    }
    
    .quick_connect_item:hover {
        background: $primary 20%;
    }
    
    Button {
        min-width: 14;
        height: 3;
        margin-left: 1;
    }
    
    Button:first-child {
        margin-left: 0;
    }
    
    .tab_button {
        min-width: 18;
        width: auto;
    }
    
    #add_btn, #delete_btn, #confirm_btn {
        min-width: 14;
        width: auto;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.current_tab = "contacts"  # contacts, groups, quick_connect
    
    def compose(self) -> ComposeResult:
        with Container(id="contact_dialog"):
            yield Label("👥 Gestionnaire de Contacts & Groupes", id="contact_title")
            
            # Tab buttons
            with Horizontal(id="tabs_container"):
                yield Button("👤 Contacts", id="tab_contacts", classes="tab_button tab_active")
                yield Button("👥 Groupes", id="tab_groups", classes="tab_button")
                yield Button("⚡ Connexion Rapide", id="tab_quick", classes="tab_button")
            
            # Content area
            yield ScrollableContainer(
                Static("Chargement...", id="main_content"),
                id="content_area"
            )
            
            # Form area (dynamic based on tab)
            with Container(id="form_area"):
                with Horizontal(classes="form_row"):
                    yield Label("Nom:", id="form_label1", classes="form_label")
                    yield Input(placeholder="Nom", id="form_input1", classes="form_input")
                
                with Horizontal(classes="form_row"):
                    yield Label("IP:", id="form_label2", classes="form_label")
                    yield Input(placeholder="192.168.1.100", id="form_input2", classes="form_input")
                
                with Horizontal(classes="form_row"):
                    yield Label("Port:", id="form_label3", classes="form_label")
                    yield Input(placeholder="8765", id="form_input3", classes="form_input")
                
                with Horizontal(classes="form_row"):
                    yield Label("Notes:", id="form_label4", classes="form_label")
                    yield Input(placeholder="Notes", id="form_input4", classes="form_input")
            
            # Buttons
            with Horizontal(id="button_area"):
                yield Button("➕ Ajouter", id="add_btn", variant="success")
                yield Button("🔗 Connecter", id="connect_btn", variant="primary")
                yield Button("🚮 Supprimer", id="delete_btn", variant="error")
                yield Button("✅ Confirmer", id="confirm_btn", variant="success")
                yield Button("❌ Fermer", id="close_btn", variant="default")
    
    def on_mount(self) -> None:
        self.switch_tab("contacts")
    
    def on_key(self, event) -> None:
        """Handle key presses in contact manager."""
        if event.key == "escape":
            self.dismiss()
    
    def switch_tab(self, tab_name: str):
        """Switch to a different tab."""
        self.current_tab = tab_name
        
        # Update tab button styles
        for tab in ["contacts", "groups", "quick"]:
            button = self.query_one(f"#tab_{tab}")
            if tab == tab_name:
                button.add_class("tab_active")
            else:
                button.remove_class("tab_active")
        
        # Update content and form
        if tab_name == "contacts":
            self.show_contacts_tab()
        elif tab_name == "groups":
            self.show_groups_tab()
        elif tab_name == "quick":
            self.show_quick_connect_tab()
    
    def show_contacts_tab(self):
        """Show contacts management."""
        content = self.query_one("#main_content")
        
        # Update form labels
        self.query_one("#form_label1").update("Nom:")
        self.query_one("#form_label2").update("IP:")
        self.query_one("#form_label3").update("Port:")
        self.query_one("#form_label4").update("Notes:")
        
        # Update placeholders
        self.query_one("#form_input1").placeholder = "Nom du contact"
        self.query_one("#form_input2").placeholder = "192.168.1.100"
        self.query_one("#form_input3").placeholder = "8765"
        self.query_one("#form_input4").placeholder = "Notes optionnelles"
        
        if not app_state.contacts:
            content.update("📋 Aucun contact enregistré.\n\nUtilisez le formulaire ci-dessous pour ajouter un contact.")
            return
        
        contact_text = "📋 Contacts enregistrés:\n\n"
        for name, contact in app_state.contacts.items():
            last_connected = contact.last_connected or "Jamais"
            if contact.last_connected:
                try:
                    dt = datetime.fromisoformat(contact.last_connected)
                    last_connected = dt.strftime("%d/%m/%Y %H:%M")
                except:
                    pass
            
            contact_text += f"🟢 {name}\n"
            contact_text += f"   📍 {contact.ip}:{contact.port}\n"
            contact_text += f"   🕒 Dernière connexion: {last_connected}\n"
            if contact.notes:
                contact_text += f"   📝 {contact.notes}\n"
            contact_text += "\n"
        
        content.update(contact_text)
    
    def show_groups_tab(self):
        """Show groups management."""
        content = self.query_one("#main_content")
        
        # Update form labels for groups
        self.query_one("#form_label1").update("Nom Groupe:")
        self.query_one("#form_label2").update("Contacts:")
        self.query_one("#form_label3").update("Description:")
        self.query_one("#form_label4").update("")
        
        # Update placeholders
        self.query_one("#form_input1").placeholder = "Nom du groupe"
        self.query_one("#form_input2").placeholder = "Contact1,Contact2,Contact3"
        self.query_one("#form_input3").placeholder = "Description du groupe"
        self.query_one("#form_input4").placeholder = ""
        
        if not app_state.groups:
            content.update("👥 Aucun groupe créé.\n\nCréez des groupes pour connecter plusieurs contacts en une fois.")
            return
        
        group_text = "👥 Groupes créés:\n\n"
        for name, group in app_state.groups.items():
            group_text += f"🔷 {name}\n"
            group_text += f"   👤 Contacts: {', '.join(group.contacts)}\n"
            group_text += f"   📅 Créé: {group.created}\n"
            if group.description:
                group_text += f"   📝 {group.description}\n"
            group_text += "\n"
        
        content.update(group_text)
    
    def show_quick_connect_tab(self):
        """Show quick connect options."""
        content = self.query_one("#main_content")
        
        # Show form for quick connect (for name input)
        self.query_one("#form_area").styles.display = "block"
        
        # Update form labels for quick connect
        self.query_one("#form_label1").update("Nom à connecter:")
        self.query_one("#form_label2").update("")
        self.query_one("#form_label3").update("")
        self.query_one("#form_label4").update("")
        
        # Update placeholders
        self.query_one("#form_input1").placeholder = "Nom du contact ou groupe"
        self.query_one("#form_input2").placeholder = ""
        self.query_one("#form_input3").placeholder = ""
        self.query_one("#form_input4").placeholder = ""
        
        if not app_state.contacts and not app_state.groups:
            content.update("⚡ Connexion Rapide\n\nAucun contact ou groupe disponible.\nAjoutez des contacts d'abord.")
            return
        
        quick_text = "⚡ Connexion Rapide - Entrez le nom dans le champ ci-dessous:\n\n"
        
        # Add individual contacts
        if app_state.contacts:
            quick_text += "👤 CONTACTS DISPONIBLES:\n"
            for name, contact in app_state.contacts.items():
                status = "🟢" if contact.last_connected else "⚪"
                quick_text += f"  {status} {name} ({contact.ip}:{contact.port})\n"
            quick_text += "\n"
        
        # Add groups
        if app_state.groups:
            quick_text += "👥 GROUPES DISPONIBLES:\n"
            for name, group in app_state.groups.items():
                available_contacts = sum(1 for c in group.contacts if c in app_state.contacts)
                quick_text += f"  🔷 {name} ({available_contacts}/{len(group.contacts)} contacts disponibles)\n"
                quick_text += f"     └─ Contacts: {', '.join(group.contacts)}\n"
            quick_text += "\n"
        
        quick_text += "💡 Entrez le nom d'un contact ou groupe ci-dessous et cliquez 'Connecter'."
        content.update(quick_text)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        
        # Tab switching
        if button_id == "tab_contacts":
            self.switch_tab("contacts")
        elif button_id == "tab_groups":
            self.switch_tab("groups")
        elif button_id == "tab_quick":
            self.switch_tab("quick")
        
        # Action buttons based on current tab
        elif button_id == "add_btn":
            if self.current_tab == "contacts":
                self.add_contact()
            elif self.current_tab == "groups":
                self.add_group()
        elif button_id == "delete_btn":
            if self.current_tab == "contacts":
                self.delete_contact()
            elif self.current_tab == "groups":
                self.delete_group()
        elif button_id == "connect_btn":
            if self.current_tab == "contacts":
                self.connect_to_contact()
            elif self.current_tab == "groups":
                self.connect_to_group()
            elif self.current_tab == "quick":
                self.quick_connect()
        elif button_id == "confirm_btn":
            self.confirm_action()
        elif button_id == "close_btn":
            self.dismiss()
    
    def add_contact(self):
        """Add a new contact."""
        name = self.query_one("#form_input1").value.strip()
        ip = self.query_one("#form_input2").value.strip()
        port_str = self.query_one("#form_input3").value.strip()
        notes = self.query_one("#form_input4").value.strip()
        
        if not all([name, ip, port_str]):
            self.notify("Nom, IP et port sont requis", severity="error")
            return
        
        if not is_valid_ip(ip):
            self.notify("Adresse IP invalide", severity="error")
            return
        
        if not is_valid_port(port_str):
            self.notify("Port invalide", severity="error")
            return
        
        contact = Contact(
            name=name,
            ip=ip,
            port=int(port_str),
            notes=notes
        )
        
        if app_state.add_contact(contact):
            self.notify(f"Contact '{name}' ajouté", severity="success")
            self.clear_form()
            self.show_contacts_tab()
        else:
            self.notify(f"Contact '{name}' existe déjà", severity="error")
    
    def add_group(self):
        """Add a new group."""
        name = self.query_one("#form_input1").value.strip()
        contacts_str = self.query_one("#form_input2").value.strip()
        description = self.query_one("#form_input3").value.strip()
        
        if not all([name, contacts_str]):
            self.notify("Nom et contacts sont requis", severity="error")
            return
        
        # Parse contacts
        contact_names = [c.strip() for c in contacts_str.split(",") if c.strip()]
        
        # Validate that contacts exist
        missing_contacts = [c for c in contact_names if c not in app_state.contacts]
        if missing_contacts:
            self.notify(f"Contacts non trouvés: {', '.join(missing_contacts)}", severity="error")
            return
        
        group = Group(
            name=name,
            contacts=contact_names,
            created=datetime.now().isoformat(),
            description=description
        )
        
        if app_state.add_group(group):
            self.notify(f"Groupe '{name}' créé", severity="success")
            self.clear_form()
            self.show_groups_tab()
        else:
            self.notify(f"Groupe '{name}' existe déjà", severity="error")
    
    def delete_contact(self):
        """Delete a contact by name."""
        name = self.query_one("#form_input1").value.strip()
        if not name:
            self.notify("Entrez le nom du contact à supprimer", severity="warning")
            return
        
        if name not in app_state.contacts:
            self.notify(f"Contact '{name}' non trouvé", severity="error")
            return
        
        if app_state.remove_contact(name):
            self.notify(f"Contact '{name}' supprimé", severity="success")
            self.clear_form()
            self.show_contacts_tab()
        else:
            self.notify("Erreur lors de la suppression", severity="error")
    
    def delete_group(self):
        """Delete a group by name."""
        name = self.query_one("#form_input1").value.strip()
        if not name:
            self.notify("Entrez le nom du groupe à supprimer", severity="warning")
            return
        
        if name not in app_state.groups:
            self.notify(f"Groupe '{name}' non trouvé", severity="error")
            return
        
        del app_state.groups[name]
        app_state.save_groups()
        self.notify(f"Groupe '{name}' supprimé", severity="success")
        self.clear_form()
        self.show_groups_tab()
    
    def connect_to_contact(self):
        """Connect to a contact by name."""
        name = self.query_one("#form_input1").value.strip()
        if not name:
            self.notify("Entrez le nom du contact pour se connecter", severity="warning")
            return
        
        contact = app_state.contacts.get(name)
        if not contact:
            self.notify(f"Contact '{name}' non trouvé", severity="error")
            return
        
        # Trigger connection in main app
        self.app.connect_to_contact(contact)
        self.notify(f"Connexion à {name} en cours...", severity="information")
        self.dismiss()
    
    def connect_to_group(self):
        """Connect to all contacts in a group."""
        name = self.query_one("#form_input1").value.strip()
        if not name:
            self.notify("Entrez le nom du groupe pour se connecter", severity="warning")
            return
        
        group = app_state.groups.get(name)
        if not group:
            self.notify(f"Groupe '{name}' non trouvé", severity="error")
            return
        
        # Connect to all contacts in the group
        connected_count = 0
        for contact_name in group.contacts:
            contact = app_state.contacts.get(contact_name)
            if contact:
                self.app.connect_to_contact(contact)
                connected_count += 1
        
        self.notify(f"Connexion à {connected_count} contacts du groupe '{name}'...", severity="information")
        self.dismiss()
    
    def quick_connect(self):
        """Quick connect based on user selection."""
        name = self.query_one("#form_input1").value.strip()
        if not name:
            self.notify("Entrez le nom d'un contact ou groupe", severity="warning")
            return
        
        # Try to connect as contact first
        if name in app_state.contacts:
            contact = app_state.contacts[name]
            self.app.connect_to_contact(contact)
            self.notify(f"Connexion au contact '{name}' en cours...", severity="information")
            self.dismiss()
            return
        
        # Try to connect as group
        if name in app_state.groups:
            group = app_state.groups[name]
            connected_count = 0
            for contact_name in group.contacts:
                contact = app_state.contacts.get(contact_name)
                if contact:
                    self.app.connect_to_contact(contact)
                    connected_count += 1
            
            self.notify(f"Connexion à {connected_count} contacts du groupe '{name}'...", severity="information")
            self.dismiss()
            return
        
        # Not found
        self.notify(f"Contact ou groupe '{name}' non trouvé", severity="error")
    
    def confirm_action(self):
        """Confirm current action."""
        if self.current_tab == "quick":
            self.quick_connect()
        else:
            self.notify("Action confirmée", severity="information")
    
    def clear_form(self):
        """Clear the form fields."""
        self.query_one("#form_input1").value = ""
        self.query_one("#form_input2").value = ""
        self.query_one("#form_input3").value = ""
        self.query_one("#form_input4").value = ""

class FileShareModal(ModalScreen[Optional[str]]):
    """Modal for sharing files with preview and size info."""
    
    CSS = """
    FileShareModal {
        align: center middle;
    }
    
    #file_dialog {
        width: 90%;
        height: 80%;
        max-width: 100;
        max-height: 30;
        border: thick $primary 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #file_path_input {
        width: 100%;
        margin: 1 0;
    }
    
    #file_preview {
        width: 100%;
        height: 12;
        border: solid $secondary;
        margin: 1 0;
        padding: 1;
    }
    
    #size_warning {
        width: 100%;
        height: 2;
        margin: 1 0;
    }
    
    #button_container {
        width: 100%;
        height: 4;
        align: center middle;
        margin: 1 0;
        padding: 0 1;
    }
    
    Button {
        margin: 0 1;
        min-width: 12;
        height: 3;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container(id="file_dialog"):
            yield Label("📎 Partage de fichier", id="title")
            yield Input(
                placeholder="Chemin du fichier ou glissez-déposez...",
                id="file_path_input"
            )
            
            yield ScrollableContainer(
                Static("Sélectionnez un fichier pour voir l'aperçu", id="preview_content"),
                id="file_preview"
            )
            
            yield Static("", id="size_warning")
            
            with Horizontal(id="button_container"):
                yield Button("📁 Parcourir", id="browse_btn", variant="primary")
                yield Button("📤 Envoyer", id="send_btn", variant="success")
                yield Button("❌ Annuler", id="cancel_btn", variant="error")
    
    def on_mount(self) -> None:
        self.query_one("#file_path_input").focus()
    
    def on_key(self, event) -> None:
        """Handle key presses in file share modal."""
        if event.key == "escape":
            self.dismiss(None)
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Update preview when path changes."""
        if event.input.id == "file_path_input":
            self.update_preview(event.input.value.strip())
    
    def update_preview(self, file_path: str):
        """Update file preview and warnings."""
        preview_content = self.query_one("#preview_content")
        size_warning = self.query_one("#size_warning")
        
        if not file_path or not os.path.exists(file_path):
            preview_content.update("❌ Fichier non trouvé")
            size_warning.update("")
            return
        
        if not os.path.isfile(file_path):
            preview_content.update("📁 Veuillez sélectionner un fichier (pas un dossier)")
            size_warning.update("")
            return
        
        try:
            filename, file_size, file_type, file_hash = get_file_info(file_path)
            size_str = format_file_size(file_size)
            
            # Create preview
            preview_lines = [
                f"📎 **Fichier**: {filename}",
                f"📏 **Taille**: {size_str}",
                f"🏷️ **Type**: {file_type}",
                f"🔐 **Hash**: {file_hash[:16]}...",
                ""
            ]
            
            # Add type-specific preview
            if is_image_file(filename):
                preview_lines.append("🖼️ **Type**: Image - Aperçu sera affiché dans le chat")
            elif file_type.startswith("text/") and file_size < 1024 * 10:  # Small text files
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(500)  # First 500 chars
                        preview_lines.extend([
                            "📄 **Aperçu du texte**:",
                            content[:200] + ("..." if len(content) > 200 else "")
                        ])
                except:
                    preview_lines.append("📄 **Fichier texte** (aperçu non disponible)")
            else:
                preview_lines.append(f"📎 **Fichier binaire** - Sera envoyé tel quel")
            
            preview_content.update("\n".join(preview_lines))
            
            # Size warning
            if file_size > app_state.max_file_size:
                size_warning.update(
                    f"⚠️ ATTENTION: Fichier trop volumineux! "
                    f"Max: {format_file_size(app_state.max_file_size)}"
                )
                size_warning.styles.color = "red"
            elif file_size > app_state.max_file_size * 0.8:  # 80% of max
                size_warning.update("⚠️ Fichier volumineux - L'envoi peut prendre du temps")
                size_warning.styles.color = "yellow"
            else:
                size_warning.update("✅ Taille acceptable")
                size_warning.styles.color = "green"
                
        except Exception as e:
            preview_content.update(f"❌ Erreur: {e}")
            size_warning.update("")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        
        if button_id == "send_btn":
            path = self.query_one("#file_path_input").value.strip()
            if path and os.path.isfile(path):
                file_size = os.path.getsize(path)
                if file_size <= app_state.max_file_size:
                    self.dismiss(path)
                else:
                    self.notify("Fichier trop volumineux!", severity="error")
            else:
                self.notify("Fichier non trouvé!", severity="error")
        elif button_id == "browse_btn":
            def handle_file_selection(file_path):
                if file_path:
                    self.query_one("#file_path_input").value = file_path
                    self.update_preview(file_path)
            
            self.app.push_screen(FileBrowserModal("📎 Sélectionner un fichier à partager"), handle_file_selection)
        elif button_id == "cancel_btn":
            self.dismiss(None)

class DownloadManagerModal(ModalScreen[None]):
    """Modal for managing file downloads."""
    
    CSS = """
    DownloadManagerModal {
        align: center middle;
    }
    
    #download_dialog {
        width: 90%;
        height: 80%;
        max-width: 100;
        max-height: 30;
        border: thick $primary 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #download_list {
        width: 100%;
        height: 18;
        border: solid $primary;
        overflow-y: auto;
    }
    
    #download_buttons {
        width: 100%;
        height: auto;
        layout: horizontal;
        content-align: center middle;
        margin: 1 0;
        padding: 0 1;
    }
    
    Button {
        min-width: 14;
        height: 3;
        margin-left: 1;
    }
    
    Button:first-child {
        margin-left: 0;
    }
    
    #open_folder_btn {
        min-width: 18;
        width: auto;
    }
    """
    
    def compose(self) -> ComposeResult:
        with Container(id="download_dialog"):
            yield Label("📥 Gestionnaire de téléchargements", id="download_title")
            
            yield ScrollableContainer(
                Static("Chargement des téléchargements...", id="download_content"),
                id="download_list"
            )
            
            with Horizontal(id="download_buttons"):
                yield Button("📂 Ouvrir dossier", id="open_folder_btn", variant="primary")
                yield Button("❌ Fermer", id="close_btn", variant="default")
    
    def on_mount(self) -> None:
        self.refresh_downloads()
    
    def on_key(self, event) -> None:
        """Handle key presses in download manager."""
        if event.key == "escape":
            self.dismiss()
    
    def refresh_downloads(self):
        """Refresh the downloads list."""
        content = self.query_one("#download_content")
        
        # Find files in conversation
        files = []
        for msg in app_state.current_conversation:
            if msg.message_type == "file" and msg.file_info:
                files.append((msg, msg.file_info))
        
        if not files:
            content.update("📭 Aucun fichier disponible en téléchargement.\n\nLes fichiers partagés dans la conversation apparaîtront ici.")
            return
        
        download_text = "📥 Fichiers disponibles:\n\n"
        for i, (msg, file_info) in enumerate(files):
            status = "✅ Disponible" if file_info.download_available else "❌ Expiré"
            download_text += f"📎 {file_info.filename}\n"
            download_text += f"   👤 Expéditeur: {msg.sender}\n"
            download_text += f"   📏 Taille: {format_file_size(file_info.file_size)}\n"
            download_text += f"   🗂️ Type: {file_info.file_type.split('/')[0].title()}\n"
            try:
                download_text += f"   🕒 Date: {datetime.fromisoformat(msg.timestamp).strftime('%d/%m %H:%M')}\n"
            except:
                download_text += f"   🕒 Date: {msg.timestamp}\n"
            download_text += f"   📊 Statut: {status}\n"
            download_text += "\n"
        
        content.update(download_text)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        
        if button_id == "open_folder_btn":
            self.open_downloads_folder()
        elif button_id == "close_btn":
            self.dismiss()
    
    def open_downloads_folder(self):
        """Open the downloads folder."""
        try:
            import subprocess
            import platform
            
            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", app_state.downloads_folder])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", app_state.downloads_folder])
            else:  # Linux
                subprocess.run(["xdg-open", app_state.downloads_folder])
                
            self.notify("Dossier de téléchargements ouvert", severity="success")
        except Exception as e:
            self.notify(f"Impossible d'ouvrir le dossier: {e}", severity="error")

# ────────────────────────────── widgets ──────────────────────────────
class ChatView(ScrollableContainer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def add_message(self, sender, message, timestamp=None, message_type="text", file_info=None, is_image=False):
        """Add a message to the chat view."""
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M:%S")

        # Create message header
        if sender == app_state.username:
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold green")
        elif sender == "Système":
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold blue")
        else:
            msg = Text(f"[{timestamp}] ", style="bold cyan")
            msg.append(f"{sender}: ", style="bold yellow")

        # Handle legacy is_image parameter
        if is_image and message_type == "text":
            message_type = "image"
        
        # Add message content based on type
        if message_type == "file":
            if file_info:
                size_str = format_file_size(file_info.file_size)
                if is_image_file(file_info.filename):
                    icon = "🖼️"
                elif file_info.file_type.startswith("text/"):
                    icon = "📄"
                elif file_info.file_type.startswith("video/"):
                    icon = "🎥"
                elif file_info.file_type.startswith("audio/"):
                    icon = "🎵"
                else:
                    icon = "📎"
                
                msg.append(f"{icon} {file_info.filename} ({size_str})", style="bold")
                if sender != app_state.username:
                    msg.append(" - Cliquez pour télécharger", style="italic blue")
            else:
                msg.append("[Fichier partagé]", style="italic")
        elif message_type == "image":
            msg.append("[Image]", style="italic magenta")
        else:
            msg.append(message)

        self.messages.append(msg)
        
        # Add conversation record
        if sender != "Système":
            conv_msg = ConversationMessage(
                sender=sender,
                content=message,
                timestamp=timestamp,
                message_type=message_type,
                file_info=file_info
            )
            app_state.add_message_to_conversation(conv_msg)
        
        # Add placeholder for file/image content
        if message_type in ["file", "image"] and sender != "Système":
            if message_type == "image":
                if sender == app_state.username:
                    placeholder = Text("[Génération de l'aperçu...]", style="dim")
                else:
                    placeholder = Text("[Traitement de l'image reçue...]", style="dim")
            else:  # file
                if sender == app_state.username:
                    placeholder = Text("[Fichier envoyé]", style="dim green")
                else:
                    placeholder = Text("[Utilisez Ctrl+D pour gérer les téléchargements]", style="dim blue")
            
            self.messages.append(placeholder)
        
        self.update_messages()
        self.scroll_end()

    def update_image_display(self, display_content: Union[Pixels, str]):
        """Update the last image message with processed content."""
        if self.messages and len(self.messages) >= 2:
            if isinstance(display_content, Pixels):
                self.messages[-1] = display_content
            else:
                self.messages[-1] = Text(str(display_content), style="red")
            
            self.update_messages()
            self.scroll_end()

    def update_file_display(self, file_info: FileMessage, download_link: bool = True):
        """Update file message with download info."""
        if self.messages and len(self.messages) >= 2:
            size_str = format_file_size(file_info.file_size)
            
            if download_link:
                content = Text(f"📥 Téléchargeable: {file_info.filename} ({size_str})\n", style="green")
                content.append("Ctrl+D pour ouvrir le gestionnaire de téléchargements", style="dim")
            else:
                content = Text(f"📎 Fichier local: {file_info.filename} ({size_str})", style="blue")
            
            self.messages[-1] = content
            self.update_messages()
            self.scroll_end()

    def load_conversation_history(self):
        """Load and display conversation history."""
        self.messages = []
        
        for conv_msg in app_state.current_conversation:
            # Add the basic message
            self.add_message(
                conv_msg.sender,
                conv_msg.content,
                conv_msg.timestamp,
                conv_msg.message_type,
                conv_msg.file_info
            )
            
            # For files, add download info
            if conv_msg.message_type == "file" and conv_msg.file_info:
                if conv_msg.sender != app_state.username:
                    self.update_file_display(conv_msg.file_info, download_link=True)
                else:
                    self.update_file_display(conv_msg.file_info, download_link=False)
            
            # For images, add preview if available
            elif conv_msg.message_type == "image":
                # Could load cached preview here
                pass

    def update_messages(self):
        self.query("*").remove()
        for msg in self.messages:
            if isinstance(msg, Pixels):
                    self.mount(Static(msg))
            else:
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

    #file-btn {
        width: 4;
        height: 3;
        margin-left: 1;
        min-width: 4;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quitter", show=True),
        Binding("ctrl+q", "quit", "Quitter", show=True),
        Binding("ctrl+r", "step_back_or_reset", "← Retour/Config", show=True),
        Binding("f5", "select_file", "📎 Fichier", show=True),
        Binding("ctrl+k", "manage_contacts", "👥 Contacts", show=True),
        Binding("ctrl+d", "manage_downloads", "📥 Téléchargements", show=True),
        Binding("ctrl+h", "load_conversation", "📜 Historique", show=True),
    ]

    app_state_ui = reactive("welcome", bindings=True)
    status_text = reactive("")
    input_label = reactive("> ")

    def __init__(self):
        super().__init__()
        self.chat_view = ChatView(id="chat-view")
        self.welcome_container = Container(id="welcome-message")
        self._visible_bindings = []
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
        
        # Update bindings visibility based on state
        self.update_binding_visibility()
    
    def update_binding_visibility(self):
        """Update which bindings are visible based on current state."""
        # Bindings are now controlled by check_action() and reactive(bindings=True)
        # Just update file button visibility
        try:
            self._update_file_button_visibility()
        except Exception:
            # Button not available yet
            pass
    
    def _update_file_button_visibility(self):
        """Show/hide file button based on current state."""
        try:
            file_button = self.query_one("#file-btn")
            if self.app_state_ui == "conversation":
                file_button.styles.display = "block"
            else:
                file_button.styles.display = "none"
        except Exception:
            # Button not available yet
            pass
    
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Control binding visibility based on current state."""
        # Masquer (=False) quand l'action n'a pas de sens dans l'écran courant
        if action in {"select_file", "manage_downloads", "load_conversation"}:
            return self.app_state_ui == "conversation"
        if action == "manage_contacts":
            return self.app_state_ui.startswith("setup_") or self.app_state_ui == "conversation"
        if action == "step_back_or_reset":
            return self.app_state_ui.startswith("setup_") or self.app_state_ui == "conversation"
        return True  # visible partout ailleurs (notamment quit)

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
            yield ChatInput(placeholder="Appuyez sur Entrée pour continuer...", id="user-input")

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
            "Version 3.0 - File Sharing & Contact Management Edition\n"
            "Développé par Nino Belaoud & Ferréol DUBOIS COLI\n\n"
            "🆕 Nouvelles fonctionnalités v3.0:\n"
            "• Partage de fichiers universels (F5)\n"
            "• Gestionnaire de contacts (Ctrl+K)\n"
            "• Téléchargements managés (Ctrl+D)\n"
            "• Sauvegarde des conversations (Ctrl+H)\n"
            "• Chats de groupe persistants\n\n"
            "Fonctionnalités:\n"
            "• Aperçu d'images en couleur\n"
            "• Chiffrement AES-256 bout-à-bout\n"
            "• Réseau mesh auto-découverte\n"
            "• Historique des conversations\n\n"
            "Appuyez sur Entrée pour commencer"
        )

        welcome_box = Container(classes="conversation-welcome")
        welcome_box.border_title = "EncodHex Mesh v3.0 - File Sharing Edition"
        self.welcome_container.mount(welcome_box)
        welcome_box.mount(Static(welcome_text, classes="content-text"))

        self.welcome_container.styles.content_align_horizontal = "center"
        self.welcome_container.styles.content_align_vertical = "middle"

        self.app_state_ui = "welcome"
        self.input_label = "> "
        
        # Reset input placeholder
        try:
            input_field = self.query_one("#user-input")
            input_field.placeholder = "Appuyez sur Entrée pour continuer..."
        except Exception:
            pass
            
        self.update_binding_visibility()

    def show_conversation(self):
        self.welcome_container.styles.display = "none"
        self.query_one("#chat-pad").styles.display = "block"
        self.chat_view.styles.display = "block"

        status_bar = self.query_one("#status-bar")
        status_bar.styles.display = "block"
        
        # Update input placeholder for conversation mode
        try:
            input_field = self.query_one("#user-input")
            input_field.placeholder = "Tapez votre message ou F5 pour fichiers..."
            
            # Add file button if not already present
            input_container = self.query_one("#input-container")
            existing_button = input_container.query("#file-btn")
            if not existing_button:
                file_button = Button("📎", id="file-btn", variant="primary")
                input_container.mount(file_button)
        except Exception as e:
            self.notify(f"Erreur lors de la mise à jour de l'interface: {e}", severity="error")

        self.chat_view.border_title = "Chat Mesh"

        self.app_state_ui = "conversation"
        self.input_label = "> "
        self.update_binding_visibility()

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
        self.update_binding_visibility()

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
        self.update_binding_visibility()

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
        
        # Show available contacts if any
        contacts_info = ""
        if app_state.contacts:
            contacts_info = f"\n📋 {len(app_state.contacts)} contact(s) disponible(s) (Ctrl+K pour gérer)"
        
        config_container.mount(Static(
            f"Nom d'utilisateur: {app_state.username}\n"
            f"Port: {app_state.port}\n"
            f"Adresse IP: {app_state.local_ip}{contacts_info}\n\n"
            f"Mode mesh: Connectez-vous à un peer ou attendez des connexions", 
            classes="content-text"
        ))
        self.update_binding_visibility()
        # Force immediate refresh of bindings for first-time display
        self.refresh()

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
        
        elif message_type == 'file':
            await self.handle_file_message(data, peer_key)
        
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
    
    async def handle_file_message(self, data, peer_key):
        """Handle encrypted file messages."""
        if 'file_data' not in data or 'file_info' not in data:
            self.chat_view.add_message("Système", "Erreur: Fichier reçu sans données complètes")
            return
        
        peer = app_state.peers.get(peer_key)
        if not peer or not peer.encryption_ready or not peer.shared_key:
            self.chat_view.add_message("Système", "Erreur: Fichier reçu mais chiffrement non établi")
            return
        
        # Check for message loop prevention
        message_id = data.get('message_id', '')
        if message_id in app_state.message_ids:
            return
        
        app_state.message_ids.add(message_id)
        
        try:
            # Decrypt file data
            decrypted_b64 = decrypt(data['file_data'], peer.shared_key)
            file_info_data = data['file_info']
            
            # Create FileMessage object
            file_info = FileMessage(
                sender=data.get('sender', 'Inconnu'),
                filename=file_info_data['filename'],
                file_size=file_info_data['file_size'],
                file_type=file_info_data['file_type'],
                file_hash=file_info_data['file_hash'],
                timestamp=data.get('timestamp', datetime.now().strftime("%H:%M:%S")),
                download_available=True
            )
            
            # Save file to temp folder for verification
            temp_path = os.path.join(app_state.temp_folder, f"received_{message_id}_{file_info.filename}")
            file_bytes = base64.b64decode(decrypted_b64)
            
            with open(temp_path, 'wb') as f:
                f.write(file_bytes)
            
            # Verify file hash
            import hashlib
            with open(temp_path, 'rb') as f:
                received_hash = hashlib.sha256(f.read()).hexdigest()
            
            if received_hash != file_info.file_hash:
                self.chat_view.add_message("Système", f"⚠️ Erreur d'intégrité du fichier {file_info.filename}")
                os.remove(temp_path)
                return
            
            # Add message to chat
            self.chat_view.add_message(
                data.get('sender', 'Inconnu'),
                f"Fichier partagé: {file_info.filename}",
                data.get('timestamp'),
                "file",
                file_info
            )
            
            # Update file display
            self.chat_view.update_file_display(file_info, download_link=True)
            
            # Forward to other peers
            await self.forward_file_to_peers(
                sender=data.get('sender', 'Inconnu'),
                file_b64=decrypted_b64,
                file_info_data=file_info_data,
                message_id=message_id,
                timestamp=data.get('timestamp'),
                exclude_peer=peer_key
            )
            
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur de traitement du fichier: {e}")
    
    async def forward_file_to_peers(self, sender, file_b64, file_info_data, message_id, timestamp, exclude_peer=None):
        """Forward a decrypted file to all other peers (re-encrypted for each)."""
        ready_peers = app_state.get_ready_peers()
        
        for peer in ready_peers:
            peer_key = app_state.get_peer_key(peer.ip, peer.port)
            if peer_key != exclude_peer:
                try:
                    # Re-encrypt with this peer's key
                    encrypted_file = encrypt(file_b64, peer.shared_key)
                    await self.send_json_to_peer(peer.ip, peer.port, {
                        "type": "file",
                        "sender": sender,
                        "file_data": encrypted_file,
                        "file_info": file_info_data,
                        "message_id": message_id,
                        "timestamp": timestamp,
                        "sender_port": app_state.port
                    })
                except Exception as e:
                    self.chat_view.add_message("Système", f"Erreur forwarding fichier vers {peer.ip}:{peer.port}: {e}")

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

    async def broadcast_message_to_peers(self, message_text=None, image_path=None, file_path=None):
        """Broadcast a message, image, or file to all connected peers CONCURRENTLY."""
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
            elif file_path is not None:
                # File message task
                task = self._send_file_to_peer(peer, file_path, message_id)
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
    
    async def _send_file_to_peer(self, peer: PeerConnection, file_path: str, message_id: str):
        """Send a file to a specific peer."""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Get file info and read file
            filename, file_size, file_type, file_hash = get_file_info(file_path)
            
            with open(file_path, 'rb') as f:
                file_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Create file info object
            file_info = {
                "filename": filename,
                "file_size": file_size,
                "file_type": file_type,
                "file_hash": file_hash
            }
            
            encrypted_file = encrypt(file_data, peer.shared_key)
            
            await self.send_json_to_peer(peer.ip, peer.port, {
                "type": "file",
                "sender": app_state.username,
                "file_data": encrypted_file,
                "file_info": file_info,
                "message_id": message_id,
                "timestamp": timestamp,
                "sender_port": app_state.port
            })
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur d'envoi de fichier vers {peer.ip}:{peer.port}: {e}")
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
            self.update_binding_visibility()
            
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
            self.update_binding_visibility()
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
        
        # Check if it's a file path
        if os.path.isfile(message):
            try:
                # Validate file size
                if os.path.getsize(message) > app_state.max_file_size:
                    size_str = format_file_size(app_state.max_file_size)
                    self.chat_view.add_message("Système", f"Fichier trop volumineux (max {size_str})")
                    return
                
                # Determine if it's an image or regular file
                if is_image_file(message):
                    # Handle as image with preview
                    self.chat_view.add_message(app_state.username, "[Image envoyée]", message_type="image")
                    
                    # Process image asynchronously for preview
                    display_content = await process_image_for_display_async(message)
                    self.chat_view.update_image_display(display_content)
                    
                    # Send as image
                    await self.broadcast_message_to_peers(image_path=message)
                else:
                    # Handle as regular file
                    filename, file_size, file_type, file_hash = get_file_info(message)
                    file_info = FileMessage(
                        sender=app_state.username,
                        filename=filename,
                        file_size=file_size,
                        file_type=file_type,
                        file_hash=file_hash,
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        download_available=False  # Local file, no download needed
                    )
                    
                    self.chat_view.add_message(app_state.username, f"Fichier partagé: {filename}", message_type="file", file_info=file_info)
                    self.chat_view.update_file_display(file_info, download_link=False)
                    
                    # Send as file
                    await self.broadcast_message_to_peers(file_path=message)
                
            except Exception as e:
                self.chat_view.add_message("Système", f"Erreur d'envoi: {e}")
        else:
            # Send text message
            self.chat_view.add_message(app_state.username, message)
            await self.broadcast_message_to_peers(message_text=message)

    # ────────────────────── actions ────────────────────────
    async def action_select_file(self) -> None:
        """Open file selector modal (F5)."""
        if self.app_state_ui != "conversation":
            self.notify("Partage de fichiers disponible uniquement en conversation", severity="warning")
            return
        
        try:
            def handle_file_result(result):
                if result:
                    asyncio.create_task(self.send_selected_file(result))
                else:
                    self.notify("Sélection de fichier annulée", severity="information")
            
            self.push_screen(FileShareModal(), handle_file_result)
            
        except Exception as e:
                        self.notify(f"Erreur lors de l'ouverture du sélecteur de fichier: {e}", severity="error")
    
    async def action_manage_contacts(self) -> None:
        """Open contact manager (Ctrl+K)."""
        try:
            # Contact manager can be opened from all setup states and conversation
            if self.app_state_ui.startswith("setup_") or self.app_state_ui == "conversation":
                self.push_screen(ContactManagerModal())
            else:
                self.notify("Gestionnaire de contacts disponible après configuration", severity="warning")
        except Exception as e:
            self.notify(f"Erreur lors de l'ouverture du gestionnaire de contacts: {e}", severity="error")
    
    async def action_manage_downloads(self) -> None:
        """Open download manager (Ctrl+D)."""
        if self.app_state_ui != "conversation":
            self.notify("Gestionnaire de téléchargements disponible uniquement en conversation", severity="warning")
            return
            
        try:
            self.push_screen(DownloadManagerModal())
        except Exception as e:
            self.notify(f"Erreur lors de l'ouverture du gestionnaire de téléchargements: {e}", severity="error")
    
    async def action_load_conversation(self) -> None:
        """Load conversation history (Ctrl+H)."""
        if self.app_state_ui != "conversation":
            self.notify("Historique disponible uniquement en conversation", severity="warning")
            return
        
        try:
            # For now, just reload current conversation
            self.chat_view.load_conversation_history()
            self.notify("Historique des conversations rechargé", severity="success")
        except Exception as e:
            self.notify(f"Erreur lors du chargement de l'historique: {e}", severity="error")
    
    async def send_selected_file(self, file_path: str):
        """Send the selected file."""
        try:
            # Validate file size
            file_size = os.path.getsize(file_path)
            if file_size > app_state.max_file_size:
                size_str = format_file_size(app_state.max_file_size)
                self.chat_view.add_message("Système", f"Fichier trop volumineux (max {size_str})")
                return
                
            # Get file info
            filename, file_size, file_type, file_hash = get_file_info(file_path)
            size_str = format_file_size(file_size)
            
            self.notify(f"Envoi de {filename} ({size_str})...", severity="information")
            
            # Determine handling based on file type
            if is_image_file(filename):
                # Handle as image with preview
                self.chat_view.add_message(app_state.username, f"Image: {filename}", message_type="image")
                
                # Process image for preview
                display_content = await process_image_for_display_async(file_path)
                self.chat_view.update_image_display(display_content)
                
                # Send as image
                await self.broadcast_message_to_peers(image_path=file_path)
            else:
                # Handle as regular file
                file_info = FileMessage(
                    sender=app_state.username,
                    filename=filename,
                    file_size=file_size,
                    file_type=file_type,
                    file_hash=file_hash,
                    timestamp=datetime.now().strftime("%H:%M:%S"),
                    download_available=False
                )
                
                self.chat_view.add_message(app_state.username, f"Fichier partagé: {filename}", message_type="file", file_info=file_info)
                self.chat_view.update_file_display(file_info, download_link=False)
                
                # Send as file
                await self.broadcast_message_to_peers(file_path=file_path)
            
            # Success notification
            self.notify(f"✅ {filename} envoyé avec succès!", severity="success")
            
        except Exception as e:
            self.chat_view.add_message("Système", f"Erreur d'envoi: {e}")
            self.notify(f"❌ Erreur d'envoi: {e}", severity="error")
    
    def connect_to_contact(self, contact: Contact):
        """Connect to a contact from the contact manager."""
        try:
            self.notify(f"Connexion à {contact.name} ({contact.ip}:{contact.port})...", severity="information")
            
            # Create connection task
            asyncio.create_task(self.establish_full_peer_connection(contact.ip, contact.port))
            
        except Exception as e:
            self.notify(f"Erreur de connexion à {contact.name}: {e}", severity="error")
    
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

    async def action_step_back(self) -> None:
        """Go back one step in configuration."""
        if self.app_state_ui == "setup_username":
            await self.show_welcome()
        elif self.app_state_ui == "setup_port":
            await self.start_setup(self.query_one("#user-input"))
        elif self.app_state_ui == "setup_mode":
            await self.setup_username("", self.query_one("#user-input"))
        elif self.app_state_ui == "setup_target_ip":
            await self.setup_port("", self.query_one("#user-input"))
        elif self.app_state_ui == "setup_target_port":
            await self.setup_target_ip("", self.query_one("#user-input"))
    
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
            
            # Reset input placeholder and hide file button
            try:
                input_field = self.query_one("#user-input")
                input_field.placeholder = "o/n"
            except Exception:
                pass
        
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
        
        self.update_binding_visibility()

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
        """Handle key presses with state-specific context awareness."""
        key_str = str(event.key)
        
        # Global shortcuts (available everywhere)
        if key_str in ["ctrl+c", "ctrl+q"]:
            await self.action_quit()
            return
        elif key_str == "ctrl+\\": # Palette shortcut
            # Let Textual handle this
            return
        
        # State-specific shortcuts
        if self.app_state_ui == "welcome":
            # Welcome screen: only quit and palette
            pass  # No additional shortcuts
            
        elif self.app_state_ui in ["setup_username", "setup_port", "setup_mode", "setup_target_ip", "setup_target_port"]:
            # Configuration screens: quit, step back, and palette
            if key_str == "ctrl+r":
                await self.action_step_back()
                
        elif self.app_state_ui == "conversation":
            # Conversation: all shortcuts available
            if key_str == "f5":
                await self.action_select_file()
            elif key_str == "ctrl+k":
                await self.action_manage_contacts()
            elif key_str == "ctrl+d":
                await self.action_manage_downloads()
            elif key_str == "ctrl+h":
                await self.action_load_conversation()
            elif key_str == "ctrl+r":
                await self.action_reset_config()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "file-btn":
            # Alternative way to open file selector
            await self.action_select_file()

# Point d'entrée principal
if __name__ == "__main__":
    # Lancer l'application Textual
    app = EncodHexApp()
    app.run()
