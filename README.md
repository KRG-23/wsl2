# Poste de travail Debian WSL2

Installer un socle DevOps configurable sur **Windows 11 x64 + Debian 13 WSL2**, ou migrer un poste existant avec ses données locales. Le provisionnement utilise PowerShell et Ansible ; il ne dépend ni de Docker Desktop, ni d’un compte cloud, ni d’un Vault personnel.

Deux profils sont disponibles :

| Profil | Usage | Fichiers privés requis |
| --- | --- | --- |
| `base` | Installation autonome pour un collègue : Zsh/Agnoster, Fzf/Fd/Bat/Rg, Dust, Zoxide (`z`/`zi`), Micro/Vim, Git, Python, Go, Ansible, Pre-commit ; Docker Engine, Terraform, Node 24 et UV optionnels | Aucun |
| `migration` | Reprendre un poste audité, ses outils supplémentaires, certificats, configurations et services locaux | Captures `private/` et configuration personnelle ; données transférées sous chiffrement |

Le profil `base` ne déploie aucun alias personnel, démarrage Vault, configuration MCP, identité Git ou certificat d’entreprise. Les outils graphiques sont Windows Terminal, VS Code et Git for Windows. Le VPN et les logiciels gérés par l’entreprise restent à installer selon ses procédures.

Dust et Zoxide sont installés dans les deux profils via les paquets Debian 13
[`du-dust`](https://packages.debian.org/trixie/du-dust) et
[`zoxide`](https://packages.debian.org/trixie/zoxide). La commande est `dust` ;
Zoxide est initialisé en fin de configuration Zsh pour fournir `z` et `zi`.
Visiter d’abord les dossiers avec `cd` pour alimenter son historique.

## Installation autonome : suivre les étapes dans l’ordre

Commencer par le **[guide d’installation pas à pas](docs/INSTALLATION.md)**.
Il indique pour chaque étape le terminal, les droits, le répertoire courant,
les commandes, le résultat attendu et le point de reprise après un redémarrage.
Le nom de distribution utilisé est **`Debian`**.

| Ordre | Où ? | Objectif |
| --- | --- | --- |
| 1 | Windows, compte habituel | Installer Git, PowerShell 7, Windows Terminal et VS Code |
| 2 | PowerShell 7 administrateur | Installer/mettre à jour WSL ; redémarrer Windows si demandé |
| 3 | PowerShell 7, compte habituel | Récupérer la bonne version du dépôt et ouvrir un journal |
| 4 | PowerShell 7, compte habituel | Importer Debian ou vérifier la Debian cible déjà présente |
| 5 | Debian, `root` | Exécuter le bootstrap Linux |
| 6 | PowerShell puis Debian `root` | Redémarrer Debian et contrôler systemd |
| 7 | Debian, `root` | Copier le code dans `/opt/wsl2` sur le système de fichiers Linux |
| 8 | Debian, `root`, `/opt/wsl2` | Choisir le login et créer/relire `local.yml` |
| 9 | Debian, `root`, `/opt/wsl2` | Contrôler l’inventaire, appliquer Ansible, définir le mot de passe et vérifier la convergence |
| 10 | PowerShell 7, compte habituel | Reconnecter l’utilisateur Linux et configurer Terminal/WSL |
| 11 | Debian, utilisateur normal | Vérifier les outils, Docker et VS Code Remote–WSL |

Le parcours détaillé donne les commandes Windows individuellement : il ne
nécessite pas que `windows/bootstrap.ps1 -Stage Prerequisites` fonctionne sur
le poste. Le script PowerShell reste une option, avec une solution manuelle pour
les paramètres de Terminal et du réseau.

**`inventory/local.yml` est un fichier de surcharges, pas une configuration
exhaustive du rôle.** Les valeurs communes viennent de
`inventory/group_vars/all.yml`, chargé avec l’inventaire `inventory/hosts.yml`.
Les commandes documentées passent donc toujours cet inventaire explicitement :

```bash
# Dans Debian, après le bootstrap et les contrôles du guide, depuis /opt/wsl2.
ANSIBLE_CONFIG=/opt/wsl2/ansible.cfg \
  ansible-playbook -i inventory/hosts.yml site.yml -e @inventory/local.yml
```

Ne pas compenser un inventaire non chargé en recopiant toutes les variables du
rôle dans `local.yml`. Le guide fournit un contrôle des variables avant toute
application. Pour reprendre un essai interrompu ou comprendre une erreur, voir
le [dépannage](docs/DEPANNAGE.md).

## Migrer un poste existant

Suivre [docs/MIGRATION.md](docs/MIGRATION.md). Les étapes distinguent inventaire, capture des outils, chiffrement, restauration en staging, prévisualisation et application. Les dépôts avec modifications locales et les volumes Docker sont conservés.

Les observations de référence et leurs limites sont dans [docs/AUDIT.md](docs/AUDIT.md). Les inventaires détaillés restent dans `artifacts/`, ignoré par Git. Aucun secret du poste de référence n’est distribué avec le dépôt.

## Maintenance et validation

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap-debian.sh
zsh -n files/devops-tools.zsh
zsh -n files/migration-tools.zsh
ansible-playbook -i inventory/hosts.yml --syntax-check site.yml
pwsh -NoProfile -File tests/test-windows.ps1
```

Les tests de chiffrement exigent `age` et `age-keygen` ; ils sont ignorés si ces outils manquent. La CI les installe et vérifie aussi les fonctions de fusion PowerShell. Les tests ne provisionnent pas le poste courant. Voir [docs/MAINTENANCE.md](docs/MAINTENANCE.md) pour les verrous, les profils, les tests de recette et les limites de prise en charge.
