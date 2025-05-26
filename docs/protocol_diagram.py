#!/usr/bin/env python3
"""
Script to generate Graphviz diagrams explaining the EncodHex protocol and architecture.
Run this script to generate SVG diagrams that explain the system.
"""

import graphviz
import os

def create_protocol_diagram():
    """Create a diagram explaining the main.py protocol flow."""
    dot = graphviz.Digraph(comment='EncodHex Protocol Flow')
    dot.attr(rankdir='TB', size='12,16')
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
    
    # Connection establishment
    with dot.subgraph(name='cluster_0') as c:
        c.attr(label='1. Connection Establishment', style='filled', color='lightgrey')
        c.node('A1', 'Client A starts\n(Waiting mode)')
        c.node('B1', 'Client B initiates\nconnection')
        c.node('hello', 'HELLO message\n{type: "hello", i_generate: bool}')
        
    # Diffie-Hellman Exchange
    with dot.subgraph(name='cluster_1') as c:
        c.attr(label='2. Diffie-Hellman Key Exchange', style='filled', color='lightgreen')
        c.node('dh_gen', 'Generate DH Parameters\n(p, g)')
        c.node('dh_params', 'DH_PARAMS message\n{type: "dh_params", p, g}')
        c.node('keys', 'Generate Private/Public\nkey pairs')
        c.node('dh_public', 'DH_PUBLIC_KEY message\n{type: "dh_public_key", public_key}')
        c.node('shared', 'Compute Shared Key\nfrom other\'s public key')
    
    # Encrypted Communication
    with dot.subgraph(name='cluster_2') as c:
        c.attr(label='3. Encrypted Communication', style='filled', color='lightyellow')
        c.node('encrypt', 'Encrypt message\nwith AES-256')
        c.node('text_msg', 'TEXT message\n{type: "text", message: encrypted}')
        c.node('decrypt', 'Decrypt message\nwith shared key')
        c.node('display', 'Display message\nto user')
    
    # Message flow
    dot.edge('B1', 'hello', label='send')
    dot.edge('hello', 'A1', label='receive')
    dot.edge('A1', 'dh_gen', label='if i_generate=false')
    dot.edge('dh_gen', 'dh_params', label='send')
    dot.edge('dh_params', 'keys', label='receive & generate')
    dot.edge('keys', 'dh_public', label='send')
    dot.edge('dh_public', 'shared', label='receive & compute')
    dot.edge('shared', 'encrypt', label='encryption ready')
    dot.edge('encrypt', 'text_msg', label='send')
    dot.edge('text_msg', 'decrypt', label='receive')
    dot.edge('decrypt', 'display', label='show user')
    
    return dot

