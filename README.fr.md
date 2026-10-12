# EPMTS — Easy Porn Media Tag System

*[English version: README.md](README.md)*

EPMTS est un système prêt à l'emploi pour **taguer des médias adultes et les tirer au sort par
tags** dans vos projets : jeux navigateur, jeux et mods sur PC, ou tout programme capable de
lire du SQLite ou d'appeler une API HTTP.

| Élément | Rôle | Où |
| --- | --- | --- |
| **Catalogue de tags** | 475 tags en 19 types, aux identifiants stables. Ce dépôt est la référence : les tags se créent **uniquement ici**. | [`catalogue/`](catalogue/) · [liste des tags](catalogue/TAGS.md) |
| **Format de pack** | Un pack de médias est un dossier : `tags.sqlite` + `tags.sql` + `tags.sql.js` + `medias/<sha256>`. | [`empty-pack/`](empty-pack/) (pack vide) |
| **Accueil** | Une fenêtre pour débuter : nombre de médias, import d'un pack (.zip), serveur, prévisualisation. | `quickstart` |
| **Gestionnaire de médias** | Parcourir, taguer, ajouter ses médias, packs personnage, créer un pack à partager (.zip avec `pack.json`). Chaque média garde son origine. | accueil |
| **Packs personnage** | Regrouper les médias d'une même personne, pour qu'une histoire garde le même personnage d'une scène à l'autre : le jeu choisit un portrait, puis ne tire que les médias de cette personne. | [guide](docs/fr/packs-personnage.md) |
| **Serveur** | Serveur HTTP local pour les jeux : tire des médias par tags, convertit pour les moteurs de jeu (PNG/JPEG, vidéo VP8 IVF). Sur un pack (SQLite) ou MySQL. Clé privée facultative. | accueil |
| **Prévisualisation** | Page web pour essayer des requêtes de tags, avec ou sans serveur. | [`web/preview.html`](web/preview.html) |
| **Lecteur navigateur** | Un fichier JavaScript pour tirer des médias d'un pack dans un jeu navigateur, sans serveur. | [`web/epmts-pack.js`](web/epmts-pack.js) |
| **Scripts PHP** | Outils en ligne de commande : créer, ajouter, personnage, fusionner, valider, gérer le catalogue. | [`tools/php/`](tools/php/) |
| **Norme** | La spécification de l'API, du format de pack et des règles de tagage. | [`standard/EPMTS-HTTP.md`](standard/EPMTS-HTTP.md) |

Aucun média n'est inclus dans ce dépôt.

## Démarrage rapide

1. **Téléchargez** ce dépôt (bouton vert *Code* › *Download ZIP*, ou `git clone`) et dézippez-le.
2. **Double-cliquez sur `quickstart.cmd`** (Windows) ou `./quickstart.sh` (Linux/macOS). Au
   premier lancement, il propose d'installer ce qui manque (Python, ffmpeg), puis la fenêtre
   d'accueil s'ouvre.
3. **Importez votre pack téléchargé** : *Import a media pack (.zip)…*. Chaque fichier est
   vérifié (SHA-256) avant tout import.
4. **Utilisez-le** : jeu navigateur → [`web/epmts-pack.js`](docs/en/web-games.md) ; jeu ou mod
   qui appelle une API → *Start the server*
   ([guide](docs/en/game-integration.md)) ; autre → lisez `tags.sqlite` directement.

## Licence

EPMTS est gratuit pour tout usage **non commercial** sous la
[licence PolyForm Noncommercial 1.0.0](LICENSE) : utilisation, modification, partage et création
de packs permis, en conservant le fichier [NOTICE](NOTICE) et son lien vers le projet d'origine
(https://github.com/phenixxx69/epmts). **Gagner de l'argent avec EPMTS demande une licence
commerciale** : voir [COMMERCIAL.md](COMMERCIAL.md). Chaque pack distribué cite le projet
d'origine dans son `pack.json`.

Débutant ? Suivez le **[guide du débutant](docs/fr/guide-debutant.md)** pas à pas, puis le
**[guide de tagage](docs/fr/guide-tagage.md)** pour taguer vos médias, et le guide des
**[packs personnage](docs/fr/packs-personnage.md)** pour garder un même personnage dans une histoire.
