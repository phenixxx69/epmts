# Comment taguer un média

Un jeu ne regarde jamais l'image : il ne lit que ses tags. Un média bien tagué sort exactement
quand il le faut, et jamais quand il ne le faut pas. Ce guide explique quels tags vont ensemble,
et l'idée la plus importante : **qui fait quoi à qui**.

Les numéros de tags viennent de [catalogue/TAGS.md](../../catalogue/TAGS.md). Dans le
gestionnaire de médias, sélectionnez une vignette puis *Edit tags…* ; tapez un mot dans
*Filter* pour trouver un tag (en français ou en anglais).

## Comment les jeux utilisent vos tags

Un jeu demande « un média qui a **tous** ces tags, **aucun** de ceux-là, et aucun tag de ces
types ». Deux conséquences :

1. **Un tag oublié cache le média.** Une demande *Kissing + M>F + bedroom* ne trouve jamais une
   scène de baiser taguée sans *bedroom*.
2. **Un tag oublié laisse aussi passer le média là où il ne devrait pas.** Une scène calme
   demande souvent « aucun tag de type *Action* » : une image sexuelle taguée sans son action y
   apparaîtrait.

Les jeux demandent de quelques façons typiques, et les tags s'organisent de la même manière :

| Le jeu veut… | Il demande avec… |
| --- | --- |
| une personne seule (présenter un personnage, un portrait, une pose) | genre + âge + cadrage |
| quelqu'un qui fait quelque chose à quelqu'un | action + direction |
| un lieu ou un objet, sans personne | `312 No person` + lieu / accessoires |

Donc **les tags dépendent du contexte de l'image** : certains n'ont de sens qu'ensemble, et la
même information n'est jamais donnée deux fois.

## Contexte 1 — une personne seule

Un portrait, une pose, une personne qui fait quelque chose seule (se baigner, marcher, danser,
dormir).

**Toujours ensemble :**

- **Genre** (type 1) : `1 Woman`, `2 Man` ou `3 Trans woman` ;
- **Tranche d'âge** (type 17) : l'âge apparent, de `292` à `296` ;
- **Cadrage** (type 3) : `8 Upper-body portrait`, `9 Full-body view`, `37 Pelvis close-up`,
  `40 Back view`.

Une personne seule est le cas par défaut : `313 One person` est facultatif.

Puis, s'il y a lieu : une action **intransitive** (voir plus bas) comme `341 Bathing`,
`202 Walking`, `261 Dance`, `174 Self-display` ; et les tags valables dans tous les contextes.

> Une femme qui prend un bain, vue en entier : `1 Woman`, `293 Age 25 to 35`,
> `9 Full-body view`, `341 Bathing`, `196 Bathtub`, `167 Nude`.

Le cadrage et l'âge décrivent *une* personne : ils appartiennent à ce contexte. Dans une scène
entre plusieurs personnes, ils ne sont pas nécessaires.

## Contexte 2 — quelqu'un fait quelque chose à quelqu'un

### Transitive ou intransitive ?

Une seule question pour chaque action : **quelqu'un le fait-il à quelqu'un ?**

- **Intransitive** : personne ne la reçoit — se baigner, marcher, danser, poser, dormir. C'est le
  contexte 1 (ou plusieurs personnes côte à côte, chacune pour soi).
- **Transitive** : quelqu'un le fait à quelqu'un — laver quelqu'un, masser, embrasser, lécher,
  tout acte sexuel. C'est ce contexte-ci.

#### Le test : peut-on le faire à quelqu'un d'autre ?

**Laver** et **se baigner** se ressemblent, mais ne se taguent pas pareil :

- **On peut laver quelqu'un** : laver est transitif. On lave quelqu'un d'autre *ou soi-même*, et
  dans les deux cas il y a quelqu'un qui reçoit l'action, donc une direction.
- **On ne baigne pas quelqu'un** : se baigner est intransitif. On est simplement dans l'eau ;
  personne ne reçoit l'action, donc **jamais** de direction.

| Image | Tags |
| --- | --- |
| Une femme se baigne | `341 Bathing` (+ genre, âge, cadrage : contexte 1) |
| Une femme se lave (elle-même) | `297 wash` + `137 F>self` |
| Une femme lave un homme | `297 wash` + `70 F>M` |
| Une femme lave une autre femme | `297 wash` + `120 F>F` |

Ce n'est pas la grammaire qui décide : en français, « se laver » et « se baigner » s'écrivent
tous les deux avec « se ». Demandez-vous seulement : **cette action pourrait-elle être faite à
quelqu'un d'autre ?** Si oui, elle est transitive — même quand la personne se la fait à
elle-même (se laver, se caresser, se masturber), et sa direction est alors `…>self`.

**Et quand c'est un objet qui agit ?** On met **deux directions** : celle de l'objet, qui dit ce
qui pénètre (`300 item > F`, `301 item > M`, `302 item > T`), et celle de la personne qui le
tient, qui dit qui le fait à qui. C'est cette seconde direction qui distingue les scènes :

