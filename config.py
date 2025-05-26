"""
Configuration management for EncodHex chat application.
Provides centralized settings with JSON-based persistence.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class NetworkConfig:
    """Network-related configuration."""
    default_port: int = 8765
    ping_interval: int = 30  # seconds
    ping_timeout: int = 5    # seconds
    connection_timeout: int = 120  # seconds for considering peer disconnected
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds


@dataclass
class FileConfig:
    """File sharing configuration."""
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    downloads_folder: str = "downloads"
    temp_folder: str = "temp"
    allowed_extensions: list = None
    
    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = [
                # Images
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
                # Documents
                '.txt', '.pdf', '.doc', '.docx', '.rtf', '.odt',
                # Archives
                '.zip', '.rar', '.7z', '.tar', '.gz',
                # Media
                '.mp3', '.mp4', '.avi', '.mkv', '.wav', '.flac',
                # Code
                '.py', '.js', '.html', '.css', '.json', '.xml', '.md'
            ]


@dataclass
class UIConfig:
    """User interface configuration."""
    image_quality: int = 80
    max_image_width: int = 120
    max_image_height: int = 60
    auto_save_interval: int = 10  # messages
    theme: str = "dark"
    show_timestamps: bool = True
    show_file_previews: bool = True


@dataclass
class SecurityConfig:
    """Security-related configuration."""
    dh_key_size: int = 256  # bits
    session_timeout: int = 3600  # seconds
    max_message_history: int = 1000  # messages to keep in memory
    enable_message_encryption: bool = True
    enable_file_integrity_check: bool = True


@dataclass
class AppConfig:
    """Main application configuration."""
    network: NetworkConfig
    files: FileConfig
    ui: UIConfig
    security: SecurityConfig
    
    def __init__(self):
        self.network = NetworkConfig()
        self.files = FileConfig()
        self.ui = UIConfig()
        self.security = SecurityConfig()


class ConfigManager:
    """Manages application configuration with JSON persistence."""
    
    def __init__(self, config_file: str = "data/config.json"):
        self.config_file = config_file
        self.config = AppConfig()
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._update_config_from_dict(data)
        except Exception as e:
            print(f"Warning: Could not load config from {self.config_file}: {e}")
            print("Using default configuration.")
    
    def save_config(self) -> None:
        """Save current configuration to JSON file."""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # Convert config to dictionary
            config_dict = {
                'network': asdict(self.config.network),
                'files': asdict(self.config.files),
                'ui': asdict(self.config.ui),
                'security': asdict(self.config.security)
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving config to {self.config_file}: {e}")
    
    def _update_config_from_dict(self, data: Dict[str, Any]) -> None:
        """Update configuration from dictionary data."""
        if 'network' in data:
            self._update_dataclass(self.config.network, data['network'])
        if 'files' in data:
            self._update_dataclass(self.config.files, data['files'])
        if 'ui' in data:
            self._update_dataclass(self.config.ui, data['ui'])
        if 'security' in data:
            self._update_dataclass(self.config.security, data['security'])
    
    def _update_dataclass(self, obj: Any, data: Dict[str, Any]) -> None:
        """Update dataclass object with dictionary data."""
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
    
    def get_network_config(self) -> NetworkConfig:
        """Get network configuration."""
        return self.config.network
    
    def get_file_config(self) -> FileConfig:
        """Get file configuration."""
        return self.config.files
    
    def get_ui_config(self) -> UIConfig:
        """Get UI configuration."""
        return self.config.ui
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration."""
        return self.config.security
    
    def update_network_config(self, **kwargs) -> None:
        """Update network configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.network, key):
                setattr(self.config.network, key, value)
        self.save_config()
    
    def update_file_config(self, **kwargs) -> None:
        """Update file configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.files, key):
                setattr(self.config.files, key, value)
        self.save_config()
    
    def update_ui_config(self, **kwargs) -> None:
        """Update UI configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.ui, key):
                setattr(self.config.ui, key, value)
        self.save_config()
    
    def update_security_config(self, **kwargs) -> None:
        """Update security configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config.security, key):
                setattr(self.config.security, key, value)
        self.save_config()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = AppConfig()
        self.save_config()
    
    def export_config(self, file_path: str) -> bool:
        """Export configuration to a specific file."""
        try:
            config_dict = {
                'network': asdict(self.config.network),
                'files': asdict(self.config.files),
                'ui': asdict(self.config.ui),
                'security': asdict(self.config.security)
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def import_config(self, file_path: str) -> bool:
        """Import configuration from a specific file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._update_config_from_dict(data)
                self.save_config()
            return True
        except Exception:
            return False


# Global configuration manager instance
config_manager = ConfigManager() 