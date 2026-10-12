/**
 * EPMTS offline pack reader for browser games.
 *
 * Reads a pack folder with sql.js, without any server: from its URL (tags.sql.js + medias/, works
 * from file:// and any static host), or from a folder the user picks (<input webkitdirectory>). Applies the same selection rules as the HTTP server
 * (standard sections 4 and 11.4): families, default exclusions, protected-age rule.
 *
 * Needs vendor/sql.js/sql-asm.js loaded first (it defines initSqlJs).
 *
 *   EpmtsPack.load('../packs/main/').then(function (pack) {
 *       var media = pack.select({include: [1, 56], format: 'img'});
 *       if (media) { img.src = media.url; }
 *   });
 */
var EpmtsPack = (function () {
    'use strict';

    var LIFTABLE_DEFAULT_EXCLUSIONS = [47, 48, 66, 135, 143, 163, 168];
    var PROTECTED_AGE_TAG_ID = 291;
    var ACTION_TYPE_ID = 6;
    var FAMILIES = {
        still: ['image/jpeg', 'image/png', 'image/webp'],
        gif: ['image/gif'],
        film: ['video/webm', 'video/mp4', 'video/x-m4v']
    };
    var FORMAT_TYPES = {
        img: FAMILIES.still,
        gif: FAMILIES.gif,
        video: FAMILIES.gif.concat(FAMILIES.film),
        animated: FAMILIES.gif.concat(FAMILIES.film),
        all: FAMILIES.still.concat(FAMILIES.gif, FAMILIES.film)
    };
    var sqlPromise = null;
    var loadQueue = Promise.resolve();

    // Returns the sql.js module, initialised once.
    function getSql() {
        if (!sqlPromise) {
            sqlPromise = initSqlJs();
        }
        return sqlPromise;
    }

    // Returns distinct positive integer ids from a list.
    function normalizeIds(values) {
        var ids = [];
        (values || []).forEach(function (value) {
            var id = parseInt(value, 10);
            if (id > 0 && ids.indexOf(id) === -1) {
                ids.push(id);
            }
        });
        return ids;
    }

    // Loads one tags.sql.js script and returns the SQL text it defines (scripts load one at a time).
    function loadDumpScript(url) {
        var task = loadQueue.then(function () {
            return new Promise(function (resolve, reject) {
                var script = document.createElement('script');
                window.db_str = undefined;
                script.src = url;
                script.onload = function () {
                    script.remove();
                    resolve(window.db_str);
                };
                script.onerror = function () {
                    script.remove();
                    reject(new Error('cannot load ' + url));
                };
                document.head.appendChild(script);
            });
        });
        loadQueue = task.catch(function () {});
        return task;
    }

    // A pack folder reached by URL: files are relative URLs, person packs load their tags.sql.js.
    function UrlSource(baseUrl) {
        this.baseUrl = baseUrl;
    }

    // Returns the URL of a file of the pack.
    UrlSource.prototype.fileUrl = function (relativePath) {
        return this.baseUrl + relativePath;
    };

    // Opens the person pack named by a portrait hash (rejects when there is none).
    UrlSource.prototype.openPerson = function (hash) {
        return EpmtsPack.load(this.baseUrl + 'medias/' + hash + '/', true);
    };

    // A pack folder picked by the user: files are File objects keyed by their path in the pack.
    function FileSource(files) {
        this.files = files;
        this.urls = {};
    }

    // Returns a blob URL for a file of the pack (made once).
    FileSource.prototype.fileUrl = function (relativePath) {
        if (!this.urls[relativePath] && this.files[relativePath]) {
            this.urls[relativePath] = URL.createObjectURL(this.files[relativePath]);
        }
        return this.urls[relativePath] || '';
    };

    // Opens the person pack named by a portrait hash from the picked files.
    FileSource.prototype.openPerson = function (hash) {
        var prefix = 'medias/' + hash + '/';
        var files = {};
        Object.keys(this.files).forEach(function (path) {
            if (path.indexOf(prefix) === 0) {
                files[path.slice(prefix.length)] = this.files[path];
            }
        }, this);
        return openFiles(files, true);
    };

    // Opens a pack from File objects keyed by their path inside the pack.
    function openFiles(files, isPerson) {
        if (!files['tags.sqlite']) {
            return Promise.reject(new Error('no tags.sqlite in this folder: it is not a pack'));
        }
        return Promise.all([getSql(), files['tags.sqlite'].arrayBuffer()]).then(function (results) {
            return new Pack(new results[0].Database(new Uint8Array(results[1])), new FileSource(files), isPerson);
        });
    }

    // An opened pack: a sql.js database plus the source of its files.
    function Pack(db, source, isPerson) {
        this.db = db;
        this.source = source;
        this.isPerson = isPerson;
        this.pornActions = this.column('SELECT id FROM tag_media WHERE type_tag = ' + ACTION_TYPE_ID + ' AND porn = 1');
    }

    // Runs a query and returns its rows as objects.
    Pack.prototype.rows = function (sql, params) {
        var statement = this.db.prepare(sql);
        var rows = [];
        statement.bind(params || []);
        while (statement.step()) {
            rows.push(statement.getAsObject());
        }
        statement.free();
        return rows;
    };

    // Runs a query and returns its first column.
    Pack.prototype.column = function (sql, params) {
        return this.rows(sql, params).map(function (row) {
            return row[Object.keys(row)[0]];
        });
    };

    // Returns the tag catalogue with type names.
    Pack.prototype.tags = function () {
        return this.rows('SELECT tm.id, tm.name, tm.logo, tm.subcategory_name, tm.description, tm.description_fr, tm.porn, tm.type_tag, tt.name AS type_name '
            + 'FROM tag_media tm LEFT JOIN type_tag tt ON tt.id = tm.type_tag ORDER BY tt.position, tt.id, tm.name');
    };

    // Returns the tag ids of one media hash.
    Pack.prototype.mediaTags = function (hash) {
        return this.column('SELECT l.tag_media_id FROM media_has_tag_media l JOIN media m ON m.id = l.media_id WHERE m.hash = ?', [hash]);
    };

    // Computes the effective exclusions, or null when nothing may match (protected-age rule).
    Pack.prototype.resolveExclusions = function (include, exclude) {
        var pornActions = this.pornActions;
        var hasPorn = include.some(function (id) { return pornActions.indexOf(id) !== -1; });
        var result = exclude.slice();
        if (include.indexOf(PROTECTED_AGE_TAG_ID) !== -1 && hasPorn) {
            return null;
        }
        var liftsDefaults = include.some(function (id) { return LIFTABLE_DEFAULT_EXCLUSIONS.indexOf(id) !== -1; });
        if (!liftsDefaults) {
            result = result.concat(LIFTABLE_DEFAULT_EXCLUSIONS);
        }
        if (include.indexOf(PROTECTED_AGE_TAG_ID) !== -1) {
            result = result.concat(pornActions);
        } else {
            result.push(PROTECTED_AGE_TAG_ID);
        }
        return normalizeIds(result);
    };

    /**
     * Draws one random media. options: include, exclude, excludeTypes (tag id arrays),
     * format (img|gif|video|animated|all, default img), maxVideoTime (seconds).
     * Returns {hash, type, url, duration} or null.
     */
    Pack.prototype.select = function (options) {
        options = options || {};
        var include = normalizeIds(options.include);
        var excludeTypes = normalizeIds(options.excludeTypes);
        var exclude = this.resolveExclusions(include, normalizeIds(options.exclude));
        var types = FORMAT_TYPES[options.format || 'img'];
        if (exclude === null || !types) {
            return null;
        }
        var where = [];
        var params = [];
        var marks = function (values) {
            params.push.apply(params, values);
            return values.map(function () { return '?'; }).join(', ');
        };
        where.push('m.type IN (' + marks(types) + ')');
        include.forEach(function (id) {
            where.push('EXISTS (SELECT 1 FROM media_has_tag_media li WHERE li.media_id = m.id AND li.tag_media_id = ?)');
            params.push(id);
        });
        if (exclude.length) {
            where.push('NOT EXISTS (SELECT 1 FROM media_has_tag_media le WHERE le.media_id = m.id AND le.tag_media_id IN (' + marks(exclude) + '))');
        }
        if (excludeTypes.length) {
            var clause = 'NOT EXISTS (SELECT 1 FROM media_has_tag_media lt JOIN tag_media tt ON tt.id = lt.tag_media_id '
                + 'WHERE lt.media_id = m.id AND tt.type_tag IN (' + marks(excludeTypes) + ')';
            if (include.length) {
                clause += ' AND lt.tag_media_id NOT IN (' + marks(include) + ')';
            }
            where.push(clause + ')');
        }
        if (options.maxVideoTime) {
            where.push('(m.type NOT IN (' + marks(FAMILIES.film) + ') OR m.duration IS NULL OR m.duration <= ?)');
            params.push(Number(options.maxVideoTime));
        }
        // Invariant: never a media holding the protected tag and a porn action.
        where.push('NOT (EXISTS (SELECT 1 FROM media_has_tag_media lm WHERE lm.media_id = m.id AND lm.tag_media_id = ' + PROTECTED_AGE_TAG_ID + ') '
            + 'AND EXISTS (SELECT 1 FROM media_has_tag_media lp JOIN tag_media tp ON tp.id = lp.tag_media_id '
            + 'WHERE lp.media_id = m.id AND tp.type_tag = ' + ACTION_TYPE_ID + ' AND tp.porn = 1))');
        var rows = this.rows('SELECT m.hash, m.type, m.duration FROM media m WHERE ' + where.join(' AND ') + ' ORDER BY RANDOM() LIMIT 1', params);
        if (!rows.length) {
            return null;
        }
        rows[0].url = this.source.fileUrl('medias/' + rows[0].hash);
        return rows[0];
    };

    /**
     * Opens the person pack of a selected portrait (PR-1), or resolves null when the media is not
     * a portrait. Also fixes media.url: a portrait file lives inside its person pack.
     */
    Pack.prototype.person = function (media) {
        if (this.isPerson || !media || !/^[0-9a-f]{64}$/.test(media.hash)) {
            return Promise.resolve(null);
        }
        return this.personByHash(media.hash).then(function (person) {
            if (person) {
                media.url = person.source.fileUrl('medias/' + media.hash);
            }
            return person;
        });
    };

    // Opens the person pack of a referenceHash, or resolves null when there is none.
    Pack.prototype.personByHash = function (hash) {
        if (this.isPerson || !/^[0-9a-f]{64}$/.test(hash)) {
            return Promise.resolve(null);
        }
        return this.source.openPerson(hash).catch(function () {
            return null;
        });
    };

    return {
        LIFTABLE_DEFAULT_EXCLUSIONS: LIFTABLE_DEFAULT_EXCLUSIONS,
        PROTECTED_AGE_TAG_ID: PROTECTED_AGE_TAG_ID,

        // Loads a pack from its folder URL (ending with "/"); resolves a Pack.
        load: function (baseUrl, isPerson) {
            if (baseUrl.slice(-1) !== '/') {
                baseUrl += '/';
            }
            return Promise.all([getSql(), loadDumpScript(baseUrl + 'tags.sql.js')]).then(function (results) {
                if (typeof results[1] !== 'string') {
                    throw new Error(baseUrl + 'tags.sql.js does not define db_str');
                }
                var db = new results[0].Database();
                db.exec(results[1]);
                return new Pack(db, new UrlSource(baseUrl), !!isPerson);
            });
        },

        // Opens a pack from the FileList of an <input type="file" webkitdirectory>: the pack is
        // the picked folder or the shallowest folder holding tags.sqlite.
        fromFileList: function (fileList) {
            var all = Array.prototype.slice.call(fileList);
            var roots = all.filter(function (file) {
                return /(^|\/)tags\.sqlite$/.test(file.webkitRelativePath || file.name);
            }).map(function (file) {
                return (file.webkitRelativePath || file.name).slice(0, -'tags.sqlite'.length);
            }).sort(function (a, b) {
                return a.split('/').length - b.split('/').length;
            });
            if (!roots.length) {
                return Promise.reject(new Error('no tags.sqlite in this folder: it is not a pack'));
            }
            var files = {};
            all.forEach(function (file) {
                var path = file.webkitRelativePath || file.name;
                if (path.indexOf(roots[0]) === 0) {
                    files[path.slice(roots[0].length)] = file;
                }
            });
            return openFiles(files, false);
        }
    };
}());