| Image | Tags |
| --- | --- |
| Une femme s'introduit un gode | `56 Vaginal penetration`, `22 Dildo`, `300 item > F`, `137 F>self` |
| Une femme pénètre une autre femme avec un gode | `56 Vaginal penetration`, `22 Dildo`, `300 item > F`, `120 F>F` |
| Un homme pénètre une femme avec un gode | `56 Vaginal penetration`, `22 Dildo`, `300 item > F`, `69 M>F` |

### Une action transitive a toujours une direction

C'est **obligatoire** : toute action transitive va avec un tag de direction (type 10, *Actor
relationship*) qui dit qui agit sur qui, **celui qui agit en premier** :

| Tag | Sens |
| --- | --- |
| `69 M>F` | un homme le fait à une femme |
| `70 F>M` | une femme le fait à un homme |
| `120 F>F` | une femme le fait à une femme |
| `125 M>M` | un homme le fait à un homme |
| `71 M>T`, `72 T>M`, `139 F>T`, `140 T>F`, `257 T>T` | idem avec une femme trans |
| `137 F>self`, `138 M>self`, `136 T>self` | quelqu'un se le fait à soi-même (masturbation, caresses) |
| `80 M=F` | un homme et une femme se le font l'un à l'autre, sans meneur |
| `300 item > F`, `301 item > M`, `302 item > T` | un objet ou une machine agit sur quelqu'un (avec, en plus, la direction de qui le tient) |

### Pas de tag de genre ici

La direction dit déjà qui est là : `69 M>F` signifie un homme et une femme. **N'ajoutez pas les
tags de genre** (`1 Woman`, `2 Man`…) : ils répéteraient la direction, et feraient sortir la
scène pour les demandes « une femme seule ». De même pour se le faire à soi-même :
`137 F>self` dit déjà que c'est une femme.

> Une femme qui lave un homme : `297 wash`, `70 F>M`, `196 Bathtub`.
>
> Une femme qui se masturbe : `15 female masturbation`, `137 F>self`, `199 bed`.

La direction distingue des images que rien d'autre ne distingue : `193 cunny` avec `69 M>F`
(un homme lèche une femme) et `193 cunny` avec `120 F>F` (une femme lèche une femme) sont deux
médias très différents. Sans la direction, un jeu qui demande l'un obtient l'autre — ou rien.

### Aussi dans ce contexte

- **Position** (type 18), quand elle est reconnaissable : `422 Cowgirl`, `425 Doggy style`…
- **Plusieurs actions** : taguez chacune, avec **toutes les directions vraies**. Un homme qui
  pénètre une femme qui lèche une autre femme : `56 Vaginal penetration`, `69 M>F`,
  `193 cunny`, `120 F>F`.
- **Groupes** (trois personnes ou plus) : ajoutez le nombre de participants
  (`250 Three people`, `251 Four people`…) et, si un sexe domine nettement,
  `47 Male-majority group` ou `48 Female-majority group`.

## Contexte 3 — personne sur l'image

`312 No person`, avec le lieu, les accessoires et l'ambiance : une taverne vide, un donjon, un
jouet.

## Tags valables dans tous les contextes

À ajouter à toute image quand ils sont vrais et visibles :

- **Lieu** (type 12), seulement s'il est reconnaissable et compte pour la scène (voir plus bas) :
  `376 bedroom`, `383 bathroom`, `245 woods`, `486 Medieval tavern`…
- **Ambiance** (type 7) : `17 Gothic`, `85 Middle Ages`, `39 Wet`, `203 sleeping`…
- **Tenue** (type 19) : un seul niveau, de `167 Nude` à `456 Fully covered`.
- **Traits physiques** (type 4) : `4 Visible penis`, `5 Visible breasts`, `27 Red hair`,
  `23 Tattoo`…
- **Accessoires** (type 5) : corde, collier, talons, gode…
- **Point de vue** (type 11) : `106 male pov`, `107 female pov`… quand la caméra est le regard
  d'une personne de la scène.
- **Race fantastique** (type 14) et **rôle** (type 16) : `244 Elf`, `228 Succubus`,
  `267 Mage`, `266 Warrior`…
- **Statut** (type 8) : `51 domination`, `46 Submission`, quand l'image le montre.
- **Consentement** (type 13) : un seul niveau, tel que la scène le présente, de
  `217 Enthusiastic consent` à `222 No consent`. Joueurs et jeux s'en servent pour éviter ce
  qu'ils ne veulent pas voir : taguez-le honnêtement dès que la scène suggère autre chose qu'un
  consentement simple.
- **Hypnose** (type 9) : uniquement pour les médias sur ce thème.

### Médias génériques : parfois, ne pas mettre de lieu

Un jeu peut exclure un **type entier** de tags. Il s'en sert pour obtenir une image *neutre*,
qui ne donne pas de couleur particulière à une scène qui n'en a pas besoin. Par exemple, une
scène où le lieu n'a aucune importance demande l'action et la direction, **en excluant le type
Lieu (12)** : seuls les médias sans lieu peuvent sortir.

