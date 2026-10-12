# EPMTS-HTTP 1.0 — Easy Porn Media Tag System, HTTP and pack standard

## Status and scope

This document specifies version `1.0` of the EPMTS media-tag protocol. It defines the observable
HTTP interface between a media-tag client and server, the Media Pack format (`MP-1`) through
which the same catalogue and selection rules are delivered for local use, and the tagging rules
every tool MUST enforce. Apart from that pack format, it does not specify storage, indexing,
file naming, link generation, conversion software, or any other server implementation detail.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.
An implementation conforms to the Core Profile when it satisfies sections 1 through 8 and
section 12. The optional Person Reference Profile (`PR-1`) is specified in section 9, and the
Media Pack Profile (`MP-1`) in section 11.

An instance exposes a configurable base URL, denoted by `B`, for example:

```
http://127.0.0.1:5055
```

A client MUST configure `B` as a complete URL. It MUST resolve only these relative routes:
`/tags`, `/select`, `/media/{mediaId}`, and `/specification`. A client MUST NOT infer `B` from
another API base URL.

## 1. Transport and authentication

1. Every request MUST carry `Authorization: Bearer <credential>`, except `GET B/specification`,
   which MUST be served without any credential, and the temporary URLs of sections 6 and 7.
2. Credential issuance and renewal are outside this standard. An instance MAY be configured by
   its owner to accept requests without a credential (for example a server only reachable from
   the same computer); it then ignores the `Authorization` header. A client SHOULD send the
   header whenever it holds a credential.
3. A request with no acceptable credential MUST receive `403` with a generic response.
4. JSON request bodies and JSON responses MUST be UTF-8 and use
   `Content-Type: application/json`.
5. A conforming request MUST receive `200` unless another status is specified below.
6. The server MUST return `400` for an invalid JSON body or a value outside this standard.
7. The server MUST NOT disclose an internal path, original file name, internal identifier,
   secret, call stack, or infrastructure detail in a response or error.
8. A client MUST ignore response members it does not recognize.

## 2. Atomic values

| Name | Definition |
| --- | --- |
| `tagId` | A strictly positive JSON integer. An unsigned decimal string is also accepted on input. |
| `tagIdList` | An array of zero to 32 `tagId` values. Duplicate values have one semantic occurrence. |
| `mediaId` | An opaque string of 8 to 255 `[A-Za-z0-9_-]` characters. |
| `referenceHash` | A case-insensitive, 64-character hexadecimal SHA-256 string. |
| `formatSelector` | One of `img`, `gif`, `video`, `animated`, or `all`. |
| `conversion` | One of `auto`, `none`, `png`, `jpg`, or `ivf`. |
| `temporaryUrl` | An absolute URL with bounded validity. It is not a durable identifier. |

A `tagIdList` containing another type or more than 32 distinct values is invalid. A server MAY
ignore an unknown request member. A client MUST NOT rely on an ignored member to alter a result.

## 3. Tag catalogue

### `GET B/tags`

The server MUST return an object containing a `tags` array:

```json
{
  "tags": [
    {
      "id": 12,
      "name": "string",
      "keywords": "string",
      "subcategory": "string",
      "description": "string",
      "descriptionFr": "string",
      "typeId": 1,
      "typeName": "string",
      "logoBase64": "data:image/png;base64,..."
    }
  ]
}
```

| Member | Requirement |
| --- | --- |
| `id` | A `tagId`, stable for the lifetime of the catalogue. |
| `name` | A string; it MAY be empty. |
| `keywords` | A legacy alias of `subcategory`; a string that MAY be empty. |
| `subcategory` | A string identifying the tag subcategory; it MAY be empty. |
| `description` | English keywords and short description; a string that MAY be empty. |
| `descriptionFr` | French keywords and short description; a string that MAY be empty. |
| `typeId` | A `tagId` or `null`. |
| `typeName` | A string; it MAY be empty. |
| `logoBase64` | OPTIONAL. A PNG data URI for the tag logo, fitted within 100 × 100 pixels. It MUST be omitted when no usable logo is defined. |

