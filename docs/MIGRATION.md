# Migration du poste de référence

Conserver le même **nom d’utilisateur Linux, chemin du home et UID/GID**. Le code de ce dépôt est paramétrable, mais les scripts hérités des projets peuvent contenir des chemins absolus. Le compte Windows peut changer ; ajuster `windows_home` sur la cible.

Ne jamais exécuter le bootstrap ou le playbook de provisionnement sur la source. Les commandes d’inventaire et de capture suivantes ne modifient pas sa configuration. Les sauvegardes Docker, elles, arrêtent temporairement les conteneurs lorsque les options correspondantes sont fournies.

Les chapitres 1 à 3 s’exécutent sur le **poste source**, les chapitres 4 et 5 sur
la **cible**. Lancer les commandes Linux depuis le dépôt indiqué et les commandes
PowerShell depuis la copie Windows du dépôt, sous le compte Windows habituel.
`monlogin` et les chemins `mon-compte` sont des exemples à adapter.

Sur la source de référence, le dépôt et ses captures sont dans
`~/devops/homelab/wsl2`. La copie d’installation publique `/opt/wsl2` décrite pour
le profil `base` n’est pas automatiquement incluse dans la sauvegarde du home :
si les captures ont été créées ailleurs, les inclure dans un arbre sauvegardé ou
les transférer séparément sous chiffrement avant de continuer.

## 1. Inventorier et capturer sur la source

```bash
python3 scripts/collect.py --home "$HOME" \
  --windows-home /mnt/c/Users/mon-compte --output artifacts/source-final.json
python3 scripts/fetch-baseline.py
python3 scripts/compare.py artifacts/baseline/inventory.json \
  artifacts/source-final.json > artifacts/comparison-final.json
python3 scripts/capture-assets.py --include-informix --output private/assets-final
```

Le collecteur signale les contrôles impossibles, notamment l’accès au daemon Docker. Le relancer avec les droits appropriés si nécessaire, en conservant `--home /home/monlogin`. Il n’exporte ni variables d’environnement, ni valeurs de credentials, ni URLs des dépôts Git. Ses métadonnées restent personnelles : ne pas publier `artifacts/`.

La capture conserve les exécutables locaux, AWS CLI, Session Manager, Python 3.12, Oh My Zsh et, avec `--include-informix`, Informix et GSK. Elle enregistre leurs SHA256 et les versions npm/pipx. Les captures de logiciels propriétaires restent privées. Le script crée ou complète `inventory/local.yml` avec le profil `migration` et le chemin de la capture. Examiner `manifest.json`, notamment `missing`, et le fichier local avant de continuer.

Pour un poste différent, `--include-informix` est facultatif. Le profil `base` est préférable si l’objectif est seulement d’installer le socle partagé. Le collecteur accepte `--projects` pour les espaces de travail hors de `~/devops`.

Depuis PowerShell 7 sur la source :

```powershell
pwsh -File windows/collect.ps1 -OutputDirectory "$env:USERPROFILE\wsl2-inventory"
```

Cela inventorie WSL, Windows, les applications WinGet et les extensions VS Code. Les applications gérées par l’IT, connexions VPN et connexions SSO/OAuth devront être réinstallées ou renouvelées ; ne pas importer aveuglément toute la liste WinGet.

## 2. Préparer les sauvegardes

Installer `age` si nécessaire. Générer une identité **hors du dépôt**, sur un support privé ; conserver la clé de déchiffrement séparément de l’archive :

```bash
umask 077
age-keygen -o /chemin/prive/wsl2-identity.txt
age-keygen -y /chemin/prive/wsl2-identity.txt
```

Pour le retour arrière, exporter aussi la distribution source depuis PowerShell vers un disque chiffré, après fermeture des applications :

```powershell
pwsh -File windows/bootstrap.ps1 -Stage Export `
  -Distro Debian -ExportPath D:\Migration\debian-source.tar
```

L’export termine la distribution choisie et contient ses secrets en clair **dans le fichier exporté** : il doit rester sur un support chiffré. Il n’inclut ni les fichiers Windows, ni le stockage Docker Desktop.

## 3. Créer l’archive chiffrée

Fermer les éditeurs et agents, arrêter les autres écritures, puis lancer la commande depuis un terminal indépendant. Utiliser un emplacement de sortie extérieur aux arbres sauvegardés et assez d’espace pour l’archive, le staging et les données finales.

```bash
sudo python3 scripts/migration.py backup \
  --home /home/monlogin --windows-home /mnt/c/Users/mon-compte \
  --recipient age1COLLER_LA_CLE_PUBLIQUE \
  --output /mnt/d/Migration/workstation.age \
  --system-odbc --docker --stop-containers --acknowledge-quiesced