Donc, quand le décor est neutre ou indistinct (fond uni, flou, gros plan où l'on ne voit rien
autour), **ne mettez pas de lieu**. Ce média devient un média générique, utilisable partout où
le lieu ne compte pas.

> Une femme qui fait une fellation sur un fond neutre : `6 Blowjob`, `70 F>M`, sans lieu. Elle
> sortira pour « une fellation, lieu sans importance » (type Lieu exclu), et ne viendra pas
> plaquer une chambre ou une forêt sur une scène qui se passe ailleurs.

Même logique pour l'ambiance (type 7) : ne la taguez que si elle se voit vraiment. Un tag de
lieu ou d'ambiance « au cas où » retire le média des demandes génériques.

Certains tags sont **exclus par défaut** (47, 48, 66, 135, 143, 163, 168) : un média qui en
porte un ne sort que si la demande le réclame explicitement. Taguez-les quand ils sont vrais ;
le média reste simplement hors des demandes ordinaires.

Le tag 291 de la tranche d'âge est un tag protégé, avec ses propres règles (norme, section 12) :
les outils le refusent là où il n'a pas sa place.

## Portraits et packs personnage

Un **portrait** est l'image qu'un jeu montre pour présenter une personne, et l'entrée d'un pack
personnage. C'est le contexte 1, sans action transitive :

- **toujours** : genre, tranche d'âge, cadrage (`313 One person` est facultatif : seul est le cas
  par défaut) ;
- **ce qui la rend reconnaissable**, car un jeu qui présente « une rousse gothique en corset »
  cherche exactement ces tags :
  - **cheveux** (type 4) : couleur (`27 Red hair`, `448 Blonde hair`, `449 Brown hair`) et
    coupe (`481 Long hair`, `482 Shaved head`) ;
  - **style vestimentaire** (type 7) : `17 Gothic`, `50 steampunk`, `61 vintage`… ;
  - **vêtements distinctifs** (type 5) : `49 Corset`, `43 Dress`, `153 Latex`, `33 Leather`,
    `118 Maid outfit`, `398 Nurse outfit`, `473 Suit and tie`, `28 High heels`, `334 Boots`… ;
  - **état d'habillement** (type 19), un seul niveau : `456 Fully covered`,
    `457 Normally dressed`, `458 Revealing outfit`, `459 Highly revealing outfit` ou `167 Nude` ;
  - **classe du personnage**, pour un RPG (type 16) : `266 Warrior`, `267 Mage`, `268 Priest`,
    `269 Archer`, `274 Rogue`, `272 Barbarian`, `276 Shaman or druid`… ;
  - **race fantastique** (type 14) : `244 Elf`, `228 Succubus`, `229 Demon`… ;
  - et si l'image le montre : statut (type 8), tatouages (`23 Tattoo`).

Il manque une couleur de cheveux ou un vêtement ? Il se crée dans ce dépôt, comme tout tag
([catalogue/README.md](../../catalogue/README.md)).

À quoi servent les packs personnage et comment les jeux s'en servent :
[packs personnage](packs-personnage.md).

Dans un pack personnage, taguez chaque média selon son propre contexte : les portraits et
images seules comme le contexte 1, les scènes avec quelqu'un d'autre comme le contexte 2.

## Erreurs fréquentes

| Erreur | Conséquence | Correction |
| --- | --- | --- |
| Action transitive sans direction | La mauvaise combinaison sort, ou rien | Toujours ajouter la direction du type 10 |
| Tags de genre sur une scène avec direction | La scène sort pour les demandes « personne seule » | Les retirer : la direction dit qui est là |
| Une direction sur une action intransitive | Le bain seul ne sort plus pour les demandes « personne seule » | Direction seulement pour une action faite à quelqu'un |
| Cadrage ou âge absent d'un portrait | Le portrait ne sort jamais pour présenter un personnage | Genre + âge + cadrage, toujours ensemble |
| Pas de tag d'action sur une image sexuelle | Elle apparaît dans les scènes calmes qui excluent le type *Action* | Toujours taguer l'action |
| Taguer ce qui est sous-entendu mais pas visible | Résultats décevants | Ne taguer que ce que l'image montre |
| Un lieu sur un fond neutre, « au cas où » | Le média ne sort plus pour les demandes génériques (type Lieu exclu) | Pas de lieu quand le décor ne se distingue pas |
| Pas de tag de consentement sur une scène non consentie | Les joueurs qui l'excluent la voient quand même | Taguer honnêtement le niveau de consentement |

## Vérifier son travail

Ouvrez la **prévisualisation** (fenêtre d'accueil › *Preview the media in your browser*) :
incluez les tags qu'un jeu demanderait et tirez plusieurs fois. Votre média doit sortir pour
ses tags, et ne plus sortir quand vous excluez l'un d'eux. Dans le gestionnaire, le filtre *Tag*
montre tous les médias qui portent un tag : pratique pour repérer un oubli.
