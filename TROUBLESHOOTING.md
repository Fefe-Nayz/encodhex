# 🔧 Guide de Dépannage EncodHex

## 🚨 Problèmes Courants et Solutions

### 1. L'application ne démarre pas

**Symptômes :** Erreurs d'import ou crash au démarrage
**Solutions :**

```bash
# Vérifier les dépendances
pip install textual websockets pillow rich-pixels

# Tester le démarrage
python test_startup.py

# Si ça échoue, vérifier Python
python --version  # Doit être 3.8+
```

### 2. Erreur "Port déjà utilisé"

**Symptômes :** `OSError: [Errno 10048] Only one usage of each socket address`
**Solutions :**

- L'application essaiera automatiquement les ports suivants
- Ou spécifiez un port différent lors de la configuration
- Vérifiez qu'aucune autre instance n'est en cours

### 3. Impossible de se connecter à un peer

**Symptômes :** "Échec de connexion" ou timeout
**Solutions :**

1. Vérifiez l'IP et le port du peer
2. Assurez-vous que le firewall autorise la connexion
3. Le peer doit être en mode "attente" (choix 'n')
4. Testez avec `telnet IP PORT` pour vérifier la connectivité

### 4. Les raccourcis clavier ne fonctionnent pas

**Symptômes :** F5, Ctrl+K, etc. ne répondent pas
**Solutions :**

- Les raccourcis ne fonctionnent qu'en mode conversation
- Assurez-vous d'être connecté à au moins un peer
- Essayez les boutons de l'interface à la place

### 5. Erreur lors du partage de fichiers

**Symptômes :** "Fichier trop volumineux" ou crash
**Solutions :**

- Limite : 50MB par fichier
- Vérifiez que le fichier existe et est lisible
- Pour les images, formats supportés : PNG, JPG, GIF, BMP, WEBP

### 6. Les contacts ne se sauvegardent pas

**Symptômes :** Contacts perdus au redémarrage
**Solutions :**

```bash
# Vérifier les permissions du dossier
ls -la data/
# Doit contenir contacts.json

# Créer le dossier si nécessaire
mkdir -p data
```

### 7. Problèmes de chiffrement

**Symptômes :** Messages non déchiffrés ou erreurs DH
**Solutions :**

- Redémarrez les deux applications
- Vérifiez que les modules `aes/` et `diffie_hellman/` sont présents
- L'échange de clés peut prendre quelques secondes

### 8. Interface corrompue ou illisible

**Symptômes :** Affichage bizarre, caractères manquants
**Solutions :**

```bash
# Redimensionner le terminal
# Minimum recommandé : 80x25

# Vérifier l'encodage
export PYTHONIOENCODING=utf-8

# Terminal Windows : utiliser Windows Terminal ou PowerShell 7
```

## 🔍 Diagnostic Avancé

### Vérification des Modules

```bash
python -c "from aes.encryption import encrypt; print('AES OK')"
python -c "from diffie_hellman.diffie_hellman import generate_parameters; print('DH OK')"
python -c "from textual.app import App; print('Textual OK')"
```

### Test de Connectivité Réseau

```bash
# Tester si le port est ouvert
netstat -an | grep :8765

# Tester la connexion (remplacez IP)
telnet 192.168.1.100 8765
```

### Logs de Debug

Pour activer les logs détaillés, modifiez temporairement `tui_app.py` :

```python
# Ajoutez en haut du fichier
import logging
logging.basicConfig(level=logging.DEBUG, filename='encodhex.log')
```

## 📱 Compatibilité

### Systèmes Supportés

- ✅ Windows 10/11
- ✅ macOS 10.15+
- ✅ Linux (Ubuntu 20.04+)

### Versions Python

- ✅ Python 3.8+
- ✅ Python 3.9 (recommandé)
- ✅ Python 3.10+
- ❌ Python 3.7 et antérieurs

### Terminaux Recommandés

- ✅ Windows Terminal
- ✅ PowerShell 7
- ✅ macOS Terminal
- ✅ Linux Terminal (gnome-terminal, konsole, etc.)
- ⚠️ CMD Windows (limité)

## 🆘 Support d'Urgence

Si rien ne fonctionne :

1. **Sauvegardez vos données :**

   ```bash
   cp -r data/ data_backup/
   cp -r conversations/ conversations_backup/
   ```

2. **Réinitialisez l'application :**

   ```bash
   rm -rf data/ conversations/ temp/ downloads/
   python tui_app.py
   ```

3. **Testez avec une configuration minimale :**

   - Utilisez les ports par défaut
   - Testez en local (127.0.0.1)
   - Désactivez temporairement le firewall

4. **Vérifiez l'intégrité des fichiers :**
   ```bash
   python test_startup.py
   ```

## 📞 Obtenir de l'Aide

Si les problèmes persistent :

1. Exécutez `python test_startup.py` et notez les erreurs
2. Vérifiez le fichier `encodhex.log` si activé
3. Notez votre système d'exploitation et version Python
4. Décrivez précisément les étapes qui causent le problème

L'application est conçue pour être robuste, la plupart des problèmes sont liés à la configuration réseau ou aux dépendances manquantes.
