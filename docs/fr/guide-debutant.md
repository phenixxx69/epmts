# Guide du débutant

Ce guide vous mène de « j'ai téléchargé un pack de médias » à « mon jeu affiche ces médias ».
Aucune connaissance en programmation n'est nécessaire avant la dernière étape.

## 1. Lancer EPMTS

1. Téléchargez ce dépôt (bouton vert *Code* › *Download ZIP*) et dézippez-le où vous voulez —
   évitez les dossiers protégés comme `C:\Program Files`.
2. **Windows** : double-clic sur **`quickstart.cmd`**.
   **Linux / macOS** : dans un terminal ouvert dans le dossier, `./quickstart.sh`.
3. La première fois, il vérifie votre ordinateur et **demande avant d'installer** ce qui manque :
   - **Python** (le langage des outils). Sous Windows, il est téléchargé depuis python.org et
     installé pour vous ; sous Linux, le gestionnaire de paquets est utilisé (mot de passe demandé).
   - **ffmpeg** (lecture des vidéos). Facultatif : les images fonctionnent sans.
   Il prépare ensuite un environnement privé dans `.venv/` (une minute environ, une seule fois).
4. La **fenêtre d'accueil EPMTS** s'ouvre. Les fois suivantes, le double-clic l'ouvre directement.

La fenêtre d'accueil indique combien de médias vous avez — *No media found* au début — et d'où
ils viennent, avec quatre boutons.

## 2. Importer le pack téléchargé

Cliquez sur **Import a media pack (.zip)…** et choisissez le zip. Avant tout import, EPMTS
vérifie le pack entier :

- tous les fichiers et dossiers attendus sont là, et rien d'autre ;
- la base est valide ;
- **chaque fichier correspond à son empreinte SHA-256** (pas de fichier corrompu ou remplacé) ;
- les règles de tagage de la [norme](../../standard/EPMTS-HTTP.md) sont respectées.

Au moindre problème, rien n'est importé et la liste des problèmes s'affiche. Sinon vous revenez
à l'accueil, qui affiche par exemple *1 250 media found — 1 250 from "Nom du pack"*. Importez
autant de packs que vous voulez : un média présent dans deux packs n'apparaît qu'une fois, avec
tous ses tags, et chaque média garde le nom du pack d'où il vient.

## 3. Utiliser les médias dans un jeu

### Un jeu qui interroge un serveur (un mod de jeu, Ren'Py, Unity…)

Cliquez sur **Start the server**. EPMTS demande s'il faut une **clé privée** :

- **Non** — n'importe quel programme de cet ordinateur peut demander des médias. Le plus simple
  quand vous jouez seul.
- **Oui** — seuls les programmes qui connaissent la clé. À choisir si d'autres personnes peuvent
  joindre votre ordinateur.