def create_tui_architecture_diagram():
    """Create a diagram explaining the TUI app architecture."""
    dot = graphviz.Digraph(comment='TUI App Architecture')
    dot.attr(rankdir='TB', size='14,18')
    dot.attr('node', shape='box', style='rounded,filled')
    
    # Main App
    dot.node('app', 'EncodHexApp\n(Main Application)', fillcolor='lightcoral')
    
    # State Management
    with dot.subgraph(name='cluster_state') as c:
        c.attr(label='State Management', style='filled', color='lightblue')
        c.node('app_state', 'AppState\n- username, port, ip\n- peers, connections\n- contacts, groups\n- conversation history', fillcolor='lightblue')
        c.node('peer_conn', 'PeerConnection\n- ip, port, websocket\n- encryption status\n- contact info', fillcolor='lightblue')
        c.node('dh_exchange', 'DHExchange\n- DH parameters\n- key exchange state', fillcolor='lightblue')
    
    # UI Screens
    with dot.subgraph(name='cluster_ui') as c:
        c.attr(label='User Interface', style='filled', color='lightgreen')
        c.node('welcome', 'Welcome Screen\n- Initial setup\n- Username/Port config', fillcolor='lightgreen')
        c.node('config', 'Configuration Screen\n- Connection setup\n- IP/Port selection', fillcolor='lightgreen')
        c.node('chat', 'Chat Screen\n- Message display\n- Input field\n- File sharing', fillcolor='lightgreen')
    
    # Modals
    with dot.subgraph(name='cluster_modals') as c:
        c.attr(label='Modal Dialogs', style='filled', color='lightyellow')
        c.node('contacts', 'ContactManagerModal\n- Add/edit contacts\n- Manage groups\n- Quick connect', fillcolor='lightyellow')
        c.node('file_browser', 'FileBrowserModal\n- File selection\n- Preview support\n- Image/GIF display', fillcolor='lightyellow')
        c.node('file_share', 'FileShareModal\n- File sharing\n- Preview & confirm\n- Drag & drop', fillcolor='lightyellow')
        c.node('downloads', 'DownloadManagerModal\n- View received files\n- Download management', fillcolor='lightyellow')
    
    # Network Layer
    with dot.subgraph(name='cluster_network') as c:
        c.attr(label='Network & Encryption', style='filled', color='lightpink')
        c.node('websocket', 'WebSocket Server\n- Handle connections\n- Message routing', fillcolor='lightpink')
        c.node('encryption', 'AES Encryption\n- Message encryption\n- File encryption', fillcolor='lightpink')
        c.node('diffie_hellman', 'Diffie-Hellman\n- Key exchange\n- Parameter generation', fillcolor='lightpink')
    
    # Connections
    dot.edge('app', 'app_state', label='manages')
    dot.edge('app_state', 'peer_conn', label='contains')
    dot.edge('app_state', 'dh_exchange', label='tracks')
    
    dot.edge('app', 'welcome', label='shows')
    dot.edge('welcome', 'config', label='proceeds to')
    dot.edge('config', 'chat', label='connects to')
    
    dot.edge('app', 'contacts', label='opens')
    dot.edge('app', 'file_browser', label='opens')
    dot.edge('app', 'file_share', label='opens')
    dot.edge('app', 'downloads', label='opens')
    
    dot.edge('app', 'websocket', label='manages')
    dot.edge('websocket', 'encryption', label='uses')
    dot.edge('websocket', 'diffie_hellman', label='uses')
    
    return dot

def create_encryption_diagram():
    """Create a diagram explaining the encryption process."""
    dot = graphviz.Digraph(comment='Encryption Process')
    dot.attr(rankdir='LR', size='12,8')
    dot.attr('node', shape='box', style='rounded,filled')
    
    # Diffie-Hellman
    with dot.subgraph(name='cluster_dh') as c:
        c.attr(label='Diffie-Hellman Key Exchange', style='filled', color='lightblue')
        c.node('dh1', 'Generate\nParameters (p,g)', fillcolor='lightblue')
        c.node('dh2', 'Generate\nPrivate Key (a)', fillcolor='lightblue')
        c.node('dh3', 'Calculate\nPublic Key (g^a mod p)', fillcolor='lightblue')
        c.node('dh4', 'Exchange\nPublic Keys', fillcolor='lightblue')
        c.node('dh5', 'Calculate\nShared Secret', fillcolor='lightblue')
    
    # AES Encryption
    with dot.subgraph(name='cluster_aes') as c:
        c.attr(label='AES-256 Encryption', style='filled', color='lightgreen')
        c.node('aes1', 'Normalize\nShared Key', fillcolor='lightgreen')
        c.node('aes2', 'Pad Message\n(PKCS7)', fillcolor='lightgreen')
        c.node('aes3', 'Generate\nRandom IV', fillcolor='lightgreen')
        c.node('aes4', 'AES-256-CBC\nEncryption', fillcolor='lightgreen')
        c.node('aes5', 'Base64\nEncoding', fillcolor='lightgreen')
    
    # Message Flow
    with dot.subgraph(name='cluster_msg') as c:
        c.attr(label='Message Transmission', style='filled', color='lightyellow')
        c.node('msg1', 'Plain Text\nMessage', fillcolor='lightyellow')
        c.node('msg2', 'Encrypted\nMessage', fillcolor='lightyellow')
        c.node('msg3', 'WebSocket\nTransmission', fillcolor='lightyellow')
        c.node('msg4', 'Decryption\nProcess', fillcolor='lightyellow')
        c.node('msg5', 'Recovered\nPlain Text', fillcolor='lightyellow')
    
    # DH Flow
    dot.edge('dh1', 'dh2')
    dot.edge('dh2', 'dh3')
    dot.edge('dh3', 'dh4')
    dot.edge('dh4', 'dh5')
    
    # AES Flow
    dot.edge('dh5', 'aes1', label='shared secret')
    dot.edge('aes1', 'aes2')
    dot.edge('aes2', 'aes3')
    dot.edge('aes3', 'aes4')
    dot.edge('aes4', 'aes5')
    
    # Message Flow
    dot.edge('msg1', 'aes2', label='input')
    dot.edge('aes5', 'msg2', label='output')
    dot.edge('msg2', 'msg3')
    dot.edge('msg3', 'msg4')
    dot.edge('msg4', 'msg5')
    
    return dot

