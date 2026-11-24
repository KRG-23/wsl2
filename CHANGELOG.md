# Changelog

## 2026-11-24

- Préparé : installation de Dust (`du-dust`) et Zoxide via APT dans les profils `base` et `migration`, initialisation de `z`/`zi` en fin de configuration Zsh et ajout des deux binaires à la recette. Disponibilité des paquets Debian 13 amd64 vérifiée ; aucun provisionnement du poste courant effectué pour cet ajout.
- Vérifié pour cet ajout : 20 tests Python et tests de fusion PowerShell réussis, syntaxe Ansible/Bash/Zsh valide, rendu des deux profils Zsh et déplacement avec `z` testés dans un environnement temporaire isolé. Installation APT simulée uniquement.
- Préparé : guide d’installation Windows 11/Debian 13 numéroté, avec terminal, droits, répertoire, redémarrages et résultats attendus ; dépannage PowerShell et méthode manuelle en l’absence du message d’erreur initial. Procédure de migration alignée sur la copie Linux `/opt/wsl2`, avec contrôles avant application.
- Corrigé dans les commandes documentées et le message du bootstrap Debian : inventaire Ansible explicite pour charger les valeurs communes avec un `local.yml` minimal. Le défaut de découverte automatique d’`ansible.cfg` en répertoire accessible en écriture à tous a été reproduit et couvert par un test de régression, sans établir qu’il était la cause exacte de l’incident utilisateur.
- Vérifié : 20 tests Python réussis, syntaxe du playbook Ansible et des 39 blocs Bash/27 blocs PowerShell de la documentation valide, liens locaux contrôlés. Parcours complet sur le nouveau PC Windows non exécuté ; modifications de cette tâche locales, sans publication ni provisionnement.
- Préparé : nom de distribution WSL par défaut fixé à `Debian`, avec dossier d’installation `%LOCALAPPDATA%\WSL\Debian` et commandes du README alignées. Analyse syntaxique PowerShell, valeur du paramètre par défaut et tests de fusion PowerShell vérifiés ; aucune distribution existante renommée ou provisionnée pendant cette modification.
- Synchronisation locale de `main` avec `origin/main` au commit `2696ee5` : le retrait de `python3-diagrams` provient du dépôt distant. Les modifications locales du 20 novembre ont été mises à l’abri puis restaurées sans conflit, avec sauvegarde privée de récupération.
- Vérifié : configuration YAML et syntaxe Zsh valides ; retrait local du démarrage automatique du collecteur migration conservé. Aucun nouveau provisionnement, commit local ni push réalisé pendant cette synchronisation.

## 2026-11-20

- Préparé : retrait du démarrage du collecteur migration local dans le helper Zsh du profil `migration`, afin qu’un futur provisionnement ne réintroduise pas cette collecte à l’ouverture du terminal.
- Vérifié : syntaxe Zsh valide et absence de l’appel à `migration/start.sh`. La modification du helper reste locale au dépôt, sans nouveau provisionnement, commit ni push ; la suppression correspondante a aussi été appliquée à la configuration Zsh du poste pendant l’arrêt local du suivi.

## 0.1.0 — Première version à recetter sur Windows

- Socle autonome Debian 13/Windows 11, configuration par utilisateur, modules Docker/Terraform/Node/UV optionnels.
- Profil de migration séparé pour les captures privées, outils hérités et helpers personnels.
- Inventaire, comparaison avec une image WSL officielle vérifiée, sauvegarde age et restauration avec prévisualisation.
- Fusion des préférences Windows Terminal/VS Code et protection des volumes Docker existants.
- Tests Python/PowerShell et contrôles syntaxiques en CI.

La recette complète sur une nouvelle distribution WSL et les tests applicatifs de migration restent des critères de diffusion comme version stable.
