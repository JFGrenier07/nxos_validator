# NX-OS Simple Validator

Script de validation pour Cisco Nexus (NX-OS) qui collecte et compare l'état du réseau avant et après une mise à niveau.

## 📋 Description

Ce script permet de:
- Collecter des données de baseline (PRE-UPGRADE)
- Collecter des données post-upgrade (POST-UPGRADE)
- Comparer automatiquement les deux états
- Identifier les changements et problèmes potentiels
- Générer des rapports détaillés lisibles

**Caractéristiques principales:**
- ✅ Stockage en texte brut (RAW command output)
- ✅ Barre de progression dynamique
- ✅ Détection complète des changements
- ✅ Rapports détaillés avec identification précise des problèmes
- ✅ Mode comparaison manuelle sans SSH

## 🔧 Prérequis

### Logiciels requis:
```bash
Python 3.6+
pip install paramiko pyyaml
```

### Fichier de configuration:
Le script nécessite un fichier `ip-device.yml` avec la liste des devices:

```yaml
devices:
  - hostname: spine1
    ip: 192.168.0.240
  - hostname: leaf1
    ip: 192.168.0.241
  - hostname: leaf2
    ip: 192.168.0.242
```

## 🚀 Utilisation

### Lancement du script:
```bash
python3 nxos_validator_simple.py
```

### Modes disponibles:

#### **Mode 1 - PRE-UPGRADE**
Collecte la baseline avant la mise à niveau.

**Actions:**
- Supprime les anciennes données PRE
- Connecte à chaque device via SSH
- Valide le hostname
- Exécute 9 commandes show avec barre de progression
- Sauvegarde les outputs RAW dans `pre_validation/`

**Utilisation:**
```
Select mode: 1
Enter SSH username: admin
Enter SSH password: ****
```

**Sortie:**
```
[spine1] [========================================>] 100% | Completed: show ip route vrf all
[spine1] Disconnected
[spine1] Data saved to pre_validation/spine1.txt
```

---

#### **Mode 2 - POST-UPGRADE**
Collecte les données après mise à niveau et compare.

**Actions:**
- Supprime les anciennes données POST
- Collecte les données (même process que PRE)
- Demande confirmation pour comparaison
- Compare PRE vs POST
- Génère les rapports dans `comparison/`
- Affiche tous les rapports à l'écran

**Utilisation:**
```
Select mode: 2
Enter SSH username: admin
Enter SSH password: ****

[Collecte en cours avec barre de progression...]

POST-UPGRADE data collection completed!

Voulez-vous faire la comparaison des fichiers? (oui/non): oui
```

---

#### **Mode 3 - COMPARE ONLY**
Compare les fichiers existants sans collecter de nouvelles données.

**Actions:**
- Vérifie que PRE et POST existent
- Compare les fichiers
- Génère les rapports
- Affiche les rapports à l'écran

**Utilisation:**
```
Select mode: 3

[MODE] COMPARE ONLY
Starting comparison...
```

**Avantages:**
- ✅ Pas besoin de credentials SSH
- ✅ Rapide (pas de connexion réseau)
- ✅ Idéal pour re-analyser après modification du script
- ✅ Permet de tester différentes analyses

## 📊 Commandes analysées

Le script exécute 9 commandes show et analyse les paramètres suivants:

| # | Commande | Analyse |
|---|----------|---------|
| 1 | `show version` | Version NX-OS uniquement |
| 2 | `show interface status` | Status, VLAN (routed/1/trunk), détection ajout/retrait |
| 3 | `show ip bgp summary vrf all` | Neighbors par VRF, état (Established/Idle/etc) |
| 4 | `show bgp sessions vrf all` | Sessions non-Established, Flaps, Neighbors manquants |
| 5 | `show ip ospf neighbors vrf all` | Neighbors par VRF, état (FULL/DOWN) |
| 6 | `show cdp neighbors` | Device-ID, Local Interface, Port ID |
| 7 | `show lldp neighbors` | Device-ID, Local Interface, Port ID |
| 8 | `show ip route summary vrf all` | Compte routes: bgp/ospf/static/direct/local par VRF |
| 9 | `show ip route vrf all` | Toutes les routes (identifie routes ajoutées/retirées) |

## 📁 Structure des fichiers

```
nxos_update/
├── nxos_validator_simple.py    # Script principal
├── ip-device.yml                # Configuration des devices
├── README.md                    # Ce fichier
├── pre_validation/              # Données PRE-UPGRADE
│   ├── spine1.txt              # ~1000 lignes de RAW output
│   ├── leaf1.txt
│   └── leaf2.txt
├── post_validation/             # Données POST-UPGRADE
│   ├── spine1.txt
│   ├── leaf1.txt
│   └── leaf2.txt
└── comparison/                  # Rapports de comparaison
    ├── spine1_report.txt
    ├── leaf1_report.txt
    └── leaf2_report.txt
```

