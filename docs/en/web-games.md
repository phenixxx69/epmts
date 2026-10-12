# Browser games

A browser game can read a pack **directly**, without any server: `tags.sql.js` is a plain
script, and `web/epmts-pack.js` applies the same selection rules as the server.

## Minimal example

Folder layout:

```
my-game/
├── index.html
├── epmts/
│   ├── epmts-pack.js           (copy of web/epmts-pack.js)
│   └── sql-asm.js              (copy of web/vendor/sql.js/sql-asm.js)
└── pack/                       (your pack folder: tags.sql.js + medias/)
```

`index.html`:

```html
<img id="picture" alt="">
<script src="epmts/sql-asm.js"></script>
<script src="epmts/epmts-pack.js"></script>
<script>
    EpmtsPack.load('pack/').then(function (pack) {
        // Woman (1) + vaginal penetration (56), still pictures only
        var media = pack.select({include: [1, 56], format: 'img'});
        if (media) {
            document.getElementById('picture').src = media.url;
        }
    });
</script>
```

This works when the page is opened by double-click (`file://`) and on any static web host.
`sql-asm.js` is the pure-JavaScript build of sql.js: unlike the WebAssembly build it needs no
`.wasm` download, which browsers block on `file://`.

`web/example-browser-game.html` is a complete demo (scenes, videos, a person kept across
scenes). Open it by double-click: it reads `packs/main`, or another folder given as
`example-browser-game.html?pack=../path/to/pack/`.

## API of `epmts-pack.js`

| Call | Result |
| --- | --- |
| `EpmtsPack.load(folderUrl)` | Promise of a pack. `folderUrl` ends with `/`. |
| `pack.select(options)` | `{hash, type, url, duration}` or `null`. |
| `pack.tags()` | The catalogue: `{id, name, type_tag, type_name, description, description_fr, porn, logo}`. |
| `pack.mediaTags(hash)` | The tag ids of a media. |
| `pack.person(media)` | Promise of the person pack of a portrait, or `null` when the media is not a portrait. Also fixes `media.url` (a portrait file lives inside its person pack). |

`select` options:

| Option | Meaning |
| --- | --- |
| `include` | Tag ids the media must all have. |
| `exclude` | Tag ids the media must not have. |
| `excludeTypes` | Tag type ids: a media with any tag of these types is left out (except included tags). |
| `format` | `img` (still pictures, default), `gif`, `video` / `animated` (GIF and films), `all`. |
| `maxVideoTime` | Longest film accepted, in seconds. |

The default exclusions and the tagging rules of the [standard](../../standard/EPMTS-HTTP.md)
(sections 4 and 12) are always applied; they cannot be turned off.

Media files have no extension. `<img>` and `<video>` recognise them by content; give a
`<video>` element `muted` and `autoplay` if it must start alone.

## Person continuity

Why and how: [Person packs](person-packs.md).

```js
var portrait = pack.select({include: [1, 8], format: 'img'});
pack.person(portrait).then(function (person) {
    // person is null when this portrait has no person pack
    var next = (person && person.select({include: [56]})) || pack.select({include: [1, 56]});
});
```

The fallback to the whole pack is your decision, as the standard requires.

## The preview page

`web/preview.html` lets you try requests:

- opened by **double-click**, it reads a pack folder directly (default `../packs/main/`), shows
  each drawn media and its tags — no server needed;
- served by the **server** at `http://127.0.0.1:5055/preview/`, it calls the HTTP API with your
  key, exactly like a game, conversions included.

Click a tag to include it, right-click (or Alt+click) to exclude it, click a type name to
exclude the whole type. *Copy link* keeps the request in the address for later.

## Using the server instead

If your game runs on a web server and the pack is large, or you want conversions, call the
HTTP API (see [server.md](server.md)). Never put an API key in public JavaScript: call the
API from your own back end.
