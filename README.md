# EncodHex - Chat P2P Chiffré Mesh

Version 2.1 - Mesh Network Fixed Edition  
Développé par Nino Belaoud & Ferréol DUBOIS COLI

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Test the simple cli app
python main.py

# Run the application
python tui_app.py
```

## Usage Guide

### **Quick Test Setup (3 Users)**

1. **Terminal 1 (Alice)**:

   ```
   python tui_app.py
   Username: Alice
   Port: 8765
   Mode: n (wait)
   ```

2. **Terminal 2 (Bob)**:

   ```
   python tui_app.py
   Username: Bob
   Port: 8766
   Mode: o (connect)
   IP: 127.0.0.1
   Port: 8765
   ```

3. **Terminal 3 (Carol)**:
   ```
   python tui_app.py
   Username: Carol
   Port: 8767
   Mode: o (connect)
   IP: 127.0.0.1
   Port: 8765
   ```

**Result**: Carol automatically discovers Bob and establishes secure connections with both Alice and Bob.

### **Message Testing**

- **Text**: Type any message and press Enter
- **Commands**:
  - `exit` - Quit
  - `Ctrl+R` - Go back to config menu
  - `Ctrl+C/Q` - Force quit
  - `F5` - Open the image selector

## Architecture Fixes

## Technical Specifications

### **Mesh Protocol**

1. **Hello**: Initial peer handshake
2. **Peer List**: Share network topology
3. **DH Params/Keys**: Establish encryption per pair
4. **Text/Image**: End-to-end encrypted content

### **Security Model**

- **Per-Peer Encryption**: Each connection has unique keys
- **Perfect Forward Secrecy**: DH key exchange per session
- **Message Loop Prevention**: Unique message IDs
- **Timeout Protection**: Connection and key exchange timeouts

### **Performance Optimizations**

- **Async Operations**: Non-blocking network and image processing
- **Connection Pooling**: Reuse WebSocket connections
- **Memory Management**: Automatic cleanup of resources
- **Error Recovery**: Graceful degradation and retry logic

## Known Limitations

- **Image Quality**: Low resolution images
- **Network Scale**: Optimized for 2-10 peers
- **File Size**: 5MB image limit for performance
- **Platform**: Best on modern terminals with Unicode support

Chat bidirectionnel chiffré par Diffie-Hellman et AES-256 pour projet d'informatique

## Fonctionnalités

Échange de clé sécurisé en utilisant l'algorithme [Diffie-Hellman](https://fr.wikipedia.org/wiki/%C3%89change_de_cl%C3%A9s_Diffie-Hellman)

Chiffrement des messages en utilisant [AES-256](https://fr.wikipedia.org/wiki/Advanced_Encryption_Standard)

## Informations

Les algorithmes de chiffrements ont été implémenté de zéro.

**Ne pas utiliser dans un véritable projet.**

## Démonstration

![Capture d'écran 2025-05-22 161806](https://github.com/user-attachments/assets/1c95780f-2359-40ad-bd8f-bed96a073834)
