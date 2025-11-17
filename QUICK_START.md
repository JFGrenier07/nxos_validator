# Guide de démarrage rapide - NX-OS Validator

## Installation (1 minute)

```bash
cd /home/jfg/ai/nxos/nxos_update
pip install paramiko pyyaml
```

## Utilisation en 3 étapes

### ⏺️ Étape 1: Collecte PRE-UPGRADE
```bash
python3 nxos_validator_simple.py
```
- Choisir: **1**
- Username: `admin`
- Password: `****`
- ✅ Données sauvées dans `pre_validation/`

### 🔄 [Faire votre upgrade des devices]

### ⏺️ Étape 2: Collecte POST-UPGRADE
```bash
python3 nxos_validator_simple.py
```
- Choisir: **2**
- Username: `admin`
- Password: `****`
- Question: **oui** (pour comparaison)
- ✅ Rapports affichés à l'écran

### 🔍 Étape 3: Analyser les rapports
Les rapports sont affichés automatiquement et sauvés dans `comparison/`

---

## Barre de progression

Pendant la collecte, vous verrez:
```
[spine1] [========================>               ] 66% | Completed: show cdp neighbors
```

- Se met à jour dynamiquement
- Montre la progression 0% → 100%
- Affiche la commande en cours

---

## Re-comparer sans SSH (Option 3)

Si vous voulez re-générer les rapports:
```bash
python3 nxos_validator_simple.py
```
- Choisir: **3**
- ✅ Pas de SSH, utilise fichiers existants
- ✅ Rapports régénérés instantanément

---

## Que vérifie le script?

| Élément | Détection |
|---------|-----------|
| **Interfaces** | Ajout, Retrait, DOWN, VLAN changé |
| **BGP** | Neighbors DOWN, Flaps, Sessions non-Established |
| **OSPF** | Neighbors manquants, États non-FULL |
| **Routes** | Comptes par protocole, Routes ajoutées/retirées |
| **CDP/LLDP** | Neighbors disparus |
| **Version** | Changement de version |

---

## Fichiers générés

```
pre_validation/
  ├── spine1.txt          # Output RAW ~1000 lignes
  ├── leaf1.txt
  └── leaf2.txt

post_validation/
  ├── spine1.txt
  ├── leaf1.txt
  └── leaf2.txt

comparison/
  ├── spine1_report.txt   # Rapport détaillé
  ├── leaf1_report.txt
  └── leaf2_report.txt
```

---

## Symboles dans les rapports

- `!` = Problème (DOWN, MISSING)
- `~` = Changement (Flaps, VLAN modifié)
- `+` = Ajout (Interface, Route)
- `-` = Retrait (Interface, Route)

---

## Exemple de rapport

```
SUMMARY
================================================================================
ISSUES FOUND (6):
  ! Interface DOWN: Eth1/2
  ! BGP session FLAPS increased in VRF prod: 10.1.1.1 (1 -> 5)
  ! Routes REMOVED in VRF prod: 20 route(s)
```

---

## Besoin d'aide?

Consulter: `README.md` pour la documentation complète

---

**C'est tout! Le script est prêt à l'emploi.** 🚀
