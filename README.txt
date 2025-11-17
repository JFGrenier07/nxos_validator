================================================================================
NX-OS VALIDATOR - Pre/Post Upgrade Validation
================================================================================

UTILISATION SIMPLE:

  1. AVANT mise à jour:
     python3 nxos_validator_simple.py
     → Choisir: 1

  2. APRÈS mise à jour:
     python3 nxos_validator_simple.py
     → Choisir: 2

================================================================================

FICHIERS GÉNÉRÉS:

  pre_validation/
    ├── spine1.txt    ← OUTPUT BRUT des commandes (comme dans le terminal)
    ├── leaf1.txt
    └── leaf2.txt

  post_validation/
    ├── spine1.txt    ← OUTPUT BRUT des commandes
    ├── leaf1.txt
    └── leaf2.txt

  comparison/
    ├── spine1_report.txt    ← Rapport de comparaison
    ├── leaf1_report.txt
    └── leaf2_report.txt

================================================================================

COMMANDES EXÉCUTÉES:

  - show version
  - show interface status
  - show ip bgp summary vrf all
  - show ip ospf neighbors vrf all
  - show cdp neighbors
  - show lldp neighbors
  - show ip route summary vrf all
  - show ip route vrf all

================================================================================

DÉTECTION D'ISSUES:

  ✓ Version changée ou pas
  ✓ Interfaces DOWN
  ✓ BGP neighbors MISSING ou DOWN (Idle/Active)
  ✓ OSPF neighbors MISSING ou NOT FULL
  ✓ CDP/LLDP neighbors MISSING
  ✓ Routes ajoutées/supprimées

================================================================================

EXEMPLE DE FICHIER PRE/POST:

  ================================================================================
  DEVICE: spine1 (192.168.0.240)
  TIMESTAMP: 2025-11-16 12:05:43
  ================================================================================

  ================================================================================
  COMMAND: show version
  ================================================================================
  Cisco Nexus Operating System (NX-OS) Software
  ...
  NXOS: version 10.3(1) [Feature Release]
  ...

  ================================================================================
  COMMAND: show interface status
  ================================================================================
  Port          Name               Status    Vlan      Duplex  Speed   Type
  Eth1/1        --                 connected routed    full    1000    10g
  ...

  → Tout le contenu BRUT des commandes, comme si tu l'avais copié-collé!

================================================================================

DÉPENDANCES:

  pip3 install paramiko PyYAML

CONFIGURATION:

  Modifier ip-device.yml pour ajouter/retirer des équipements

CLEANUP AUTOMATIQUE:

  Mode PRE  → Supprime anciens fichiers PRE
  Mode POST → Supprime anciens fichiers POST et rapports

================================================================================