A client MUST use `id`, not textual fields, in a selection request.

### 3.1 Catalogue authority

Tag and tag-type identifiers belong to one shared catalogue, published in the EPMTS repository
(`catalogue/catalogue.json`). **That repository is the only place where a tag or a tag type is
created.** The same `id` designates the same tag in every conforming server, client and pack.

1. An implementation MUST NOT create, renumber or reuse a tag or tag-type `id`.
2. A retired `id` is listed in the catalogue and MUST NOT be given to another tag.
3. A new tag receives the next free `id` from the repository catalogue, never from a local tool.
4. A pack or a server MAY lag behind the catalogue; it is brought up to date by replacing its
   `type_tag` and `tag_media` rows with the catalogue ones, which never changes an `id`.

## 4. Media selection

### `POST B/select`

The request body is a JSON object. The following Core Profile members affect selection:

| Member | Type | Default | Requirement |
| --- | --- | --- | --- |
| `format` | `formatSelector` | `img` | The eligible media family. |
| `includeTagImg` | `tagIdList` | `[]` | Every listed tag MUST be associated with the selected media. |
| `excludeTagImg` | `tagIdList` | `[]` | No listed tag MUST be associated with the selected media. |
| `excludeTypeTag` | `tagIdList` | `[]` | A media with a tag of a listed type MUST be excluded, except for an explicitly included tag. |
| `convert` | `conversion` | `auto` | The requested delivered representation. |
| `max_video_time` | Integer from 1 to 3600 | Absent | The maximum acceptable film duration. It is a filter, never a trimming instruction. |

The selector families are defined as follows:

| Value | Eligible set |
| --- | --- |
| `img` | Still media. |
| `gif` | Animated GIF media. |
| `video` | All animated media, including GIF media. |
| `animated` | All animated media, including GIF media. |
| `all` | All media. |

The families are defined by media type as follows:

| Family | Media types |
| --- | --- |
| Still | `image/jpeg`, `image/png`, `image/webp` |
| GIF | `image/gif` |
| Film | `video/webm`, `video/mp4`, `video/x-m4v` |
| Animated | GIF and Film |

#### 4.1 Default exclusions

The tags `47`, `48`, `66`, `135`, `143`, `163` and `168` are excluded by default: they MUST be
added to `excludeTagImg` unless `includeTagImg` contains at least one of them. Including any one
of them lifts these seven default exclusions for that selection.

#### 4.2 Protected age tag

Tag `291` ("Age other") is governed by section 12 and is never part of the group above:

1. Tag `291` MUST be added to `excludeTagImg` unless `includeTagImg` contains `291` itself.
   Including another default tag MUST NOT lift it.
2. When `includeTagImg` contains `291`, every porn action tag (section 12) MUST be added to
   `excludeTagImg`.
3. A request whose `includeTagImg` contains both `291` and a porn action tag MUST be answered
   with `{"found": false}`.
4. Whatever the request, a server MUST NOT select a media associated with both `291` and a
   porn action tag.

#### 4.3 Maximum duration

`max_video_time` applies to Film media only. GIF and still media MUST NOT be filtered by
duration. A server MAY deliver a film whose duration cannot be determined; a pack builder MUST
NOT include one when a maximum duration is requested (section 11).

The server MUST select media satisfying every applicable criterion, or return exactly:

```json
{"found": false}
```

The server MAY select randomly among eligible media.

## 5. Delivered representation

The `convert` member specifies the delivered representation, not the selection family.

| Value | Requirement |
| --- | --- |
| `none` | The server MUST deliver the selected native representation. |
| `png` | The server MUST deliver a still PNG image. |
| `jpg` | The server MUST deliver a still JPEG image. |
| `ivf` | The server MUST deliver video in the instance's declared IVF profile. |
| `auto` | The server MUST deliver still media for `img`, video for `gif`, `video`, and `animated`, and may select either representation for `all`. |

An explicit `png` or `jpg` request for GIF or video media MUST produce a still image. The still
image MUST represent the first usable image of the animated media. How that image is produced
is outside this standard.

