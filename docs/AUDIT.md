# Audit du poste de référence — 3 novembre 2026

Ce document ne contient que des observations publiables. Les chemins internes, noms de dépôts professionnels, identités, certificats et inventaires détaillés restent hors Git.

## Comparaison vérifiée

| Élément | Poste source | Image officielle WSL |
| --- | --- | --- |
| Distribution | Debian 13 Trixie, base-files indiquant 13.7 | Debian 13 Trixie, image indiquant 13.5 |
| Architecture | amd64 | amd64 |
| Paquets installés | 923 | 157 |
| Différentiel | 767 supplémentaires, 1 absent, 40 versions différentes | Référence avant premier démarrage |

Image : Debian WSL AMD64 `1.26.0.0`, publiée via le [catalogue Microsoft WSL](https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json), provenant de Debian Salsa. URL et SHA256 sont verrouillés dans `manifests/debian-image.json`. Le téléchargement a été vérifié ; l’inventaire provient directement de `var/lib/dpkg/status`, sans lancer l’image.

Une différence de version n’est pas une personnalisation. L’image n’a pas été mise à jour au même niveau que la source. Le comparateur distingue donc les paquets ajoutés des changements de versions, sans transformer automatiquement les 767 ajouts en exigences d’installation.

Le collecteur a identifié 234 espaces Git et 138 avec changements suivis ou fichiers non suivis. Ces nombres portent sur les chemins explorés et ne prouvent pas la disponibilité des dépôts distants. Ils justifient le transfert des espaces de travail complets.

## Personnalisations observées

- Zsh par défaut ; Oh My Zsh/Agnoster ; Git/Fzf ; fonctions de navigation, recherche et édition ; couleurs par extension ; Micro et Vim.
- Windows Terminal : police Powerline, taille 14, couleurs et image de fond ; extensions VS Code réparties entre Windows et WSL.
- Ansible, Terraform, Go, Node, Python, outils cloud et MCP ; binaires hors APT et outils npm/pipx. Python 3.12 local coexiste avec Python 3.13 Debian.
- Docker Engine avec paquets encore étiquetés Bookworm, et traces de Docker Desktop ; démarrage via une commande WSL. La cible utilise le dépôt Docker Trixie et systemd.
- Les liens `kubectl` et `cagent` vers Docker Desktop sont cassés sur la source ; ils ne sont pas reproduits comme outils fonctionnels.
- Réseau mirrored, proxy automatique et DNS tunneling désactivé ; liens cloud vers Windows ; Git for Windows utilisé pour certains accès réseau.
- CA d’entreprise, certificats privés et clés SSH/GPG ; Vault local et services de supervision démarrés depuis des scripts personnels.
- Informix/ODBC et GSK installés hors du socle Debian.

Les fichiers Bash ont aussi été comparés aux modèles `/etc/skel` : variables Bedrock/région AWS et chargement de l’environnement local sont des ajouts explicites. Les définitions Fzf et ajouts PATH répétés ont été regroupés dans la configuration cible.

## Vérifications après redémarrage

L’accès au daemon Docker a été vérifié en lecture seule après le redémarrage : 13 conteneurs actifs et 12 volumes locaux étaient visibles. Ils couvrent notamment Vault, supervision, synchronisation et PostgreSQL. Aucun conteneur n’a été arrêté par l’implémentation. Les données des volumes n’ont pas été sauvegardées pendant cette session de développement.

Treize captures privées d’outils/runtimes ont été produites, dont Informix/GSK, sans élément déclaré manquant. Les archives sont locales et ne font pas partie du dépôt public. Les configurations et bases sensibles doivent encore être sauvegardées sous chiffrement au moment de la migration, applications arrêtées.
