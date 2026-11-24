# Dépannage et reprise d’installation

Le parcours de référence est [INSTALLATION.md](INSTALLATION.md). Reprendre la
dernière étape réussie, dans le terminal et sous l’utilisateur indiqués. Conserver
le message initial ; une reprise d’Ansible ne demande normalement ni réimport de
Debian ni suppression de données.

## Variables absentes dans `inventory/local.yml`

Exemples : `workstation_home is undefined`, `base_apt_packages is undefined`, ou
avertissement indiquant un répertoire `world-writable` et un `ansible.cfg` ignoré.

`local.yml` fournit seulement les surcharges. Les valeurs communes viennent de
`inventory/group_vars/all.yml`. Les versions sont chargées séparément par le
playbook depuis `manifests/tools.yml` et, pour une migration, la capture privée.

Le défaut de chargement a été reproduit depuis un dossier accessible en écriture
à tous : Ansible ignore sa configuration et perd l’inventaire par défaut. Ce
scénario explique des variables absentes, sans établir la cause de chaque erreur
rencontrée sur un autre poste.

**Dans Debian root, depuis la copie Linux :**

```bash
cd /opt/wsl2
export ANSIBLE_CONFIG=/opt/wsl2/ansible.cfg
test -f inventory/hosts.yml
test -f inventory/group_vars/all.yml
test -f inventory/local.yml
ansible --version
ansible-inventory -i inventory/hosts.yml --graph
```

**Attendu :** configuration `/opt/wsl2/ansible.cfg`, trois fichiers présents et
hôte `localhost`. Exécuter le contrôle des variables de l’étape 9 du guide, puis :

```bash
ansible-playbook -i inventory/hosts.yml site.yml -e @inventory/local.yml
```

