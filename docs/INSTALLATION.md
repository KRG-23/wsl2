# Installation pas à pas — Windows 11 et Debian 13

Ce parcours installe le profil **`base`** sur le nouveau PC. La distribution doit
s’appeler **`Debian`**. Pour transférer aussi les données et outils privés du
poste précédent, choisir plutôt le [guide de migration](MIGRATION.md), dont la
préparation de la cible remplace les étapes Ansible du profil `base`.

Exécuter les étapes dans l’ordre. Ne passer au bloc suivant que lorsque le
résultat attendu est obtenu. Une erreur ne justifie pas de réimporter ou de
supprimer Debian : utiliser les [points de reprise](DEPANNAGE.md).

## Repères avant de commencer

| Élément | Emplacement ou valeur |
| --- | --- |
| Distribution WSL | `Debian`, en version WSL **2**, Debian **13 amd64** |
| Dépôt Windows | `%USERPROFILE%\wsl2` : téléchargement et commandes Windows |
| Code d’installation Linux | `/opt/wsl2` : copie utilisée pour Ansible |
| Configuration réellement appliquée | `/opt/wsl2/inventory/local.yml` |
| Inventaire Ansible | `/opt/wsl2/inventory/hosts.yml` |
| Valeurs communes du rôle | `/opt/wsl2/inventory/group_vars/all.yml` |
| Utilisateur Linux | À choisir ; les exemples utilisent `monlogin` |

Le compte Windows et le login Linux sont deux identités différentes. Le nom du
dossier `C:\Users\...` peut encore être différent du nom affiché à la connexion.
Les chemins Windows seront convertis à l’étape 4 ; ne pas les deviner.

Les variables PowerShell ou Bash disparaissent à la fermeture d’un terminal ou
au redémarrage. Les blocs ci-dessous réinitialisent celles dont ils ont besoin.
Ne pas coller les délimiteurs Markdown ni le texte des résultats attendus dans
le terminal.

## 1. Installer les outils Windows

**Terminal : Windows PowerShell ou PowerShell, sous le compte Windows habituel.**

```powershell
winget --version
```

Si WinGet manque, faire installer **App Installer**, Git, PowerShell 7, Windows
Terminal et VS Code par le canal autorisé sur le poste. Ne pas continuer avec
des commandes introuvables.

Exécuter séparément les installations manquantes :

```powershell
winget install --id Git.Git --exact --source winget
winget install --id Microsoft.PowerShell --exact --source winget
winget install --id Microsoft.WindowsTerminal --exact --source winget
winget install --id Microsoft.VisualStudioCode --exact --source winget
```

Si une application est déjà installée et qu’aucune mise à jour n’est applicable,
la conserver. Pour toute autre erreur, noter le message et arrêter cette étape.
Les commandes WinGet ne sont pas exécutées par `bootstrap.ps1` dans ce parcours.

**Fermer le terminal**, ouvrir **PowerShell 7** depuis le menu Démarrer et contrôler :

```powershell
$PSVersionTable.PSVersion
git --version
Get-Command pwsh
Get-Command wt.exe, code
```

**Attendu :** PowerShell **7.2 ou supérieur**, Git reconnu et `pwsh` disponible.
L’installation de PowerShell 7 ne remplace pas Windows PowerShell 5.1 : choisir
le bon terminal. [Installation officielle PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows).

## 2. Préparer WSL avec les droits administrateur

**Terminal : nouvelle fenêtre PowerShell 7, « Exécuter en tant qu’administrateur ».**

Si WSL n’est pas encore installé :

```powershell
wsl --install --no-distribution
$LASTEXITCODE
```

Cette commande prépare WSL sans installer une seconde distribution. Si Windows
demande un redémarrage, **redémarrer Windows maintenant**, même si le code vaut
`0`. Les codes d’installation `3010` ou `1641` signalent également un redémarrage ;
pour un autre code non nul, conserver l’erreur et consulter le dépannage.