The IVF profile of the reference server is VP8 (`VP80` FourCC), constant 30 frames per second,
at most 1280 pixels wide and 60 seconds long, with the sound track, when there is one, delivered
separately as OGG Vorbis (`audioUrl`). Game engines that decode VP8 only depend on it.

## 6. Ready response

When media is deliverable, `POST B/select` and `POST B/media/{mediaId}` MUST return:

```json
{
  "found": true,
  "mediaId": "opaque-media-id",
  "format": "img",
  "converted": true,
  "url": "https://example.invalid/temporary-media-url",
  "audioUrl": null
}
```

| Member | Requirement |
| --- | --- |
| `found` | MUST be `true`. |
| `mediaId` | An opaque `mediaId`, stable for the same available media. |
| `format` | `img` or `video`; it describes the delivered file, not the requested selector. |
| `converted` | MUST be `true`. |
| `url` | A `temporaryUrl` for the media. Its path SHOULD end with the file extension (`.png`, `.jpg`, `.ivf`...). |
| `audioUrl` | `null` or a `temporaryUrl` for audio associated with delivered video. |

The server MUST NOT use a directly guessable internal identifier or source-file hash as a
`mediaId`.

## 7. Deferred conversion and poster image

If the requested representation is not ready, the server MUST return:

```json
{
  "found": true,
  "mediaId": "opaque-media-id",
  "format": "video",
  "converted": false,
  "retryAfterSeconds": 1,
  "elapsedSeconds": 12,
  "statusUrl": "https://example.invalid/media/opaque-media-id",
  "posterUrl": "https://example.invalid/temporary-poster-url"
}
```

`retryAfterSeconds` MUST be a positive integer. A client MUST NOT call `statusUrl` before that
delay. `elapsedSeconds` MUST be a non-negative integer. `statusUrl` MUST be an absolute URL
for `POST B/media/{mediaId}`.

`posterUrl` is optional. A server capable of extracting a still image from GIF or video media
MUST return it. The image MUST meet the first-usable-image rule in section 5.

For a definitive failure, the server MUST return `found: true`, `converted: false`, and
`error: "conversion_failed"`. It MUST NOT return `statusUrl` in that state. It MAY still return
an already available `posterUrl`.

## 8. Media re-description

### `POST B/media/{mediaId}`

This route MUST describe the media designated by `mediaId`; it MUST NOT perform another draw.
Its body MAY contain `format`, `convert`, and `max_video_time`, under the rules in section 4.
`includeTagImg`, `excludeTagImg`, `excludeTypeTag`, and all other selection members MUST NOT
alter the re-described media.

An unknown, expired, or invalid `mediaId` MUST return `{"found": false}` or `404`, without
revealing whether another resource exists.

## 9. PR-1 — Person continuity by reference

A server implementing `PR-1` accepts the optional `referenceHash` member on `POST B/select`.
The value MUST be a valid `referenceHash`. The same reference identifies a stable person context
across every selection carrying it.

A client obtains a reference by being handed a portrait: when the media described by a ready or
deferred response (sections 6 and 7) is the portrait of a person context, the response MUST carry
that context's `referenceHash` member, and MUST NOT carry one otherwise.

1. The server MUST select exclusively in the context associated with `referenceHash`.
2. Requests carrying the same `referenceHash` MUST preserve the same reference person, even
   when they return distinct matching media.
3. An absent context or a context with no eligible media MUST return `{"found": false}`.
4. The server MUST NOT silently fall back to the unreferenced catalogue or another context.
5. The server MUST NOT provide an operation that enumerates or searches `referenceHash` values.
6. A client MUST send only a hash obtained in its own authorized context.

A context is the person pack of the portrait whose SHA-256 is `referenceHash` (section 11.1.1):
selection in it follows the section 4 rules, default exclusions and protected-age rule
included. How the server stores it is outside this standard.

A Core Profile server that does not implement `PR-1` MUST NOT ignore `referenceHash`: it MUST
answer a selection carrying one with `{"found": false}`, as a `PR-1` server holding no context
does. A malformed `referenceHash` MUST receive `400`.