Depuis le compte normal, utiliser la commande `sudo env ... ansible-playbook ...`
de la fin du guide. Ne pas remplacer `-i inventory/hosts.yml` par
`-i inventory/local.yml` et ne pas recopier toutes les variables communes dans
les surcharges pour contourner ce contrôle. Si l’erreur persiste, relever le nom
exact de la variable et de la tâche ; une version n’est pas une variable
d’inventaire. [Documentation Ansible](https://docs.ansible.com/ansible/latest/reference_appendices/config.html#avoiding-security-risks-with-ansible-cfg-in-the-current-directory).

## Reprise selon le symptôme

| Symptôme | Contrôle et point de reprise |
| --- | --- |
| `git`, `pwsh`, `winget` ou `code` introuvable | Étape 1 ; rouvrir le terminal après l’installation. WinGet absent nécessite App Installer ou le canal IT. |
| PowerShell 7.2 exigé, paramètre PowerShell inconnu | Vérifier `$PSVersionTable.PSVersion` : `powershell.exe` est Windows PowerShell 5.1, `pwsh.exe` PowerShell 7. |
| Droits administrateur demandés pour préparer WSL | Étape 2 dans PowerShell 7 administrateur ; revenir ensuite au compte habituel pour l’import. |
| Redémarrage demandé après installation WSL | Redémarrer Windows avant de poursuivre avec la mise à jour et l’import. |
| `Debian` existe déjà | Vérifier `wsl --list --verbose`, sa version Debian et ses données ; suivre la branche correspondante de l’étape 4. |
| SHA256 différent | Ne pas importer ; suivre la section image ci-dessous. |
| `Run with sudo on the target only` | Rouvrir Debian avec `wsl -d Debian -u root`, puis revenir au bon dossier. |
| Marqueur `bootstrap-ready` absent | Reprendre l’étape 5 et résoudre les erreurs APT ; ne pas créer le marqueur à la main. |
| PID 1 différent de `systemd` | Vérifier le bootstrap et le redémarrage ; voir la section systemd. |
| `inventory/local.yml` existe déjà | Relire/éditer la configuration Linux de l’essai précédent ; le générateur refuse volontairement de l’écraser. |
| UID/GID déjà utilisé | Lire `getent passwd 1000` et `getent group 1000` ; réutiliser le compte compatible ou adapter le provisionnement avant application. |
| `sudo` refuse le mot de passe | Utiliser le mot de passe Linux, défini par `passwd monlogin` depuis root, pas celui du compte Windows. |
| Docker répond `permission denied` | Vérifier `whoami` et `id`, puis reconnecter le compte après le rôle ; ne pas ouvrir le socket à tous. |
| Répertoire temporaire `/tmp/wsl2-ansible` refusé | Reprendre via la commande `sudo env ... ansible-playbook ...` du guide, après un premier passage en root. |
| `Open Windows Terminal once` | Ouvrir Terminal une fois sous le compte habituel ; reprendre `Configure` ou choisir la configuration manuelle. |
| Erreur TLS, DNS ou proxy | Vérifier réseau et confiance des CA dans Debian ; ne pas désactiver TLS. Voir la section réseau. |

## Bootstrap PowerShell en échec

Sans le message original, sa cause ne peut pas être identifiée rétrospectivement.
Le guide principal donne donc les commandes Windows séparément, avec une méthode
manuelle pour les préférences Windows.

Chaque phase du script a un périmètre distinct :

| Phase | Préconditions et effet |
| --- | --- |
| `Prerequisites` | PowerShell 7 administrateur ; installation WSL, mise à jour, WinGet. Un redémarrage peut interrompre l’enchaînement. |
| `Import` | Compte Windows habituel, image et SHA256 vérifiés ; enregistre Debian mais ne crée pas le compte Linux et n’exécute pas Ansible. |
| `Configure` | Compte habituel, Terminal déjà ouvert une fois, login Linux créé ; prépare Terminal et `.wslconfig`, pas les paquets Debian. |
| `Export` | Arrête la distribution choisie et exporte son disque ; ce n’est pas une étape d’installation. |

Pour recueillir un incident de `Configure`, sous **PowerShell 7 normal** :

```powershell
$repoWindows = Join-Path $env:USERPROFILE 'wsl2'
Set-Location -LiteralPath $repoWindows
$PSVersionTable.PSVersion
whoami
New-Item -ItemType Directory -Force .\artifacts | Out-Null
Start-Transcript -Path (Join-Path $repoWindows ('artifacts\diagnostic-configure-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log'))
pwsh -NoProfile -File .\windows\bootstrap.ps1 -Stage Configure -Distro Debian -LinuxUser monlogin
$configurationExitCode = $LASTEXITCODE
Stop-Transcript
Write-Host "Code de retour Configure : $configurationExitCode"
```

Remplacer `monlogin` par le compte créé. Ne pas utiliser ce bloc pour rejouer les
autres phases sans leurs préconditions. Le script peut avoir écrit `.wslconfig`
avant de signaler l’absence du fichier Terminal : un échec peut donc être partiel.
Consulter le journal, puis utiliser si nécessaire la méthode manuelle de l’étape 10.
Une restriction d’exécution imposée par l’entreprise doit être traitée avec son
administrateur ; le parcours manuel n’exige pas de modifier globalement cette politique.

## systemd ne démarre pas

**Dans Debian root :**

```bash
cat /etc/wsl.conf
dpkg-query -W systemd systemd-sysv
cat /proc/1/comm
```

Les paquets doivent être installés et la section `[boot]` doit contenir
`systemd = true`. Après correction du bootstrap, quitter Debian.

**Dans PowerShell normal :**

```powershell
wsl --terminate Debian
wsl -d Debian -u root -- cat /proc/1/comm
```

Si le résultat n’est toujours pas `systemd`, contrôler `wsl --version`, fermer
les applications des autres distributions, puis utiliser `wsl --shutdown` et
rouvrir Debian. Si WSL ne comprend pas `--version`, sa mise à jour Windows est
nécessaire. [Activer systemd dans WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## Image téléchargée non conforme

Ne pas importer une image dont le SHA256 diffère du verrou. Depuis le dépôt
Windows, conserver le téléchargement douteux sous un autre nom :

```powershell
$repoWindows = Join-Path $env:USERPROFILE 'wsl2'
Set-Location -LiteralPath $repoWindows
$imagePath = Join-Path $repoWindows 'artifacts\debian.wsl'
if (Test-Path -LiteralPath $imagePath) {
    Move-Item -LiteralPath $imagePath -Destination ($imagePath + '.invalid-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
```

Reprendre téléchargement et vérification à l’étape 4. Si le serveur renvoie une
erreur, signaler l’URL et le statut. Ne pas remplacer seulement le SHA256 par
celui du fichier reçu sans revoir l’origine et la version de l’image.

## Réseau et certificats d’entreprise

Dans Debian, commencer par la résolution du serveur concerné :

```bash
getent hosts deb.debian.org
getent hosts github.com
```

Après installation de curl, essayer aussi `curl -I` sur l’URL HTTPS concernée.
Valider le réseau avec et sans VPN selon les règles de l’entreprise.

Si une CA d’entreprise est nécessaire après le bootstrap, obtenir le certificat
public PEM `.crt` par le canal de confiance de l’entreprise, le placer en root
dans `/opt/wsl2/private/ca/`, puis activer `enable_corporate_ca: true` dans le
`local.yml` Linux. Relancer Ansible avec son inventaire explicite : le rôle
applique les CA avant les téléchargements des éditeurs.

Si APT ou le téléchargement initial est déjà bloqué, résoudre d’abord les accès
réseau/proxy/CA avec l’IT ; le rôle Ansible n’a pas encore été exécuté et ne peut
pas corriger rétroactivement cet accès.

## Informations à conserver

Noter l’étape, le terminal, l’utilisateur, le répertoire, la commande et l’erreur
exacts, ainsi que la version du dépôt. Conserver les journaux dans `artifacts/`
côté Windows ou un dossier privé Linux. Relire avant partage : ne pas envoyer
les secrets, clés, captures privées ou configurations complètes. Un SHA Git seul
ne décrit pas les modifications non publiées.
