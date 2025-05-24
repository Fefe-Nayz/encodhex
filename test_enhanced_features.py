#!/usr/bin/env python3
"""
Test script for EncodHex v3.0 enhanced features
Tests file sharing, contact management, search, and GIF animation capabilities
"""

import os
import sys
import tempfile
import json
from PIL import Image
import base64

def create_test_files():
    """Create test files for the enhanced browser."""
    test_dir = "test_files"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create some test text files
    with open(f"{test_dir}/readme.txt", "w") as f:
        f.write("This is a test README file.\nIt contains sample text for testing the file browser preview functionality.\n")
    
    with open(f"{test_dir}/config.json", "w") as f:
        json.dump({"test": True, "version": "3.0", "features": ["search", "filter", "preview"]}, f, indent=2)
    
    with open(f"{test_dir}/script.py", "w") as f:
        f.write('#!/usr/bin/env python3\nprint("Hello from test script!")\n')
    
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    for x in range(100):
        for y in range(100):
            if (x + y) % 20 < 10:
                img.putpixel((x, y), (0, 255, 0))
    img.save(f"{test_dir}/test_image.png")
    
    # Create a simple animated GIF
    frames = []
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    for i, color in enumerate(colors):
        frame = Image.new('RGB', (50, 50), color=color)
        # Add some pattern
        for x in range(0, 50, 10):
            for y in range(0, 50, 10):
                if (x//10 + y//10 + i) % 2:
                    for px in range(x, min(x+5, 50)):
                        for py in range(y, min(y+5, 50)):
                            frame.putpixel((px, py), (255, 255, 255))
        frames.append(frame)
    
    frames[0].save(
        f"{test_dir}/animated.gif",
        save_all=True,
        append_images=frames[1:],
        duration=500,
        loop=0
    )
    
    # Create different file types
    with open(f"{test_dir}/data.csv", "w") as f:
        f.write("name,age,city\nAlice,25,Paris\nBob,30,Lyon\nCharlie,35,Marseille\n")
    
    # Create binary file
    with open(f"{test_dir}/binary.dat", "wb") as f:
        f.write(b'\x00\x01\x02\x03\x04\x05' * 100)
    
    print(f"✅ Test files created in {test_dir}/")
    return test_dir

def test_contacts_data():
    """Create test contacts data."""
    test_contacts = {
        "Alice": {
            "name": "Alice",
            "ip": "192.168.1.100",
            "port": 8765,
            "notes": "Friend from work"
        },
        "Bob": {
            "name": "Bob", 
            "ip": "192.168.1.101",
            "port": 8766,
            "notes": "College buddy"
        },
        "Charlie": {
            "name": "Charlie",
            "ip": "10.0.0.50",
            "port": 8765,
            "notes": "Gaming friend"
        }
    }
    
    os.makedirs("data", exist_ok=True)
    with open("data/contacts.json", "w") as f:
        json.dump(test_contacts, f, indent=2)
    
    print("✅ Test contacts created in data/contacts.json")

def test_groups_data():
    """Create test groups data."""
    test_groups = {
        "Work Team": {
            "name": "Work Team",
            "contacts": ["Alice"],
            "created": "2024-01-15T10:00:00",
            "description": "Work colleagues"
        },
        "Gaming Squad": {
            "name": "Gaming Squad", 
            "contacts": ["Bob", "Charlie"],
            "created": "2024-01-20T15:30:00",
            "description": "Weekend gaming sessions"
        }
    }
    
    os.makedirs("data", exist_ok=True)
    with open("data/groups.json", "w") as f:
        json.dump(test_groups, f, indent=2)
    
    print("✅ Test groups created in data/groups.json")

def test_conversation_data():
    """Create test conversation history."""
    test_conversation = [
        {
            "sender": "Alice",
            "content": "Hello everyone!",
            "timestamp": "2024-01-25T10:00:00",
            "message_type": "text"
        },
        {
            "sender": "User",
            "content": "Fichier partagé: document.pdf",
            "timestamp": "2024-01-25T10:05:00", 
            "message_type": "file",
            "file_info": {
                "sender": "User",
                "filename": "document.pdf",
                "file_size": 1024000,
                "file_type": "application/pdf",
                "file_hash": "abc123def456",
                "timestamp": "2024-01-25T10:05:00",
                "download_available": True
            }
        },
        {
            "sender": "Bob",
            "content": "Thanks for the file!",
            "timestamp": "2024-01-25T10:10:00",
            "message_type": "text"
        }
    ]
    
    os.makedirs("conversations", exist_ok=True)
    with open("conversations/test_conversation.json", "w") as f:
        json.dump(test_conversation, f, indent=2)
    
    print("✅ Test conversation created in conversations/test_conversation.json")

def test_file_formats():
    """Test that various file formats are handled correctly."""
    import mimetypes
    
    test_files = [
        "test.txt", "document.pdf", "image.png", "video.mp4", 
        "audio.mp3", "archive.zip", "data.json", "script.py"
    ]
    
    print("\n📋 File format detection test:")
    for filename in test_files:
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # Test icon detection
        if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg')):
            icon = "🖼️"
        elif mime_type.startswith("text/"):
            icon = "📄"
        elif mime_type.startswith("video/"):
            icon = "🎥"
        elif mime_type.startswith("audio/"):
            icon = "🎵"
        else:
            icon = "📎"
        
        print(f"  {icon} {filename} → {mime_type}")

def test_file_size_formatting():
    """Test file size formatting."""
    import math
    
    def format_file_size(size_bytes):
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    test_sizes = [0, 512, 1024, 1536, 1048576, 1073741824, 5368709120]
    
    print("\n📏 File size formatting test:")
    for size in test_sizes:
        formatted = format_file_size(size)
        print(f"  {size:>12} bytes → {formatted}")

def print_usage_instructions():
    """Print usage instructions for the enhanced features."""
    print("""
🎯 EncodHex v3.0 - Enhanced Features Test Setup Complete!

🔧 New Features to Test:

1. 📎 File Sharing (F5):
   - Browse and share any file type
   - Search files by name
   - Filter to show only images
   - Preview images, GIFs (animated!), and text files
   - File size and type information

2. 👥 Contact Management (Ctrl+K):
   - Add, edit, delete contacts
   - Quick connect to saved contacts
   - Contact notes and last connection time
   - Automatic contact association

3. 📥 Download Manager (Ctrl+D):
   - View all received files
   - Download files to local folder
   - File integrity verification
   - Open downloads folder

4. 📜 Conversation History (Ctrl+H):
   - Auto-save conversations
   - Load previous conversations
   - File sharing history
   - Group chat support

🎮 Enhanced File Browser Features:
   • 🔍 Real-time search as you type
   • 🖼️ Image-only filter toggle
   • 📄 Text file preview (up to 50KB)
   • 🎬 Animated GIF preview with ASCII frames
   • 📊 File size and type information
   • 🔍 Split-view with preview panel

📁 Test Files Created:
   • test_files/ - Various file types for testing
   • data/contacts.json - Sample contacts
   • data/groups.json - Sample groups
   • conversations/ - Sample conversation history

💡 Tips:
   - Use arrow keys to navigate file browser
   - Type in search box to filter files
   - Click "🖼️ Images" to show only image files
   - GIFs will animate in the preview panel
   - Files under 50KB will show text preview

🚀 Start the app with: python tui_app.py
""")

def main():
    """Main test setup function."""
    print("🧪 Setting up EncodHex v3.0 Enhanced Features Test Environment...")
    
    # Create test data
    test_dir = create_test_files()
    test_contacts_data()
    test_groups_data()
    test_conversation_data()
    
    # Run format tests
    test_file_formats()
    test_file_size_formatting()
    
    # Create directories
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    
    print_usage_instructions()

if __name__ == "__main__":
    main() 