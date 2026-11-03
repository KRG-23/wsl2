# Maintenance du socle partagé

## Contrat de la première version

- Windows 11 x64, WSL2 récent, Debian 13 amd64 ; PowerShell 7.2+ côté Windows.
- Installation autonome avec droits administrateur Windows pour les prérequis et droits root/sudo dans Debian.
- Configuration par utilisateur dans `inventory/local.yml`, ignorée par Git ; `inventory/example.yml` ne contient aucune identité réelle.
- Modules Docker, Terraform, Node et UV activables avant la première installation. Les désactiver ne désinstalle pas un logiciel existant.
- CA d’entreprise facultatives : activer `enable_corporate_ca` et fournir les certificats publics PEM `.crt` dans `private/ca/` ou un `corporate_ca_directory` privé explicite.
- Le profil `base` fonctionne sans `private/`, Vault ou outils du poste de référence. Le profil `migration` charge les captures privées et ajoute les helpers personnels.
- Pas de déploiement IT centralisé, Ubuntu, ARM, migration automatique de Docker Desktop ni relocalisation arbitraire du home Linux dans cette version.

## Versions et téléchargements

`manifests/debian-image.json` fige l’image officielle et son SHA256. `manifests/public-assets.json` fige Oh My Zsh et UV, avec révisions et SHA256 ; l’installation ne résout jamais une branche `latest` pour ces archives.

Pour actualiser ces deux outils, modifier les révisions explicites de `scripts/refresh-public-assets.py`, exécuter `python3 scripts/refresh-public-assets.py --write-lock`, puis examiner le diff. Le verrou initial est établi depuis les endpoints HTTPS officiels ; les installations suivantes vérifient ce verrou. Ne pas régénérer automatiquement les empreintes pendant l’installation.

APT vérifie les signatures des dépôts Debian et des éditeurs. Terraform est explicitement versionné. Docker et les paquets Debian reçoivent les versions disponibles dans leurs dépôts ; Node est fixé à une branche majeure. La reproductibilité vise les fonctions et configurations, pas un clone binaire éternel du système APT. Si une version verrouillée disparaît, corriger et revoir le verrou ; ne pas substituer silencieusement une autre version.

Le socle partagé utilise Node 24 LTS ; le profil de migration conserve la majeure capturée sur la source, initialement Node 20. Cette dernière est en fin de vie : prévoir sa montée de version avec les projets concernés avant de l’adopter comme standard d’équipe. [Calendrier officiel Node.js](https://nodejs.org/en/about/previous-releases).

Les runtimes hérités sont copiés avec empreintes depuis la source. Cela conserve les versions existantes mais ne remplace pas une maintenance de ces logiciels. Vérifier les bibliothèques dynamiques, les dépendances Informix/GSK et les licences avant transfert.

## Ajouter une option commune

Ajouter une variable publique avec un défaut explicite, sa validation et sa documentation dans l’exemple. Isoler les tâches optionnelles et conserver le profil `base` utilisable sans configuration d’entreprise. Ajouter les secrets et personnalisations spécifiques uniquement aux fichiers privés ou aux mécanismes de connexion propres à chaque utilisateur.

Conserver les noms de fichiers de profils séparés ; ne jamais copier un home ou une configuration personnelle dans les fichiers publics pour proposer un nouveau défaut. Aucun jeton GitHub/Vault n’est nécessaire pour installer le dépôt public.

## Recette avant diffusion d’une version

1. Exécuter les tests Python, les tests de fusion PowerShell et le contrôle syntaxique Ansible.
2. Importer une **nouvelle distribution WSL de test**, appliquer le profil `base` sans aucun fichier privé, puis réexécuter le playbook : aucun changement inattendu ne doit subsister.
3. Redémarrer WSL, vérifier le shell, le rendu Powerline, les liens Fd/Bat, les outils, Docker et l’accès VS Code Remote-WSL.
4. Tester un profil avec les modules optionnels désactivés.
5. Tester une restauration chiffrée sur des données synthétiques et un volume de test, puis vérifier le refus d’une archive altérée et d’un volume cible non vide.
6. Sur le poste cible de migration, tester VPN/DNS/TLS, connexions Git/cloud, Vault, bases de données et changements Git locaux avant la bascule.

La CI automatise les vérifications sans provisionnement système. Elle ne démontre pas à elle seule le bon fonctionnement de WSL, de l’IT d’entreprise ou des applications restaurées. La recette WSL complète doit être effectuée sur un poste Windows de test avant diffusion comme version stable.