Context construction, persistence, and authorization are outside this standard and MUST NOT be
exposed in protocol messages.

### 9.1 Person flow

`PR-1` supports the whole person flow, the same way over HTTP and in a pack (section 11):

| Step | HTTP | Pack |
| --- | --- | --- |
| Choose a person's portrait | `POST B/select` on the catalogue, with the portrait criteria | Selection in the pack database |
| Learn the person's reference | `referenceHash` member of the response, present only for a person-context portrait | `media.hash` of the selected row, which names a person pack only when `medias/<hash>/` exists |
| Draw the person's media | `POST B/select` with the same criteria plus `referenceHash` | Selection in the person pack `medias/<referenceHash>/` |
| Fall back when the person has none | A new `POST B/select` with the same criteria and no `referenceHash`, after `{"found": false}` | A new selection in the enclosing pack, after an empty result |
| Show the portrait or a media again | `POST B/media/{mediaId}` with the `mediaId` kept from the first answer | The file of the kept `media.hash` |

1. The fallback is always the caller's explicit decision; neither a server nor a pack reader
   performs it silently.
2. A `mediaId` returned by a selection with a reference MUST remain re-describable through
   section 8, like any other `mediaId`.
3. Keeping the association between the caller's own person and its `referenceHash` is the
   caller's responsibility and is outside this standard.

## 10. Standard retrieval

### `GET B/specification`

The server MUST return this exact document with
`Content-Type: text/markdown; charset=utf-8`. This route MUST NOT require authentication: the
standard is public, and a client MUST be able to read it before it holds any credential. The
document is the normative source for a compatible client or server implementation.

## 11. MP-1 — Media Pack format

A media pack delivers a subset of the media, with the whole catalogue, for local selection. Any
conforming client or local server MUST be able to read any pack, and packs MUST be mergeable.

### 11.1 Layout

A pack is one directory containing exactly:

| Entry | Requirement |
| --- | --- |
| `tags.sqlite` | The SQLite database specified in 11.2. |
| `tags.sql` | An SQL dump that rebuilds `tags.sqlite` when run as one script. |
| `tags.sql.js` | A script defining `var encodedStr`, the base64 encoding of the UTF-8 bytes of `tags.sql`, and `var db_str`, that text decoded as UTF-8. |
| `pack.json` | REQUIRED in a distributed pack, absent from person packs (11.1.2). |
| `medias/<sha256>` | One file per media, named by the lowercase SHA-256 of its content, without extension. |
| `medias/<portraitSha256>/` | OPTIONAL. A person pack (11.1.1). |

The directory MUST NOT contain any other file. A pack MUST NOT carry an original file name, an
internal path or an internal identifier.

#### 11.1.1 Person packs

A person pack gathers the media showing one same person. It is a directory named by the
lowercase SHA-256 of that person's portrait, and it is itself a pack in this format, except that
it MUST NOT contain a person pack. Its database holds only that person's media, the portrait
included, and the whole catalogue.

The enclosing pack's database MUST hold the portrait as a media row whose `hash` is the portrait
SHA-256. That row is how the person is chosen; its file is stored only once, in the person pack,
at `medias/<portraitSha256>/medias/<portraitSha256>`. The portrait SHA-256 is the `referenceHash`
of `PR-1` (section 9).

#### 11.1.2 Manifest

A pack handed to other people carries `pack.json`, a UTF-8 JSON object:

```json
{
  "format": "EPMTS-MP-1",
  "project": "https://github.com/phenixxx69/epmts",
  "name": "Pack name",
  "author": "Author",
  "version": "1.0",
  "date": "2026-10-11",
  "description": "optional text",
  "media_count": 120
}
```

`project` MUST be exactly `https://github.com/phenixxx69/epmts`, the original project every pack
derives from. A tool that builds a pack MUST write it; a reader, importer or validator MUST refuse
a manifest without it or with another value. `name`, `author`, `version` and `date` (`YYYY-MM-DD`)
MUST be non-empty strings of at most 255 characters. `name` is what importers record as the origin of the media (11.2). A reader MUST
ignore unknown members. A working pack kept by its owner MAY have no manifest; an importer
then uses the name of the imported file or folder.

