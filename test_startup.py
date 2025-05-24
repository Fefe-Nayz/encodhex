#!/usr/bin/env python3
"""
Script de test pour vérifier que EncodHex peut démarrer sans erreurs critiques
"""

import sys
import traceback

def test_imports():
    """Test des imports critiques"""
    print("🧪 Test des imports...")
    
    try:
        import textual
        print("✅ Textual importé")
    except ImportError as e:
        print(f"❌ Erreur d'import Textual: {e}")
        return False
    
    try:
        from textual.widgets import DataTable
        print("✅ DataTable importé")
    except ImportError as e:
        print(f"❌ Erreur d'import DataTable: {e}")
        return False
    
    try:
        import websockets
        print("✅ Websockets importé")
    except ImportError as e:
        print(f"❌ Erreur d'import websockets: {e}")
        return False
    
    try:
        from PIL import Image
        print("✅ PIL importé")
    except ImportError as e:
        print(f"❌ Erreur d'import PIL: {e}")
        return False
    
    try:
        from rich_pixels import Pixels
        print("✅ Rich-pixels importé")
    except ImportError as e:
        print(f"❌ Erreur d'import rich-pixels: {e}")
        return False
    
    return True

def test_app_init():
    """Test de l'initialisation de l'app"""
    print("\n🧪 Test de l'initialisation de l'app...")
    
    try:
        # Import de l'app
        from tui_app import EncodHexApp, app_state
        print("✅ App importée")
        
        # Test de création de l'instance
        app = EncodHexApp()
        print("✅ Instance créée")
        
        # Test de l'état initial
        print(f"✅ État initial: {app.app_state_ui}")
        print(f"✅ Username: '{app_state.username}'")
        print(f"✅ Port: {app_state.port}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        traceback.print_exc()
        return False

def test_data_structures():
    """Test des structures de données"""
    print("\n🧪 Test des structures de données...")
    
    try:
        from tui_app import Contact, Group, FileMessage, ConversationMessage
        
        # Test Contact
        contact = Contact("Test", "192.168.1.1", 8765, notes="Test contact")
        contact_dict = contact.to_dict()
        contact_restored = Contact.from_dict(contact_dict)
        print("✅ Contact serialization/deserialization")
        
        # Test Group
        group = Group("TestGroup", ["Contact1"], "2024-01-01T00:00:00")
        group_dict = group.to_dict()
        group_restored = Group.from_dict(group_dict)
        print("✅ Group serialization/deserialization")
        
        # Test FileMessage
        file_msg = FileMessage("sender", "test.txt", 1024, "text/plain", "hash123", "timestamp")
        file_dict = file_msg.to_dict()
        file_restored = FileMessage.from_dict(file_dict)
        print("✅ FileMessage serialization/deserialization")
        
        # Test ConversationMessage
        conv_msg = ConversationMessage("sender", "content", "timestamp")
        conv_dict = conv_msg.to_dict()
        conv_restored = ConversationMessage.from_dict(conv_dict)
        print("✅ ConversationMessage serialization/deserialization")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur dans les structures de données: {e}")
        traceback.print_exc()
        return False

def test_file_functions():
    """Test des fonctions de fichier"""
    print("\n🧪 Test des fonctions de fichier...")
    
    try:
        from tui_app import format_file_size, is_image_file
        
        # Test format_file_size
        sizes = format_file_size(0), format_file_size(1024), format_file_size(1048576)
        print(f"✅ Format file size: {sizes}")
        
        # Test is_image_file
        is_img = is_image_file("test.png"), is_image_file("test.txt")
        print(f"✅ Is image file: {is_img}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur dans les fonctions de fichier: {e}")
        traceback.print_exc()
        return False

def main():
    """Test principal"""
    print("🚀 Test de démarrage d'EncodHex v3.0\n")
    
    success = True
    
    success &= test_imports()
    success &= test_data_structures()
    success &= test_file_functions()
    success &= test_app_init()
    
    print(f"\n{'✅ Tous les tests passés!' if success else '❌ Certains tests ont échoué!'}")
    
    if success:
        print("\n💡 L'application devrait pouvoir démarrer. Essayez:")
        print("   python tui_app.py")
    else:
        print("\n🔧 Corrigez les erreurs avant de lancer l'application.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 