L'accueil affiche alors l'**adresse à donner au jeu** (et la clé s'il y en a une), avec des
boutons *Copy*. Laissez la fenêtre ouverte pendant que vous jouez ; *Stop the server* ou la
fermeture de la fenêtre l'arrête.

Dans les réglages médias du jeu ou du mod, indiquez :

| Réglage | Valeur |
| --- | --- |
| Adresse des médias | `http://127.0.0.1:5055/select` |
| Clé | vide si vous avez répondu *Non*, sinon la clé affichée |
| Conversion | ce que le moteur affiche : images `jpg`/`png`, vidéos `ivf` (VP8), ou `auto` |
| Taille maximale d'un fichier | 32 Mo ou plus, pour les vidéos converties |

Détails : [game-integration.md](../en/game-integration.md).

Le serveur convertit les médias pour les moteurs de jeu (images en JPEG/PNG, animations en vidéo
VP8 IVF avec piste son OGG). La première vidéo d'un média prend quelques secondes.

### Un jeu navigateur (HTML/JavaScript)

Copiez le dossier du pack (`packs/main`) à côté de votre jeu et ajoutez deux scripts :

```html
<img id="image" alt="">
<script src="epmts/sql-asm.js"></script>
<script src="epmts/epmts-pack.js"></script>
<script>
    EpmtsPack.load('pack/').then(function (pack) {
        var media = pack.select({include: [1, 56], format: 'img'});
        if (media) { document.getElementById('image').src = media.url; }
    });
</script>
```

Tout passe par des inclusions de scripts, donc cela fonctionne en local (`file://`), où les
navigateurs bloquent les chargements de fichiers. Voir [web-games.md](../en/web-games.md) ;
`web/example-browser-game.html` est une démo.

### Tout autre programme

`packs/main/tags.sqlite` est une base SQLite normale. Les règles de sélection sont dans la
[norme](../../standard/EPMTS-HTTP.md) (sections 4 et 11).

## 4. Voir vos médias

**Preview the media in your browser** ouvre une page où vous cliquez sur des tags pour les
inclure ou les exclure et tirez des médias comme le ferait un jeu — sans serveur.

## 5. Gérer vos médias et créer vos packs

**Open the media manager** permet de :

- parcourir vos médias, filtrés par tag, type et **origine** (*Local* = ajouté par vous, ou le
  nom d'un pack importé) ;
- **modifier les tags** d'un média (🔞 = action porn) — lisez d'abord le
  [guide de tagage](guide-tagage.md) ;
- **ajouter vos propres fichiers** (onglet *Import*) : métadonnées retirées (appareil, GPS,
  noms…), renommage par empreinte, origine *locale* ;
- créer des **packs personnage** (*Person › New person pack from a portrait…*) : plusieurs
  médias d'une même personne, pour qu'une histoire garde le même personnage d'une scène à
  l'autre ([packs personnage](packs-personnage.md)) ;
- **partager votre travail** : *File › Create a pack from my local media…* (seulement ce que vous
  avez ajouté) ou *File › Create a pack from all media…* (tout, packs importés compris). EPMTS
  demande le nom, l'auteur, la version et la date, et enregistre un `.zip` prêt à partager,
  contenant un `pack.json` avec ces informations et le lien du projet d'origine
  (https://github.com/phenixxx69/epmts), obligatoire : un pack sans ce lien est refusé à l'import. Vos médias locaux qu'il contient sont ensuite
  marqués comme venant de ce pack : un prochain pack « médias locaux » ne contiendra que ce que
  vous ajouterez après.

Tout est enregistré immédiatement.

## 6. Garder le catalogue à jour

Quand ce dépôt reçoit de nouveaux tags, retéléchargez-le (ou `git pull`), puis dans le
gestionnaire *File › Update the tag catalogue*. Vos médias et leurs tags sont conservés. Les
tags ne se créent **que dans ce dépôt** ([catalogue/README.md](../../catalogue/README.md)).

## En cas de souci

| Problème | Solution |
| --- | --- |
| « Windows a protégé votre ordinateur » | *Informations complémentaires › Exécuter quand même* (les scripts sont du texte lisible). |
| « Your Python has no tcl/tk » | Windows : répondez *y*, quickstart l'ajoute à votre Python (ou installe un Python séparé pour EPMTS si c'est impossible). Linux : acceptez l'installation proposée. |
| Pas de vignette pour les vidéos | ffmpeg manque : relancez `quickstart` et acceptez le téléchargement. |
| L'import est refusé | Lisez les problèmes listés : le pack est abîmé ou incomplet. Retéléchargez-le. |
| Le serveur ne démarre pas | Un autre programme utilise le port 5055 : changez `port` dans `tools/python/server/config.json`. |
| Le jeu ne reçoit rien | Vérifiez l'adresse (elle finit par `/select`), la clé, que le serveur tourne, et les tags dans la prévisualisation. |

Usage avancé : `quickstart.cmd editor` ou `quickstart.cmd server` lancent directement le
gestionnaire ou le serveur.