Après le redémarrage, rouvrir **PowerShell 7 administrateur**, puis exécuter :

```powershell
wsl --update
```

Après succès seulement :

```powershell
wsl --set-default-version 2
wsl --version
wsl --status
```

**Attendu :** WSL répond et la version par défaut est `2`. Une erreur de
virtualisation ou de fonctionnalité Windows doit être résolue avant l’import.
Si WSL fonctionnait déjà en version 2, conserver l’installation et vérifier
simplement ces commandes. [Commandes officielles WSL](https://learn.microsoft.com/en-us/windows/wsl/basic-commands).

**Fermer la fenêtre administrateur.** La suite, dont l’import, se fait avec le
compte Windows habituel : une distribution WSL est enregistrée pour ce compte.

## 3. Récupérer le dépôt et ouvrir un journal Windows

**Terminal : PowerShell 7 normal, compte Windows habituel.**

```powershell
$ErrorActionPreference = 'Stop'
$repoWindows = Join-Path $env:USERPROFILE 'wsl2'
```

Si le dossier n’existe pas :

```powershell
git clone https://github.com/KRG-23/wsl2.git $repoWindows
if ($LASTEXITCODE -ne 0) { throw 'Échec du clone : ne pas continuer.' }
```

S’il existe déjà, utiliser la copie prévue pour cet essai. Ne pas la supprimer ni
écraser ses changements locaux pour résoudre une erreur d’installation.

```powershell
Set-Location -LiteralPath $repoWindows
git rev-parse HEAD
git status --short
Test-Path .\scripts\bootstrap-debian.sh
Test-Path .\inventory\group_vars\all.yml
```

**Attendu :** les deux `Test-Path` renvoient `True`. Conserver le SHA Git avec le
compte rendu ; si `git status` montre des modifications locales, elles font aussi
partie de la version testée. Un clone sur un autre PC ne récupère pas les
modifications non publiées : transférer ou publier la bonne copie avant l’essai.

```powershell
New-Item -ItemType Directory -Force .\artifacts | Out-Null
$journalWindows = Join-Path $repoWindows ('artifacts\installation-windows-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
Start-Transcript -Path $journalWindows
```

Le journal reste privé et ignoré par Git. Le relire avant de le partager.

## 4. Importer Debian, ou identifier la Debian cible déjà présente

**Terminal : même PowerShell 7 normal, dans le dépôt Windows.**

```powershell
wsl --list --verbose
```

### Si `Debian` n’existe pas

```powershell
$repoWindows = Join-Path $env:USERPROFILE 'wsl2'
Set-Location -LiteralPath $repoWindows
$lock = Get-Content .\manifests\debian-image.json -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force .\artifacts | Out-Null
$imagePath = Join-Path $repoWindows 'artifacts\debian.wsl'
if (-not (Test-Path -LiteralPath $imagePath)) {
    Invoke-WebRequest -Uri $lock.url -OutFile $imagePath
}
if ((Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $lock.sha256.ToLowerInvariant()) {
    throw 'Image non conforme : ne pas importer. Voir le dépannage SHA256.'
}
$installLocation = Join-Path $env:LOCALAPPDATA 'WSL\Debian'
wsl --import Debian $installLocation $imagePath --version 2
if ($LASTEXITCODE -ne 0) { throw 'Import Debian en échec : conserver le message.' }
wsl --list --verbose
```

**Attendu :** une ligne nommée `Debian` avec la colonne `VERSION` à `2`.
L’image est vérifiée avant l’import. Ne pas exécuter aussi `wsl --install -d Debian`.

### Si `Debian` existe déjà

Ne pas relancer l’import. Contrôler que c’est bien la distribution choisie comme
cible sur le nouveau PC :

```powershell
wsl -d Debian -u root -- cat /etc/os-release
wsl -d Debian -u root -- uname -m
```

**Attendu :** Debian `VERSION_ID="13"`, architecture `x86_64`, WSL version `2`
dans la liste précédente. Si elle contient déjà des données, les sauvegarder
avant son provisionnement. Si elle appartient au poste source à migrer, ne pas
continuer cette procédure dessus. `-AllowExistingDistro` ne remet pas une
distribution à neuf ; il ne fait que sauter l’import.

### Afficher les chemins pour la prochaine étape

```powershell
$repoWindows = Join-Path $env:USERPROFILE 'wsl2'
wsl -d Debian -u root -- wslpath -u $repoWindows
wsl -d Debian -u root -- wslpath -u $env:USERPROFILE
Stop-Transcript
wsl -d Debian -u root
```

Noter les deux chemins affichés, par exemple `/mnt/c/Users/Alice Smith/wsl2`
et `/mnt/c/Users/Alice Smith`. Le dernier appel ouvre **un shell Linux root** ;
les commandes suivantes ne sont plus des commandes PowerShell.

## 5. Exécuter le bootstrap Debian

**Terminal : Debian, utilisateur `root`. Répertoire : copie Windows montée.**

Remplacer le chemin ci-dessous par le premier chemin affiché à l’étape 4 :

```bash
whoami
repo_windows='/mnt/c/Users/TON_COMPTE_WINDOWS/wsl2'
cd -- "$repo_windows"
pwd
bash scripts/bootstrap-debian.sh --target-new-distro && echo 'Bootstrap Debian terminé.'
```

**Attendu :** `whoami` affiche `root`, les opérations APT réussissent et la phrase
`Bootstrap Debian terminé.` apparaît. Le script installe notamment Ansible,
Python/PyYAML, rsync, Zsh et systemd, écrit `/etc/wsl.conf` et crée le marqueur de
bootstrap. Aucun utilisateur de travail n’est encore créé par ce script.

Si APT échoue, rester à cette étape : ne pas créer manuellement le marqueur pour
contourner l’erreur. Après succès, contrôler puis quitter Debian :

```bash
test -f /var/lib/wsl2-workstation/bootstrap-ready && echo 'Marqueur présent.'
cat /etc/wsl.conf
exit
```

**Attendu :** marqueur présent et section `[boot]` contenant `systemd = true`.

## 6. Redémarrer Debian avant Ansible

**Terminal : retour dans PowerShell 7 normal.**

```powershell
wsl --terminate Debian
wsl -d Debian -u root
```

**Terminal : nouveau shell Debian root.**

```bash
whoami
cat /proc/1/comm
test -f /var/lib/wsl2-workstation/bootstrap-ready && echo 'Marqueur présent.'
python3 -c "import yaml; print('Python et PyYAML disponibles.')"
```

**Attendu :** `root`, `systemd`, marqueur présent et import PyYAML réussi.
Si PID 1 n’est pas `systemd`, utiliser la procédure du dépannage avant de
continuer. Le redémarrage est une étape fonctionnelle, pas une simple reconnexion.
[Prérequis systemd de WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## 7. Copier le code d’installation sur le système de fichiers Linux

**Terminal : Debian root.** Redéfinir le chemin, car le terminal a été rouvert :

```bash
repo_windows='/mnt/c/Users/TON_COMPTE_WINDOWS/wsl2'
install -d -m 0755 /opt/wsl2
rsync -a --no-owner --no-group --chmod=D755,F644 \
  --exclude='/.git/' --exclude='/artifacts/' --exclude='/private/' \
  --exclude='/inventory/local.yml' --exclude='/.venv/' \
  --exclude='__pycache__/' \
  "$repo_windows/" /opt/wsl2/
cd /opt/wsl2
pwd
```

**Attendu :** `/opt/wsl2`. Cette copie conserve le code de l’essai, y compris ses
modifications non publiées, mais pas Git, les captures privées, les grosses
archives ou la configuration personnelle d’une autre installation.
Si `/opt/wsl2/inventory/local.yml` existe après un essai précédent, rsync le conserve.

**À partir de maintenant, Ansible s’exécute uniquement dans cette copie Linux.**
Sur un dossier Windows monté avec des droits trop ouverts, Ansible peut ignorer
`ansible.cfg`. Le paramètre `-i` restera explicite pour charger les valeurs communes.
[Comportement documenté d’Ansible](https://docs.ansible.com/ansible/latest/reference_appendices/config.html#avoiding-security-risks-with-ansible-cfg-in-the-current-directory).

## 8. Choisir l’utilisateur et créer les surcharges locales

**Terminal : Debian root, répertoire `/opt/wsl2`.**

```bash
getent passwd 1000
getent group 1000
```

Sur une image importée sans compte utilisateur, ces commandes peuvent ne rien
afficher. Si l’UID/GID 1000 est déjà attribué, réutiliser le login/groupe existant
ou adapter les UID/GID dans la configuration ; ne pas créer un deuxième compte
avec ces mêmes identifiants.

Choisir le login réel avant d’exécuter le bloc ; `monlogin` est un exemple :

```bash
cd /opt/wsl2
linux_login='monlogin'
windows_profile='/mnt/c/Users/TON_COMPTE_WINDOWS'
python3 scripts/configure.py --user "$linux_login" --windows-home "$windows_profile"
```

Le second chemin est celui affiché à l’étape 4, sans le suffixe `/wsl2`.
Pour désactiver un module, ajouter par exemple `--without node` à cette commande
**avant la création du fichier**. Le profil par défaut est `base`.

**Attendu :** création de `/opt/wsl2/inventory/local.yml`. Si le fichier existe,
`configure.py` refuse de le remplacer : le relire et l’éditer au lieu de relancer
le générateur. La copie `inventory/local.yml` du dossier Windows n’est pas utilisée.

```bash
nano /opt/wsl2/inventory/local.yml
```

Contrôler au minimum `workstation_profile: base`, le login, le chemin Windows et
les options `enable_*`. Dans Nano : `Ctrl+O`, Entrée pour enregistrer, `Ctrl+X`
pour quitter. Le rôle créera ensuite l’utilisateur Linux ; il n’est pas
nécessaire de l’ajouter manuellement pour ce parcours `base`.

### D’où viennent les autres variables ?

| Fichier | Rôle |
| --- | --- |
| `inventory/hosts.yml` | Hôte `localhost` et connexion locale |
| `inventory/group_vars/all.yml` | Valeurs communes : home, UID/GID, paquets, options, etc. |
| `inventory/local.yml` | Surcharges personnelles passées avec `-e @...` |
| `manifests/tools.yml` | Versions chargées par le playbook avant le rôle |
| `private/assets…/versions.yml` | Versions capturées, uniquement pour le profil `migration` |

`inventory/example.yml` n’est pas non plus une liste exhaustive des variables.
Ne pas utiliser `local.yml` comme inventaire avec `-i` et ne pas recopier les
valeurs communes pour masquer un défaut de chargement de l’inventaire.

## 9. Contrôler l’inventaire, puis appliquer Ansible

**Terminal : Debian root, répertoire `/opt/wsl2`.**

```bash
cd /opt/wsl2
export ANSIBLE_CONFIG=/opt/wsl2/ansible.cfg
ansible --version
```

**Attendu :** la ligne `config file` désigne `/opt/wsl2/ansible.cfg`.
Contrôler ensuite que les valeurs communes et les surcharges sont présentes,
sans afficher leurs valeurs personnelles :

```bash
set -o pipefail
ansible-inventory -i inventory/hosts.yml --host localhost -e @inventory/local.yml |
  python3 -c 'import json,sys; d=json.load(sys.stdin); required=("workstation_user","workstation_profile","workstation_home","workstation_uid","workstation_gid","base_apt_packages","enable_corporate_ca"); missing=[k for k in required if k not in d]; print("Variables manquantes : " + ", ".join(missing) if missing else "Inventaire et surcharges chargés."); sys.exit(bool(missing))'
```

**Attendu :** `Inventaire et surcharges chargés.` Si une variable manque, arrêter
ici et suivre le dépannage ; ne pas lancer le rôle avec une configuration partielle.

```bash
ansible-playbook -i inventory/hosts.yml site.yml -e @inventory/local.yml
```

**Attendu :** récapitulatif avec `failed=0` et `unreachable=0`. Un premier passage
peut durer plusieurs minutes. En cas d’erreur, conserver le nom de la tâche et
le message, corriger la cause puis relancer **la même commande complète**.
Un `--syntax-check` réussi ne remplace pas cette exécution.

Après réussite, définir le mot de passe du compte choisi à l’étape 8 :

```bash
linux_login='monlogin'
getent passwd "$linux_login"
passwd "$linux_login"
```

**Attendu :** compte existant, home `/home/monlogin`, shell `/usr/bin/zsh`, puis
confirmation du changement de mot de passe. Aucun caractère ne s’affiche pendant
la saisie. Ce mot de passe sera notamment utilisé par `sudo`.

Pour vérifier immédiatement la convergence, relancer le playbook :

```bash
ansible-playbook -i inventory/hosts.yml site.yml -e @inventory/local.yml
```

**Attendu :** aucune erreur et, normalement, `changed=0`. Examiner les changements
récurrents éventuels avant de considérer la recette terminée.

```bash
exit
```

## 10. Reconnecter le compte normal et finaliser Windows

**Terminal : PowerShell 7 normal.** Reprendre le même login Linux :

```powershell
$linuxUserName = 'monlogin'
$repoWindows = Join-Path $env:USERPROFILE 'wsl2'
Set-Location -LiteralPath $repoWindows
wsl --terminate Debian
wsl -d Debian -u $linuxUserName -- whoami
```

**Attendu :** `monlogin`, pas `root`. Cette reconnexion prend aussi en compte
l’appartenance au groupe Docker.

Pour les préférences Windows, choisir **une** méthode :

### Méthode A — configuration manuelle, indépendante du bootstrap PowerShell

Ouvrir Windows Terminal une première fois, puis ses **Paramètres** :

1. Sélectionner le profil `Debian`, ou créer un profil avec la ligne de commande
   `wsl.exe -d Debian -u monlogin` si ce profil n’est pas encore visible.
2. Définir le répertoire de départ à
   `\\wsl.localhost\Debian\home\monlogin\devops`.
3. Choisir Cascadia Mono, taille 14, et le jeu de couleurs Tango Dark pour
   reproduire les valeurs communes ; choisir Debian comme profil par défaut.
4. Enregistrer. Le thème Agnoster sera fourni par le Zsh déjà configuré.

Si les réglages réseau du poste de référence sont nécessaires :

```powershell
notepad (Join-Path $env:USERPROFILE '.wslconfig')
```

Créer ou compléter les sections suivantes **sans dupliquer les sections ni
effacer les autres clés existantes** :

```ini
[wsl2]
networkingMode=mirrored
dnsTunneling=false
autoProxy=true

[experimental]
hostAddressLoopback=true
```

Enregistrer puis fermer Notepad. Ces réglages reprennent le poste de référence,
mais doivent être validés avec le VPN/proxy du nouveau PC. Ils sont globaux à WSL.

### Méthode B — script de fusion du dépôt

Windows Terminal doit avoir été ouvert une fois. Dans le même PowerShell 7 :

```powershell
$linuxUserName = 'monlogin'
$repoWindows = Join-Path $env:USERPROFILE 'wsl2'
Set-Location -LiteralPath $repoWindows
New-Item -ItemType Directory -Force .\artifacts | Out-Null
Start-Transcript -Path (Join-Path $repoWindows ('artifacts\configuration-windows-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log'))
pwsh -NoProfile -File .\windows\bootstrap.ps1 -Stage Configure -Distro Debian -LinuxUser $linuxUserName
$configurationExitCode = $LASTEXITCODE
Stop-Transcript
if ($configurationExitCode -ne 0) { throw 'Configuration Windows incomplète : lire le journal ou utiliser la méthode A.' }
```

Le script fusionne Terminal et `.wslconfig`, ainsi que d’éventuelles préférences
Windows restaurées. Il peut avoir modifié un premier fichier avant une erreur :
ne pas considérer toute l’étape comme validée si son code de retour est non nul.

### Appliquer et ouvrir Debian

Après modification de `.wslconfig`, fermer les applications de toutes les
distributions WSL avant cette commande, qui les arrête toutes :

```powershell
wsl --shutdown
```

Puis :

```powershell
$linuxUserName = 'monlogin'
wsl --set-default Debian
wsl -d Debian -u $linuxUserName
```

**Attendu :** shell Zsh du compte normal. Un simple retour dans l’ancienne fenêtre
root ne remplace pas cette reconnexion.

## 11. Faire la recette utilisateur

**Terminal : Debian, utilisateur normal.**

```bash
whoami
id
cd /opt/wsl2
python3 scripts/verify.py --profile base --docker
```

**Attendu :** le compte choisi, groupe `docker` présent et contrôles JSON à `true`.
Si un module a été exclu, adapter le contrôle : retirer `--docker` et/ou ajouter
`--without node`, `--without terraform`, `--without uv` selon la configuration.

Si Docker est activé :

```bash
docker run --rm hello-world
docker compose version
```

**Attendu :** fonctionnement sans `sudo`. Tester aussi `Ctrl+R`, `Ctrl+T`, `cdf`
et l’ouverture d’un fichier avec Micro. Le code sous `/opt/wsl2` appartient à root ;
les projets quotidiens doivent être créés dans le home de l’utilisateur.

Pour VS Code, installer l’extension WSL **côté Windows**, depuis PowerShell normal :

```powershell
code --install-extension ms-vscode-remote.remote-wsl
```

Puis, dans Debian sous le compte normal :

```bash
mkdir -p "$HOME/devops/recette-wsl"
cd "$HOME/devops/recette-wsl"
code .
```

**Attendu :** VS Code affiche une connexion **WSL: Debian** et son terminal est
Linux. Si `code` n’est pas encore reconnu, rouvrir les terminaux après installation
de VS Code ou lancer la connexion à Debian depuis la palette de commandes de
VS Code. [Documentation VS Code WSL](https://code.visualstudio.com/docs/remote/wsl).

## Reprendre un essai ou faire évoluer la configuration

Le fichier actif reste **`/opt/wsl2/inventory/local.yml`**, pas sa copie Windows.
Après le premier provisionnement, les reprises depuis le compte normal se font
ainsi ; `sudo` demande le mot de passe défini à l’étape 9 :

```bash
cd /opt/wsl2
sudo nano /opt/wsl2/inventory/local.yml
sudo env ANSIBLE_CONFIG=/opt/wsl2/ansible.cfg \
  ansible-playbook -i inventory/hosts.yml site.yml -e @inventory/local.yml
```

Pour mettre à jour les sources, recopier la bonne version du dossier Windows avec
la commande rsync de l’étape 7 en root : elle conserve le `local.yml` Linux. La
copie `/opt/wsl2` ne contient volontairement pas les métadonnées Git. Les étapes de
reprise par symptôme sont dans [DEPANNAGE.md](DEPANNAGE.md).

La validation de la documentation et des scripts ne prouve pas que le parcours a
été exécuté de bout en bout sur chaque poste Windows : conserver le SHA/copie
testée, les journaux privés et les résultats de la recette du poste concerné.
