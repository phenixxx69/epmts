# Packs personnage : garder la même personne dans une histoire

Un jeu qui tire des médias par tags montre une personne **différente** à chaque fois : « une
femme rousse » n'est jamais deux fois la même femme. Pour une histoire, la continuité est
cassée — le personnage rencontré à la taverne ne ressemble pas à celui de la scène suivante.

Un **pack personnage** règle ce problème : il regroupe plusieurs médias d'**une même
personne**. Le jeu présente un personnage avec un portrait, puis tire les scènes suivantes
**uniquement parmi les médias de cette personne**. Le personnage garde le même visage et le
même corps d'une scène à l'autre.

## Ce qu'est un pack personnage

Dans un pack, un pack personnage est un dossier `medias/<sha256 du portrait>/`, lui-même un
petit pack avec les médias de la personne :

```
mon-pack/
├── tags.sqlite              le portrait y est un média comme les autres
└── medias/
    ├── 81bd…07e             médias ordinaires
    └── 5c0e…9aa/            pack personnage — nommé par l'empreinte du portrait
        ├── tags.sqlite      seulement les médias de la personne
        └── medias/
            ├── 5c0e…9aa     le portrait
            ├── a41f…2c3     la même personne, seule
            └── 9d07…e18     la même personne, dans une scène
```

Le portrait appartient aux deux : dans le pack principal, il est tiré comme n'importe quel
média (c'est ainsi qu'un jeu choisit un personnage) ; dans le pack personnage, c'est le premier
média de la personne. Son empreinte est la **référence** de la personne.

Les autres médias de la personne sont **uniquement** dans le pack personnage : un tirage
ordinaire ne les renvoie jamais, seul un tirage qui porte la référence le fait. Mettez dans un
pack personnage les médias à réserver à ce personnage ; un média destiné à n'importe quelle
scène reste dans le pack principal.

## Le créer

Dans le gestionnaire de médias :

1. *Person › New person pack from a portrait…* et choisissez le portrait (une image fixe).
2. Taguez le portrait (voir plus bas). Le gestionnaire crée le pack personnage et l'ouvre.
3. Dans l'onglet *Import*, importez les médias de cette personne : ils vont dans le pack
   personnage.
4. Taguez chaque média (*Edit tags…*). Cliquez sur *BACK* pour revenir au pack principal, où
   la personne apparaît comme une carte orange.

En ligne de commande : `php tools/php/pack_add_person.php <pack> <dossier> <fichier portrait>`
crée le pack personnage à partir d'un dossier contenant les images d'une même personne
([php-tools.md](../en/php-tools.md)).

## Taguer un pack personnage

- **Le portrait** est ce qui permet au jeu de trouver le personnage : taguez-le comme une
  personne seule — genre, tranche d'âge, cadrage — et surtout **ce qui la rend
  reconnaissable** : couleur de cheveux, style vestimentaire, vêtements distinctifs, état
  d'habillement, classe ou race pour un RPG. Un jeu qui présente « une mage gothique rousse »
  cherche exactement ces tags. Détails : [guide de tagage › Portraits](guide-tagage.md#portraits-et-packs-personnage).
- **Les autres médias** se taguent selon leur propre contexte, exactement comme dans le pack
  principal : une image seule avec genre, âge et cadrage ; une scène avec action + direction,
  sans tag de genre.
- **La variété paie** : portraits, poses seules, tenues et états d'habillement différents,
  scènes. Plus la personne couvre de contextes, plus l'histoire trouve un média de *cette*
  personne au lieu de se rabattre sur quelqu'un d'autre.

## Comment un jeu s'en sert

Le même déroulement fonctionne en HTTP et dans un pack lu par le navigateur :

1. **Choisir un personnage** : tirer un portrait avec les critères du personnage, par exemple
   `1 Woman` + `8 Upper-body portrait` + `27 Red hair`.
2. **Savoir si c'est une personne** : la réponse le dit (voir plus bas). Gardez la référence
   avec votre personnage — dans la sauvegarde, par exemple.
3. **Scènes suivantes** : envoyer le même genre de demande **avec la référence**. Seuls les
   médias de cette personne peuvent sortir.
4. **Quand la personne n'a rien qui corresponde**, la réponse est vide. Le jeu décide : refaire
   un tirage sans la référence (une autre personne), ou ne rien montrer. EPMTS ne change jamais
   de personne en silence.

**En HTTP** ([server.md](../en/server.md)) : la réponse d'un portrait porte `referenceHash` ;
renvoyez-le dans les demandes suivantes :

```json
{"format": "img", "includeTagImg": [15, 137], "referenceHash": "5c0e…9aa"}
```

**Dans un jeu navigateur** ([web-games.md](../en/web-games.md)) :

```js
var portrait = pack.select({include: [1, 8, 27], format: 'img'});
pack.person(portrait).then(function (person) {
    // person vaut null quand ce portrait n'a pas de pack personnage
    var next = (person && person.select({include: [15, 137]})) || pack.select({include: [15, 137]});
});
```

La règle est dans la [norme](../../standard/EPMTS-HTTP.md), section 9 (PR-1).

## Partager et fusionner

- **Créer un pack** (*File › Create a pack from…*) inclut un pack personnage dès que son
  portrait fait partie du pack.
- **Importer ou fusionner** : les packs personnage qui ont le même portrait sont fusionnés,
  leurs médias réunis, comme le reste du pack.

## Bon à savoir

- La référence est l'**empreinte du fichier portrait** : un autre fichier, même très proche,
  est une autre personne. Ne modifiez plus le portrait une fois que des jeux l'utilisent.
- Un pack personnage ne peut pas contenir un autre pack personnage.
- Les packs personnage vivent dans les packs : le serveur les gère avec son mode SQLite par
  défaut, pas avec le mode MySQL.
- Un portrait ne peut pas être supprimé tant que son pack personnage existe : supprimez d'abord
  le dossier de la personne.
- Modifier les tags du portrait le met à jour aux deux endroits (pack principal et pack
  personnage).