## 📈 Rapports de comparaison

### Sections du rapport:

#### 1. VERSION
```
VERSION:
--------------------------------------------------------------------------------
  UNCHANGED: 10.3(1)
```
⚠️ Issue si version non changée après upgrade

#### 2. INTERFACES
```
INTERFACES:
--------------------------------------------------------------------------------
  INTERFACES REMOVED (1):
    ! Eth1/10
  INTERFACES ADDED (1):
    + Lo15
  INTERFACES WENT DOWN (2):
    ! Eth1/2.50: connected -> disabled
    ! Lo50: connected -> disabled
  INTERFACE VLAN CHANGED (1):
    ~ Eth1/5: VLAN 1 -> trunk
```

Détecte:
- ✅ Interfaces ajoutées
- ✅ Interfaces retirées
- ✅ Interfaces tombées (UP → DOWN)
- ✅ Changements de VLAN

#### 3. BGP NEIGHBORS
```
BGP NEIGHBORS:
--------------------------------------------------------------------------------
  VRF non-prod - MISSING (1):
    ! 10.255.1.5
  VRF non-prod - DOWN:
    ! 10.255.1.5 (Idle)
```

Détecte neighbors manquants et états non-Established

#### 4. BGP SESSIONS (Nouveau!)
```
BGP SESSIONS:
--------------------------------------------------------------------------------
  VRF non-prod:
    ! Neighbor 10.255.1.5: State=Idle
    ~ Neighbor 10.255.1.5: Flaps 1 -> 2
```

Détecte:
- ✅ Sessions non-Established (I/A/O/C/S)
- ✅ **Flaps augmentés** (reconnexions)
- ✅ Neighbors disparus

États BGP:
- **E** = Established (OK)
- **I** = Idle (Problème)
- **A** = Active (Problème)
- **O** = Open (En cours)
- **C** = Closing (Fermeture)
- **S** = Shutdown (Arrêté)

#### 5. OSPF NEIGHBORS
```
OSPF NEIGHBORS:
--------------------------------------------------------------------------------
  VRF non-prod - MISSING (1):
    ! 3.3.3.3
  VRF non-prod - NOT FULL:
    ! 2.2.2.2 (INIT)
```

Détecte neighbors manquants et états non-FULL

#### 6. CDP/LLDP NEIGHBORS
```
CDP NEIGHBORS:
--------------------------------------------------------------------------------
  OK: No CDP neighbors missing
```

Détecte neighbors disparus

#### 7. ROUTE SUMMARY (Nouveau!)
```
ROUTE SUMMARY:
--------------------------------------------------------------------------------
  VRF non-prod:
    bgp     :   20 ->   10 (-10)
    ospf    :    3 ->    2 (-1)
    static  :    0 (unchanged)
    direct  :   12 ->   11 (-1)
    local   :   12 ->   11 (-1)
```

Analyse **uniquement** ces 5 types de routes:
- bgp
- ospf
- static
- direct
- local

⚠️ Ignore les autres types (broadcast, am, etc.)

#### 8. ROUTES
```
ROUTES:
--------------------------------------------------------------------------------
  VRF non-prod:
    Total routes: 46 -> 35
    ROUTES REMOVED (11):
      - 10.255.3.5/32
      - 172.17.50.0/24
      - 172.17.51.0/24
      ...
    ROUTES ADDED (5):
      + 192.168.100.0/24
      + 192.168.101.0/24
      ...
```

Liste **toutes les routes** ajoutées/retirées avec leurs préfixes exacts

#### 9. SUMMARY
```
SUMMARY
================================================================================
ISSUES FOUND (10):
  ! Version NOT changed - still 10.3(1)
  ! Interface DOWN: Lo50
  ! Interface ADDED: Lo15
  ! BGP neighbor DOWN in VRF non-prod: 10.255.1.5
  ! BGP session FLAPS increased in VRF non-prod: 10.255.1.5 (1 -> 2)
  ! Route count changed in VRF non-prod: bgp (20 -> 0)
  ! Routes REMOVED in VRF non-prod: 21 route(s)
```

Résumé de **tous les problèmes** détectés

## 🎯 Scénarios d'utilisation

### Scénario 1: Upgrade complète
```bash
# Avant l'upgrade
python3 nxos_validator_simple.py
> Choisir mode 1 (PRE-UPGRADE)

# [Effectuer l'upgrade des devices]

# Après l'upgrade
python3 nxos_validator_simple.py
> Choisir mode 2 (POST-UPGRADE)
> Répondre "oui" à la comparaison
> Analyser les rapports affichés
```