```

Cette commande archive les projets avec `.git`, changements locaux et fichiers non suivis ; les configurations, clés, certificats privés, historiques et données applicatives ; les fichiers cloud Windows sélectionnés ; les données des volumes Docker locaux. `private/` et `inventory/local.yml` sont inclus lorsque le dépôt se trouve dans `~/devops`. Les identités de chiffrement doivent rester ailleurs.

Les conteneurs locaux actifs sont arrêtés avec un délai de 60 secondes puis redémarrés, y compris lors d’une erreur récupérable. Les bind mounts doivent être couverts par la sauvegarde. Ajouter `--extra-home chemin/relatif` pour un autre dossier du home. Pour un socket Docker ou un montage déjà exporté séparément, utiliser explicitement `--ignore-bind /chemin/absolu` ; ces omissions sont consignées dans le manifeste. Les volumes externes/NFS exigent un export spécifique et sont refusés.

Les exclusions de caches s’appliquent au home, jamais aux données des volumes Docker. Les liens symboliques externes non portables sont omis et listés dans le manifeste. Après une coupure électrique ou un arrêt forcé du processus, contrôler manuellement l’état des conteneurs avant de relancer. Un simple accord `--acknowledge-quiesced` ne rend pas cohérente une application qui écrit encore.

Les images Docker ne sont pas des volumes. Le manifeste conserve leurs digests et les projets Compose actifs pour éviter de récupérer silencieusement une nouvelle image `latest`. Pour conserver exactement une image construite localement, l’exporter séparément sous chiffrement avec `docker image save IMAGE | age -r age1... > image.tar.age`, puis vérifier le succès **des deux commandes** avec `set -o pipefail`. Sur la cible, déchiffrer complètement dans un fichier temporaire privé avant `docker image load -i fichier.tar` ; effacer ensuite ce fichier. Une image peut elle aussi contenir des secrets.

## 4. Restaurer sur la cible

Sur la **cible**, suivre [INSTALLATION.md](INSTALLATION.md) jusqu’à la fin de
l’étape 7 incluse : outils Windows, import, bootstrap Debian, redémarrage avec
systemd, copie du code dans `/opt/wsl2`. Rester dans Debian **root**, puis :

```bash
cd /opt/wsl2
```

Ne pas générer de configuration `base` et ne pas lancer encore Ansible. Les
surcharges `migration` et leurs captures privées seront récupérées depuis la
sauvegarde. Le compte Linux doit avoir le même nom, home et UID/GID que sur la source.

Le staging doit se trouver sur le système de fichiers Linux, dans un répertoire privé encore inexistant, hors du home final :

```bash
sudo python3 scripts/migration.py restore /mnt/d/Migration/workstation.age \
  --identity /chemin/prive/wsl2-identity.txt --into /var/tmp/wsl2-restore
```

La restauration vérifie l’authentification du flux chiffré et refuse les chemins dangereux. Elle ne copie rien vers le home final. Examiner `manifest.json` : dossiers inclus, exclusions de bind mounts, liens omis et volumes. Le marqueur `.verified` n’est créé qu’après succès complet.

Récupérer les captures privées et les surcharges dans le répertoire qui servira
effectivement à Ansible. Le chemin du dépôt archivé ci-dessous correspond au
poste de référence ; l’adapter si la source utilisait un autre emplacement.

Avant de continuer, contrôler `getent passwd 1000` et `getent group 1000`. Si
l’identité est déjà occupée par un autre utilisateur, résoudre cette différence
avant de provisionner. Le rôle créera le compte attendu sur une Debian importée
vide ; il n’est pas nécessaire de créer manuellement un utilisateur différent.

```bash
# En root sur la CIBLE uniquement.
saved_repo=/var/tmp/wsl2-restore/home/devops/homelab/wsl2
test -d "$saved_repo/private"
test -f "$saved_repo/inventory/local.yml"
```

Les deux contrôles `test` doivent réussir (code de retour `0`). Si les captures
sont ailleurs dans l’archive, utiliser leur emplacement réel ; ne pas appliquer
le profil avec des fichiers manquants. Dans le même shell, après ces contrôles :

```bash
cp -a "$saved_repo/private" /opt/wsl2/
install -m 0600 "$saved_repo/inventory/local.yml" /opt/wsl2/inventory/local.yml
cd /opt/wsl2
nano inventory/local.yml
```

Contrôler `workstation_profile: migration`, le login source, `windows_home` du
**nouveau** compte Windows et `assets_directory` vers les captures restaurées
(de préférence un chemin relatif à `{{ playbook_dir }}`). Garder
`enable_local_autostart: false` jusqu’à la fin de la restauration, pour éviter le
démarrage d’applications avant leurs données. Le `local.yml` copié plus tard
dans un dépôt du home ne remplace pas ce fichier actif sous `/opt/wsl2`.

Puis lancer le premier passage :

```bash
export ANSIBLE_CONFIG=/opt/wsl2/ansible.cfg
ansible-playbook -i inventory/hosts.yml site.yml -e @inventory/local.yml
```

Après un récapitulatif avec `failed=0` et `unreachable=0` seulement, définir le
mot de passe du compte créé ; remplacer par le login source :

```bash
passwd monlogin
```

Ne pas ouvrir encore de session utilisateur de travail. Rester root pour la
copie et le second passage Ansible ; la procédure de staging ne déploie pas
automatiquement l’archive dans le home final.

Arrêter les conteneurs éventuellement démarrés sur la cible. Prévisualiser la copie :

```bash
sudo python3 scripts/deploy-restored.py --staging /var/tmp/wsl2-restore \
  --home /home/monlogin --windows-home /mnt/c/Users/nouveau-compte --volumes