def create_mesh_network_diagram():
    """Create a diagram explaining the mesh networking capability."""
    dot = graphviz.Digraph(comment='Mesh Network Architecture')
    dot.attr(size='10,10')
    dot.attr('node', shape='circle', style='filled', fillcolor='lightblue')
    
    # Nodes
    dot.node('A', 'Client A\n192.168.1.10:8765')
    dot.node('B', 'Client B\n192.168.1.11:8765') 
    dot.node('C', 'Client C\n192.168.1.12:8765')
    dot.node('D', 'Client D\n192.168.1.13:8765')
    
    # Connections
    dot.edge('A', 'B', label='encrypted')
    dot.edge('B', 'C', label='encrypted')
    dot.edge('C', 'D', label='encrypted')
    dot.edge('A', 'C', label='encrypted')
    dot.edge('B', 'D', label='encrypted')
    
    # Message flow
    with dot.subgraph(name='cluster_legend') as c:
        c.attr(label='Message Forwarding', style='filled', color='lightgrey')
        c.node('legend1', 'Messages are forwarded\nthrough the mesh network', shape='box', fillcolor='white')
        c.node('legend2', 'Each client maintains\nencrypted connections', shape='box', fillcolor='white')
        c.node('legend3', 'Message deduplication\nprevents loops', shape='box', fillcolor='white')
    
    return dot

def create_diagrams():
    """Generate all diagrams."""
    os.makedirs('docs/diagrams', exist_ok=True)
    
    # Protocol diagram
    protocol = create_protocol_diagram()
    protocol.render('docs/diagrams/protocol_flow', format='svg', cleanup=True)
    print("Generated: docs/diagrams/protocol_flow.svg")
    
    # TUI architecture
    tui = create_tui_architecture_diagram()
    tui.render('docs/diagrams/tui_architecture', format='svg', cleanup=True)
    print("Generated: docs/diagrams/tui_architecture.svg")
    
    # Encryption process
    encryption = create_encryption_diagram()
    encryption.render('docs/diagrams/encryption_process', format='svg', cleanup=True)
    print("Generated: docs/diagrams/encryption_process.svg")
    
    # Mesh network
    mesh = create_mesh_network_diagram()
    mesh.render('docs/diagrams/mesh_network', format='svg', cleanup=True)
    print("Generated: docs/diagrams/mesh_network.svg")

if __name__ == "__main__":
    try:
        create_diagrams()
        print("\nAll diagrams generated successfully!")
        print("View the SVG files in docs/diagrams/")
    except Exception as e:
        print(f"Error generating diagrams: {e}")
        print("Make sure you have graphviz installed: pip install graphviz") 