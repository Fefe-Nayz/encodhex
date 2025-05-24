#!/usr/bin/env python3
"""
Script de test pour tester les nouvelles fonctionnalités de contacts et groupes
"""

import sys
import os
import json
from datetime import datetime

# Ajouter le dossier parent au path pour importer les modules
sys.path.append('.')

def create_test_contacts():
    """Créer des contacts de test."""
    contacts = {
        "Alice": {
            "name": "Alice",
            "ip": "192.168.1.10",
            "port": 8765,
            "last_connected": datetime.now().isoformat(),
            "notes": "Contact de test - Alice"
        },
        "Bob": {
            "name": "Bob", 
            "ip": "192.168.1.11",
            "port": 8765,
            "last_connected": None,
            "notes": "Contact de test - Bob"
        },
        "Charlie": {
            "name": "Charlie",
            "ip": "192.168.1.12",
            "port": 8766,
            "last_connected": datetime.now().isoformat(),
            "notes": "Contact de test - Charlie sur port différent"
        },
        "David": {
            "name": "David",
            "ip": "10.0.0.5",
            "port": 8765,
            "last_connected": None,
            "notes": "Contact de test - David réseau différent"
        }
    }
    
    # Créer le dossier data s'il n'existe pas
    os.makedirs("data", exist_ok=True)
    
    # Sauvegarder les contacts
    with open("data/contacts.json", "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=False)
    
    print("✅ Contacts de test créés:")
    for name, contact in contacts.items():
        print(f"  - {name}: {contact['ip']}:{contact['port']}")

def create_test_groups():
    """Créer des groupes de test."""
    groups = {
        "Réseau Local": {
            "name": "Réseau Local",
            "contacts": ["Alice", "Bob", "Charlie"],
            "created": datetime.now().isoformat(),
            "description": "Groupe pour le réseau local 192.168.1.x"
        },
        "Équipe Alpha": {
            "name": "Équipe Alpha",
            "contacts": ["Alice", "David"],
            "created": datetime.now().isoformat(),
            "description": "Équipe Alpha - contacts prioritaires"
        },
        "Tous": {
            "name": "Tous",
            "contacts": ["Alice", "Bob", "Charlie", "David"],
            "created": datetime.now().isoformat(),
            "description": "Groupe avec tous les contacts"
        }
    }
    
    # Sauvegarder les groupes
    with open("data/groups.json", "w", encoding="utf-8") as f:
        json.dump(groups, f, indent=2, ensure_ascii=False)
    
    print("✅ Groupes de test créés:")
    for name, group in groups.items():
        print(f"  - {name}: {len(group['contacts'])} contacts ({', '.join(group['contacts'])})")

def test_app_startup():
    """Tester le démarrage de l'app avec les données de test."""
    try:
        from tui_app import app_state
        print("✅ App state importé")
        
        # Charger les contacts et groupes
        app_state.load_contacts()
        app_state.load_groups()
        
        print(f"✅ {len(app_state.contacts)} contacts chargés")
        print(f"✅ {len(app_state.groups)} groupes chargés")
        
        # Afficher les détails
        if app_state.contacts:
            print("\n📋 Contacts chargés:")
            for name, contact in app_state.contacts.items():
                print(f"  - {contact.name}: {contact.ip}:{contact.port}")
        
        if app_state.groups:
            print("\n👥 Groupes chargés:")
            for name, group in app_state.groups.items():
                print(f"  - {group.name}: {len(group.contacts)} contacts")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 Test des Contacts et Groupes EncodHex\n")
    
    print("1. Création des contacts de test...")
    create_test_contacts()
    
    print("\n2. Création des groupes de test...")
    create_test_groups()
    
    print("\n3. Test du chargement dans l'app...")
    success = test_app_startup()
    
    if success:
        print("\n✅ Tous les tests réussis!")
        print("\n💡 Pour tester:")
        print("   1. Lancez: python tui_app.py")
        print("   2. Configurez votre nom et port")
        print("   3. Appuyez Ctrl+K pour ouvrir le gestionnaire")
        print("   4. Testez les onglets Contacts, Groupes, Connexion Rapide")
        print("   5. Essayez la connexion rapide avec 'Alice' ou 'Réseau Local'")
    else:
        print("\n❌ Des erreurs ont été détectées")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 