### Scénario 2: Re-analyse après correction du script
```bash
# Vous avez déjà PRE et POST, mais le script a été amélioré
python3 nxos_validator_simple.py
> Choisir mode 3 (COMPARE ONLY)
> Pas besoin de SSH
> Nouveaux rapports générés instantanément
```

### Scénario 3: Collecte POST sans comparaison immédiate
```bash
python3 nxos_validator_simple.py
> Choisir mode 2 (POST-UPGRADE)
> Répondre "non" à la comparaison
> Données POST sauvegardées

# Plus tard, faire la comparaison
python3 nxos_validator_simple.py
> Choisir mode 3 (COMPARE ONLY)
```

## 🔍 Interprétation des symboles

Dans les rapports:
- `!` = Problème critique (down, missing, error)
- `~` = Changement (modification, flaps)
- `+` = Ajout (nouvelle interface, route ajoutée)
- `-` = Retrait (interface supprimée, route retirée)

## ⚙️ Configuration avancée

### Modifier les commandes analysées

Éditer la liste `COMMANDS` dans le script (ligne 20-30):
```python
COMMANDS = [
    "show version",
    "show interface status",
    # Ajouter vos commandes ici
]
```

### Ajuster la barre de progression

Modifier `bar_length` dans `print_progress_bar()` (ligne 152):
```python
def print_progress_bar(self, current, total, cmd, hostname, bar_length=40):
    # bar_length=60 pour une barre plus longue
```

## 🐛 Dépannage

### Erreur: "No PRE data found"
**Cause:** Mode POST ou COMPARE sans avoir fait PRE d'abord
**Solution:** Exécuter mode 1 (PRE-UPGRADE) avant

### Erreur: "Hostname mismatch"
**Cause:** Le hostname retourné par le device ne correspond pas à `ip-device.yml`
**Solution:** Vérifier le hostname dans le fichier YAML (peut contenir domaine: spine1.cisco.com)

### Caractères résiduels dans la barre de progression
**Cause:** Terminal trop petit
**Solution:** La ligne est paddée à 120 caractères. Agrandir le terminal ou réduire `bar_length`

### Pas de connexion SSH
**Cause:** Credentials incorrects ou connectivité réseau
**Solution:**
- Vérifier username/password
- Tester manuellement: `ssh admin@192.168.0.240`
- Vérifier les IPs dans `ip-device.yml`

### Script lent pendant "show ip route vrf all"
**Cause:** Commande avec beaucoup de routes (normal)
**Solution:** Patience, la barre de progression montre l'avancement

## 📝 Notes importantes

1. **Stockage RAW:** Les fichiers contiennent les outputs complets des commandes (format texte lisible)
2. **Nettoyage automatique:** PRE supprime old PRE, POST supprime old POST
3. **Validation hostname:** Le script vérifie que vous êtes connecté au bon device
4. **Terminal length 0:** Désactive la pagination pour capturer 100% du output
5. **Timeout:** 60 secondes par commande (configurable)

## 📞 Support

Pour toute question ou amélioration:
1. Vérifier ce README
2. Consulter les commentaires dans le code
3. Tester en mode 3 (COMPARE ONLY) pour debug rapide

## 🎓 Exemples de rapports

### Exemple 1: Tout OK
```
SUMMARY
================================================================================
ISSUES FOUND (1):
  ! Version NOT changed - still 10.3(1)
```
Seul "problème": version non changée (attendu si pas d'upgrade)

### Exemple 2: Problèmes réseau
```
SUMMARY
================================================================================
ISSUES FOUND (8):
  ! Interface DOWN: Eth1/2
  ! BGP neighbor DOWN in VRF prod: 10.1.1.1
  ! BGP session FLAPS increased in VRF prod: 10.1.1.1 (0 -> 5)
  ! OSPF neighbor MISSING in VRF prod: 2.2.2.2
  ! Routes REMOVED in VRF prod: 50 route(s)
```
Problèmes sérieux nécessitant investigation

## 📜 Historique des versions

### v2.0 (Actuel)
- ✅ Barre de progression dynamique
- ✅ Détection ajout/retrait interfaces
- ✅ Analyse BGP sessions avec flaps
- ✅ Route summary (bgp/ospf/static/direct/local)
- ✅ Mode COMPARE ONLY
- ✅ Confirmation avant comparaison
- ✅ Identification exacte des routes ajoutées/retirées

### v1.0 (Initial)
- Collecte et comparaison basique
- Stockage JSON (obsolète)

---

**Script créé pour simplifier la validation des mises à niveau NX-OS**
**Format RAW, analyse complète, rapports détaillés** 🚀
