# EncodHex - Guide Utilisateur Complet

## Vue d'ensemble

EncodHex est une application de chat sécurisée avec chiffrement de bout en bout utilisant l'échange de clés Diffie-Hellman et le chiffrement AES-256. Elle permet de communiquer en toute sécurité entre plusieurs utilisateurs via un réseau en maille (mesh network).

## Fonctionnalités principales

### 🔐 Sécurité

- **Chiffrement de bout en bout** : Tous les messages sont chiffrés avec AES-256
- **Échange de clés Diffie-Hellman** : Génération sécurisée de clés partagées
- **Aucun serveur central** : Communication peer-to-peer directe
- **Réseau en maille** : Messages relayés automatiquement entre les pairs connectés

### 💬 Communication

- **Messages texte** en temps réel
- **Partage de fichiers** sécurisé (jusqu'à 50MB par défaut)
- **Partage d'images** avec prévisualisation
- **Support des GIF** animés
- **Historique des conversations** persistant

### 👥 Gestion des contacts

- **Carnet d'adresses** pour sauvegarder les contacts
- **Groupes de contacts** pour les conversations multi-utilisateurs
- **Connexion rapide** aux contacts favoris
- **Statut de connexion** en temps réel

## Installation et Configuration

### Prérequis

```bash
pip install -r requirements.txt
```

### Lancement de l'application

```bash
python tui_app.py
```

## Guide d'utilisation

### 1. Premier démarrage

Au premier lancement, vous devez configurer :

1. **Nom d'utilisateur** : Identifiant qui apparaîtra dans les messages
2. **Port d'écoute** : Port sur lequel votre application écoutera (défaut: 8765)
3. **Mode de connexion** :
   - **Attente** : Votre application attend les connexions entrantes
   - **Connexion** : Vous vous connectez à quelqu'un d'autre

### 2. Modes de connexion

#### Mode Attente

- Votre application devient un serveur
- Autres utilisateurs peuvent se connecter à votre IP:Port
- Idéal pour héberger une conversation

#### Mode Connexion

- Vous vous connectez à un autre utilisateur
- Nécessite l'IP et le port de destination
- L'échange de clés se fait automatiquement

### 3. Interface principale

Une fois connecté, vous accédez à l'interface de chat avec :

- **Zone de messages** : Affichage des conversations
- **Champ de saisie** : Pour taper vos messages
- **Barre d'état** : Informations de connexion
- **Raccourcis clavier** affichés en bas

### 4. Raccourcis clavier

| Raccourci  | Action                          |
| ---------- | ------------------------------- |
| `F1`       | Gestionnaire de contacts        |
| `F2`       | Gestionnaire de téléchargements |
| `F3`       | Historique des conversations    |
| `F5`       | Partager un fichier             |
| `Ctrl+R`   | Retour/Réinitialisation         |
| `Ctrl+C/Q` | Quitter                         |

### 5. Gestion des contacts

#### Ajouter un contact

1. Appuyez sur `F1` pour ouvrir le gestionnaire
2. Onglet "Contacts" → Bouton "Ajouter"
3. Remplissez les informations :
   - **Nom** : Nom du contact
   - **IP** : Adresse IP du contact
   - **Port** : Port du contact
   - **Notes** : Informations supplémentaires

#### Créer un groupe

1. Onglet "Groupes" → Bouton "Ajouter"
2. Remplissez :
   - **Nom du groupe**
   - **Contacts** : Noms séparés par des virgules
   - **Description** : Description du groupe

#### Connexion rapide

1. Onglet "Connexion rapide"
2. Saisissez IP:Port ou sélectionnez un contact
3. Cliquez "Connecter"

### 6. Partage de fichiers

#### Envoyer un fichier

1. Appuyez sur `F5` ou cliquez sur l'icône 📎
2. **Méthodes de sélection** :
   - Navigateur de fichiers intégré
   - Saisie manuelle du chemin
   - Glisser-déposer (si supporté)
3. **Prévisualisation** automatique
4. Confirmez l'envoi

#### Types de fichiers supportés

- **Images** : JPG, PNG, GIF (avec animation)
- **Texte** : TXT, MD, JSON, etc.
- **Tous fichiers** : Support universel avec détection MIME

#### Réception de fichiers

- Les fichiers reçus apparaissent dans le chat
- Téléchargement via le gestionnaire (`F2`)
- Stockage temporaire automatique

### 7. Gestion des téléchargements

Accès via `F2` :

- **Liste des fichiers** reçus dans la conversation
- **Informations** : nom, taille, type, date
- **Actions** :
  - Télécharger vers le dossier Downloads
  - Ouvrir le dossier de téléchargements
  - Gestion des doublons automatique

### 8. Historique des conversations

#### Sauvegarde automatique

- Conversations sauvegardées tous les 10 messages
- Sauvegarde immédiate pour les fichiers
- Format JSON pour la persistance

#### Restauration

- `F3` pour accéder à l'historique
- Sélection par contact ou groupe
- Chargement automatique des conversations existantes

### 9. Réseau en maille (Mesh Network)

#### Fonctionnement

- Chaque client peut se connecter à plusieurs autres
- Messages automatiquement relayés
- Déduplication pour éviter les boucles
- Pas de point de défaillance unique

#### Avantages

- **Redondance** : Multiple chemins de communication
- **Évolutivité** : Ajout facile de nouveaux participants
- **Résistance** : Continue de fonctionner même si certains nœuds tombent

## Sécurité et Vie Privée

### Chiffrement

- **AES-256-CBC** : Chiffrement symétrique des messages
- **Clés éphémères** : Nouvelles clés pour chaque session
- **IV aléatoires** : Vecteurs d'initialisation uniques
- **Pas de stockage des clés** : Clés uniquement en mémoire

### Échange de clés

- **Diffie-Hellman** : Protocole d'échange sécurisé
- **Paramètres robustes** : Nombres premiers de 256 bits
- **Protection contre l'écoute** : Impossible de déchiffrer sans la clé privée

### Bonnes pratiques

- Utilisez des réseaux privés de confiance
- Vérifiez l'identité de vos correspondants
- Pas de stockage des mots de passe
- Fermez l'application quand elle n'est pas utilisée

## Résolution des problèmes

### Problèmes de connexion

- **Vérifiez les firewalls** : Ports doivent être ouverts
- **IP correcte** : Utilisez l'IP locale du réseau
- **Ports disponibles** : Évitez les ports déjà utilisés
- **Même réseau** : Les clients doivent être sur le même réseau local

### Problèmes de performance

- **Taille des fichiers** : Limitez les gros fichiers
- **Mémoire** : L'application peut consommer de la RAM avec de gros transferts
- **Réseau lent** : Réduisez la qualité des images partagées

### Messages d'erreur courants

- **"Port déjà utilisé"** : Changez le port d'écoute
- **"Connexion refusée"** : Vérifiez IP/Port destination
- **"Clé d'échange échouée"** : Reconnectez-vous
- **"Fichier introuvable"** : Vérifiez le chemin du fichier

## Configuration avancée

### Paramètres de fichiers

Dans le code `AppState` :

- `max_file_size` : Taille maximum des fichiers (défaut: 50MB)
- `downloads_folder` : Dossier de téléchargements
- `temp_folder` : Dossier temporaire

### Paramètres d'images

- `image_quality` : Qualité de compression (défaut: 80%)
- `max_image_width/height` : Dimensions maximum pour l'aperçu

### Paramètres réseau

- Port par défaut : 8765
- Timeout de connexion : configurable dans le code
- Retry automatique : implémenté pour la robustesse

## Support et Contribution

Cette application est un projet éducatif démontrant :

- Les principes de la cryptographie moderne
- Les réseaux peer-to-peer
- Le développement d'interfaces textuelles
- La programmation asynchrone en Python

Pour des améliorations ou des questions, consultez le code source et la documentation technique.
