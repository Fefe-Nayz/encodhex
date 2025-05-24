# EncodHex - Problèmes UI à résoudre

## 🚨 Problèmes Critiques Actuels

### 1. **Modal Contacts - Hauteur insuffisante**

**Statut:** ❌ Non résolu (malgré augmentation de 90% → 95%)
**Description:** Le modal des contacts reste trop petit, causant des éléments coupés
**Fichier:** `tui_app.py` - ContactManagerModal CSS
**Ligne:** ~963 (`#contact_dialog`)

**Solutions à essayer:**

- [ ] Augmenter à 98% ou utiliser une hauteur fixe plus grande
- [ ] Modifier `max-height: 45` vers `max-height: 50`
- [ ] Ajuster les hauteurs internes des conteneurs (`#form_area`, `#content_area`)
- [ ] Utiliser `height: auto` avec `min-height`

```css
#contact_dialog {
  width: 95%;
  height: 98%; // OU height: auto; min-height: 40;
  max-width: 120;
  max-height: 50; // Augmenté de 45
}
```

### 2. **Footer Bindings - Raccourcis invisibles**

**Statut:** ❌ Non résolu
**Description:** Les raccourcis contextuel ne s'affichent pas dans le footer malgré les modifications
**Fichier:** `tui_app.py` - méthode `_update_footer_bindings()`
**Ligne:** ~2124

**Cause probable:** Textual ne permet pas la modification dynamique des BINDINGS après initialisation

**Solutions à essayer:**

- [ ] Utiliser une approche avec `watch` sur `app_state_ui`
- [ ] Implémenter un Custom Footer Widget
- [ ] Utiliser la méthode `refresh_bindings()` si disponible
- [ ] Créer des bindings conditionnels dans la méthode `on_key`

```python
# Solution Alternative - Custom Footer
class DynamicFooter(Footer):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

    def get_bindings(self):
        # Retourner bindings selon app_state_ui
        pass
```

### 3. **Modal Contacts - Inaccessible en configuration**

**Statut:** ❌ Nouvelle régression
**Description:** Le modal contacts ne s'ouvre plus depuis le menu de configuration
**Fichier:** `tui_app.py` - méthode `action_manage_contacts()`
**Ligne:** ~3215

**Diagnostic requis:**

- [ ] Vérifier la condition dans `action_manage_contacts()`
- [ ] Tester si l'erreur se produit dans tous les états de config
- [ ] Vérifier les logs d'erreur

```python
# Condition actuelle à vérifier
if self.app_state_ui in ["setup_mode", "setup_target_ip", "setup_target_port", "conversation"]:
    self.push_screen(ContactManagerModal())
```

### 4. **Boutons - Décalage persistant**

**Statut:** ⚠️ Partiellement résolu
**Description:** Certains boutons ont encore un décalage/alignement incorrect
**Fichiers:** Plusieurs modales CSS

**Zones à vérifier:**

- [ ] ContactManagerModal - boutons action (`#button_area`)
- [ ] FileBrowserModal - boutons filtres
- [ ] Alignement vertical des conteneurs de boutons

## 📋 Problèmes Résolus

### ✅ 1. Boutons trop petits

- Ajouté `height: 3` à tous les boutons
- Ajouté `min-width` appropriées selon le contexte

### ✅ 2. Form area hauteur

- Augmenté `#form_area` de `height: 10` à `height: 15`

## 🔧 Plan d'Action Prioritaire

### Étape 1: Footer Bindings (Critique)

1. Tester approche avec Custom Footer Widget
2. Si échec, implémenter logique dans `on_key()` avec indicateurs visuels
3. Alternative: Label statique avec raccourcis contextuels

### Étape 2: Modal Contacts Hauteur

1. Tester hauteur 98% + max-height 50
2. Ajuster hauteurs internes des sous-conteneurs
3. Tester sur différentes tailles d'écran

### Étape 3: Accès Modal Configuration

1. Debug condition `action_manage_contacts()`
2. Ajouter logs pour identifier l'état exact
3. Corriger la logique de disponibilité

### Étape 4: Alignement Boutons

1. Audit CSS de tous les conteneurs de boutons
2. Standardiser les styles d'alignement
3. Tester responsive design

## 🧪 Tests à Effectuer

**Après chaque correction:**

- [ ] Test sur écran petit (80x24)
- [ ] Test sur écran moyen (120x40)
- [ ] Test sur grand écran (200x60)
- [ ] Navigation complète: Welcome → Config → Conversation
- [ ] Test de tous les modales (Contacts, Files, Downloads)
- [ ] Vérification raccourcis clavier dans chaque état

## 📊 Métriques de Succès

**Modal Contacts:**

- [ ] Tous les éléments visibles sans scroll
- [ ] Boutons cliquables et non coupés
- [ ] Accessible depuis configuration

**Footer:**

- [ ] Raccourcis visibles selon contexte
- [ ] Quit toujours visible
- [ ] Contacts visible après port setup
- [ ] Tous raccourcis visible en conversation

**Navigation:**

- [ ] Aucune régression dans l'ouverture des modales
- [ ] Pas d'erreurs JavaScript/Python
- [ ] Interface responsive et professionnelle

---

_Document créé le: $(date)_
_Dernière mise à jour: À mettre à jour après chaque session de debugging_
