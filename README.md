# Poste de travail Debian WSL2

Installer un socle DevOps configurable sur **Windows 11 x64 + Debian 13 WSL2**, ou migrer un poste existant avec ses données locales. Le provisionnement utilise PowerShell et Ansible ; il ne dépend ni de Docker Desktop, ni d’un compte cloud, ni d’un Vault personnel.

Deux profils sont disponibles :

| Profil | Usage | Fichiers privés requis |
| --- | --- | --- |
| `base` | Installation autonome pour un collègue : Zsh/Agnoster, Fzf/Fd/Bat/Rg, Micro/Vim, Git, Python, Go, Ansible, Pre-commit ; Docker Engine, Terraform, Node 24 et UV optionnels | Aucun |
| `migration` | Reprendre un poste audité, ses outils supplémentaires, certificats, configurations et services locaux | Captures `private/` et configuration personnelle ; données transférées sous chiffrement |

Le profil `base` ne déploie aucun alias personnel, démarrage Vault, configuration MCP, identité Git ou certificat d’entreprise. Les outils graphiques sont Windows Terminal, VS Code et Git for Windows. Le VPN et les logiciels gérés par l’entreprise restent à installer selon ses procédures.

## Installation autonome

### 1. Préparer Windows

Installer PowerShell 7 si nécessaire : `winget install --id Microsoft.PowerShell --exact`. Ouvrir **PowerShell 7 en administrateur**, cloner ce dépôt puis préparer WSL :

```powershell
git clone https://github.com/KRG-23/wsl2.git
cd wsl2
pwsh -File windows/bootstrap.ps1 -Stage Prerequisites
```

Si Git manque, installer d’abord `winget install --id Git.Git --exact` puis rouvrir le terminal. Si Windows demande un redémarrage, redémarrer et relancer l’étape. Exécuter les étapes suivantes avec son compte Windows habituel.

### 2. Importer une Debian isolée

Le verrou [manifests/debian-image.json](manifests/debian-image.json) contient l’URL officielle et le SHA256 de l’image Debian WSL. Depuis PowerShell :

```powershell
$lock = Get-Content manifests/debian-image.json -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force artifacts | Out-Null
Invoke-WebRequest $lock.url -OutFile artifacts/debian.wsl
pwsh -File windows/bootstrap.ps1 -Stage Import `
  -Image "$PWD/artifacts/debian.wsl" -ImageSha256 $lock.sha256 `
  -Distro Debian-Workstation
wsl -d Debian-Workstation -u root
```

Le script refuse d’écraser une distribution existante. Une importation ne crée pas d’utilisateur. Dans Debian, utiliser le dépôt Windows monté, par exemple `/mnt/c/Users/mon-compte/wsl2` :

```bash
cd /mnt/c/Users/mon-compte/wsl2
bash scripts/bootstrap-debian.sh --target-new-distro
exit
```

Depuis PowerShell, redémarrer **cette** distribution puis rouvrir un shell root :

```powershell
wsl --terminate Debian-Workstation
wsl -d Debian-Workstation -u root
```

### 3. Configurer et appliquer

Dans Debian, depuis le dépôt :

```bash
python3 scripts/configure.py --user monlogin \
  --windows-home /mnt/c/Users/mon-compte
# Relire inventory/local.yml. Exemple complet : inventory/example.yml.
ansible-playbook site.yml -e @inventory/local.yml
passwd monlogin
```

`configure.py` crée un fichier privé en mode `0600` et refuse de remplacer un fichier existant. Les options `--without docker`, `--without terraform`, `--without node`, `--without uv` désactivent leur installation. Elles ne désinstallent pas les logiciels déjà présents. Les valeurs personnelles et les paquets supplémentaires peuvent être ajoutés à `inventory/local.yml`.

Relancer la même commande Ansible pour faire converger la configuration. Depuis un utilisateur sudo, ajouter `-K`. Le provisionnement refuse un système autre que Debian 13 amd64 et exige le marqueur créé par le bootstrap du **poste cible**.

### 4. Finaliser Windows et vérifier

Fermer puis rouvrir Windows Terminal une première fois pour qu’il crée ses paramètres. Depuis PowerShell :

```powershell
pwsh -File windows/bootstrap.ps1 -Stage Configure `
  -Distro Debian-Workstation -LinuxUser monlogin
wsl --terminate Debian-Workstation
wsl -d Debian-Workstation
```

Dans Debian :

```bash
# Depuis le dépôt, sous le nouvel utilisateur ; le PATH est chargé par Zsh.
python3 scripts/verify.py --profile base --docker
```

Si un module est désactivé, adapter la vérification : `--without node`, `--without terraform`, `--without uv` et omettre `--docker` si nécessaire. Installer l’extension VS Code **Remote - WSL** côté Windows puis ouvrir les projets stockés dans le système de fichiers Linux.

Le profil Terminal utilise Cascadia Mono, Agnoster et les couleurs du poste de référence. Le réseau WSL est configuré en `mirrored`, avec proxy automatique et DNS tunneling désactivé : ces réglages reprennent le poste audité et doivent être validés avec le VPN de chaque utilisateur. `Configure` sauvegarde et fusionne les paramètres existants ; il ne redémarre pas les autres distributions.

## Migrer un poste existant

Suivre [docs/MIGRATION.md](docs/MIGRATION.md). Les étapes distinguent inventaire, capture des outils, chiffrement, restauration en staging, prévisualisation et application. Les dépôts avec modifications locales et les volumes Docker sont conservés.

Les observations de référence et leurs limites sont dans [docs/AUDIT.md](docs/AUDIT.md). Les inventaires détaillés restent dans `artifacts/`, ignoré par Git. Aucun secret du poste de référence n’est distribué avec le dépôt.

## Maintenance et validation

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap-debian.sh
zsh -n files/devops-tools.zsh
zsh -n files/migration-tools.zsh
ansible-playbook --syntax-check site.yml
pwsh -NoProfile -File tests/test-windows.ps1
```

Les tests de chiffrement exigent `age` et `age-keygen` ; ils sont ignorés si ces outils manquent. La CI les installe et vérifie aussi les fonctions de fusion PowerShell. Les tests ne provisionnent pas le poste courant. Voir [docs/MAINTENANCE.md](docs/MAINTENANCE.md) pour les verrous, les profils, les tests de recette et les limites de prise en charge.