```

Lire le rapport privé `.deployment-preview-*.txt` dans le staging. Après
vérification des fichiers et volumes concernés, appliquer les mêmes paramètres :

```bash
sudo python3 scripts/deploy-restored.py --staging /var/tmp/wsl2-restore \
  --home /home/monlogin --windows-home /mnt/c/Users/nouveau-compte --volumes --apply
```

Après réussite de la copie, réappliquer la configuration cible :

```bash
ansible-playbook -i inventory/hosts.yml site.yml -e @inventory/local.yml
```

Ces commandes se lancent toujours depuis `/opt/wsl2`, sous root. Le dernier
playbook réapplique la configuration cible après la copie des anciens dotfiles.

Les fichiers remplacés sont conservés dans un dossier de retour arrière. Un rapport privé `.deployment-preview-*.txt` dans le staging liste les fichiers qui changeraient ; l’examiner avant `--apply`. Les volumes cibles doivent être neufs ou vides : fusionner deux jeux de fichiers de base de données est refusé. L’absence de `--volumes` laisse les volumes dans le staging.

Les réglages Windows Terminal et VS Code sont préparés dans `%USERPROFILE%\.wsl2-source-preferences`, puis fusionnés par `windows/bootstrap.ps1 -Stage Configure`. Les données Windows restantes sont copiées avec sauvegarde des fichiers remplacés. Les références au profil Windows sont adaptées dans les configurations Git/cloud/MCP/ODBC sélectionnées et les préférences VS Code. Les projets ne sont pas réécrits : vérifier leurs éventuels chemins spécifiques à l’ancien compte. Recréer ensuite les liens `.aws`/`.azure` par le playbook.

## 5. Recette et bascule

Quitter le shell root. Dans PowerShell normal :

```powershell
wsl --terminate Debian
wsl -d Debian -u monlogin
```

Depuis le nouvel utilisateur, utiliser le code sous `/opt/wsl2` :

```bash
cd /opt/wsl2
python3 scripts/verify.py --profile migration --docker --toolz --cloud-links
```

**Attendu :** contrôles JSON à `true`. Pour restaurer aussi les extensions VS Code,
transférer séparément l’inventaire privé `artifacts/source-final.json` de la source :
`artifacts/` est exclu de l’archive. Placer le fichier dans un dossier privé du
home cible, par exemple `~/migration-privee/source-final.json`, puis vérifier
sa présence avant la restauration facultative :

```bash
test -f "$HOME/migration-privee/source-final.json" && echo 'Inventaire présent.'
```

Après confirmation :

```bash
python3 scripts/restore-extensions.py "$HOME/migration-privee/source-final.json" --surface wsl --apply
```

Installer les extensions Windows depuis PowerShell avec `python scripts/restore-extensions.py CHEMIN_INVENTAIRE --surface windows --code code.cmd --apply`, si Python Windows est disponible, ou avec les IDs de `windows/collect.ps1` et `code.cmd --install-extension`.

Vérifier les accès Git Linux/Windows, SSH, CA/TLS, DNS/VPN et refaire les authentifications SSO/OAuth et les connexions aux registres Docker. Les images construites localement doivent être chargées avant de reprendre les applications. Prévisualiser puis reprendre les projets Compose avec leurs digests d’origine :

```bash
sudo python3 scripts/restore-services.py --staging /var/tmp/wsl2-restore
sudo python3 scripts/restore-services.py --staging /var/tmp/wsl2-restore --phase vault --apply
# Déverrouiller Vault avec Toolz/docker-tools/vault/local/unseal.sh et vérifier sa santé.
sudo python3 scripts/restore-services.py --staging /var/tmp/wsl2-restore --phase applications --apply
```

Le script ne démarre que les services Compose actifs lors de la sauvegarde ; les conteneurs temporaires créés par les clients MCP sont recréés par ces clients. Il refuse de reconstruire implicitement une image locale absente. Les fichiers de verrou d’images sont conservés dans `~/.config/workstation/compose-locks`, indépendamment du staging. Les scripts locaux susceptibles d’exécuter eux-mêmes `compose up` devront conserver ces verrous ou leurs références explicites pour garder ce résultat dans le temps. Tester les bases restaurées avant d’activer `enable_local_autostart: true`. Le mot de passe sudo et les sessions Windows ne sont pas copiés.

Une fois la recette terminée, fermer les applications sur la source et réaliser une dernière sauvegarde cohérente pour les changements intervenus entre-temps. Restaurer cette dernière sauvegarde vers de nouveaux volumes vides ; ne pas fusionner les fichiers d’une base active. Conserver la source, l’export WSL, l’archive et le staging jusqu’à validation des projets et des services, puis supprimer les copies privées devenues inutiles selon la politique de conservation choisie.