### 11.2 Database

| Table | Columns |
| --- | --- |
| `type_tag` | `id` INTEGER PRIMARY KEY, `name` NOT NULL, `position`, `color` |
| `tag_media` | `id` INTEGER PRIMARY KEY, `name`, `logo`, `type_tag` → `type_tag.id`, `subcategory_name`, `description`, `description_fr`, `ia_text`, `porn` INTEGER NOT NULL (0 or 1) |
| `media` | `id` INTEGER PRIMARY KEY, `size`, `hash` UNIQUE NOT NULL, `unique_use`, `type` NOT NULL, `size_x`, `size_y`, `path`, `duration`, `origin` |
| `media_has_tag_media` | `media_id` → `media.id`, `tag_media_id` → `tag_media.id`, PRIMARY KEY (`media_id`, `tag_media_id`) |

1. `type_tag` and `tag_media` MUST hold the whole shared catalogue under its `id` values
   (section 3), whatever media the pack holds.
2. `media.hash` MUST equal the name of the media file, which is in the same pack, or in the
   person pack of that name for a portrait (11.1.1). `media.type` MUST be one of the media types
   of section 4. `media.path` MUST be NULL. `media.duration` is the length in seconds, or NULL.
   `media.origin` is the name of the pack the media was imported from, or NULL for a media its
   owner added locally. A distributed pack SHOULD have no NULL origin.
3. `media.id` is local to the pack and carries no meaning outside it; `media.hash` identifies a
   media across packs.
4. Every media MUST carry all its tags, not only those that caused its selection, so that any
   request can be answered from the pack.
5. The database MUST satisfy its foreign keys. It SHOULD index `media.type`,
   `tag_media.type_tag` and (`tag_media_id`, `media_id`).
6. No media MAY break the tagging rules of section 12.

### 11.3 Media files

A media file MUST keep only the data needed to decode and display it: EXIF, XMP, IPTC,
comments, container tags and any other metadata MUST be removed. A colour profile MAY be kept.

### 11.4 Selection in a pack

A reader MUST apply the section 4 rules to a pack: families, `excludeTypeTag` semantics,
default exclusions, protected-age rule and maximum duration. A selection by `referenceHash`
MUST use only the person pack of that name, under the `PR-1` rules; when it finds nothing, a
caller MAY then make a new selection without reference, but the reader MUST NOT do so silently.
When a pack is built for a maximum duration, it MUST NOT contain a Film longer than that
duration or of unknown duration.

### 11.5 Merging

Packs are merged by union. Media with the same `hash` are the same media: they appear once, with
the union of their tags. Tag identifiers are kept unchanged. `media.id` values MAY be reassigned.
A media new to the target keeps its `origin`; when that is NULL, it takes the `name` of the
imported pack's manifest. A media already in the target keeps its own `origin`.
Person packs with the same portrait SHA-256 are merged by the same rules.

### 11.6 Creating a pack

A pack built for distribution from a working pack holds either every media or only the local
ones (`origin` NULL), the person packs whose portrait it holds, and a manifest. In it, a media
without origin takes the new pack's `name`; the builder SHOULD then record that name as the
`origin` of the exported local media in the working pack, so that a later build of local media
does not include them again. A media whose united
tags would break section 12 MUST NOT be merged; the merge tool MUST report it.

## 12. Tagging rules

A **porn action tag** is a tag of type `6` (Action) whose `porn` column is `1`.

1. Tag `291` ("Age other") MUST NEVER be associated with a media that is associated with a
   porn action tag. It describes non-sexual content only.
2. Every tool that creates or changes tag associations (editors, import scripts, merge tools,
   pack builders) MUST refuse an association set that breaks rule 1.
3. A pack validator MUST report any media that breaks rule 1, and a reader MUST NOT select it
   (section 4.2).
4. These rules cannot be disabled by configuration.
