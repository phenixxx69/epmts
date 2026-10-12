/**
 * EPMTS preview page, in two modes:
 *  - local (opened by double click, file://): reads a pack folder directly with epmts-pack.js,
 *    no server needed;
 *  - API (served at /preview/ by the server): a small client of the EPMTS-HTTP API. The API key
 *    is kept in this browser only (localStorage).
 */
var EpmtsPreview = {
    local: window.location.protocol === 'file:',
    apiBase: window.location.origin,
    apiKey: '',
    pack: null,
    persons: {},
    state: {include: [], exclude: [], excludeTypes: []},

    // Restores the key and the request from the URL hash, then wires the forms.
    init: function () {
        try {
            EpmtsPreview.apiKey = localStorage.getItem('epmts_api_key') || '';
        } catch (error) {
            EpmtsPreview.apiKey = '';
        }
        document.getElementById('api_key').value = EpmtsPreview.apiKey;
        document.getElementById(EpmtsPreview.local ? 'api_key_label' : 'pack_path_label').style.display = 'none';
        document.getElementById('mode_note').textContent = EpmtsPreview.local
            ? 'Local mode: the pack folder is read directly, no server needed. Files are shown as stored (convert is ignored).'
            : 'Server mode: requests go to the EPMTS server API.';
        EpmtsPreview.readHash();
        document.getElementById('connection').addEventListener('submit', EpmtsPreview.handleConnect);
        document.getElementById('pack_folder').addEventListener('change', EpmtsPreview.handlePickFolder);
        document.getElementById('request').addEventListener('submit', EpmtsPreview.handleDraw);
        document.getElementById('copy_link').addEventListener('click', EpmtsPreview.handleCopyLink);
        document.getElementById('clear').addEventListener('click', EpmtsPreview.handleClear);
        document.getElementById('tag_filter').addEventListener('input', EpmtsPreview.handleFilter);
        document.getElementById('tags').addEventListener('click', EpmtsPreview.handleTagClick);
        document.getElementById('tags').addEventListener('contextmenu', EpmtsPreview.handleTagClick);
        ['include', 'exclude', 'exclude_types'].forEach(function (id) {
            document.getElementById(id).addEventListener('change', EpmtsPreview.handleListEdit);
        });
        if (EpmtsPreview.local || EpmtsPreview.apiKey) {
            EpmtsPreview.loadTags();
        }
    },

    // Parses "1, 2,3" into distinct positive ints.
    parseIds: function (text) {
        var ids = [];
        String(text || '').split(',').forEach(function (part) {
            var id = parseInt(part.trim(), 10);
            if (id > 0 && ids.indexOf(id) === -1) {
                ids.push(id);
            }
        });
        return ids;
    },

    // Calls the API with the key; resolves the parsed JSON.
    call: function (method, path, body) {
        var options = {method: method, headers: {'Authorization': 'Bearer ' + EpmtsPreview.apiKey}};
        if (body) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }
        return fetch(path.indexOf('http') === 0 ? path : EpmtsPreview.apiBase + path, options).then(function (response) {
            return response.json().then(function (json) {
                if (!response.ok && response.status !== 404) {
                    throw new Error(response.status + ' ' + (json.error || ''));
                }
                return json;
            });
        });
    },

    // Saves the key (server mode) and loads the catalogue.
    handleConnect: function (event) {
        event.preventDefault();
        if (EpmtsPreview.local) {
            EpmtsPreview.pack = null;
            EpmtsPreview.persons = {};
            EpmtsPreview.loadTags();
            return;
        }
        EpmtsPreview.apiKey = document.getElementById('api_key').value.trim();
        try {
            localStorage.setItem('epmts_api_key', EpmtsPreview.apiKey);
        } catch (error) {
            // private mode: the key just is not remembered
        }
        EpmtsPreview.loadTags();
    },

    // Loads the catalogue (from the pack or from /tags) and draws it.
    loadTags: function () {
        var container = document.getElementById('tags');
        container.textContent = 'Loading…';
        if (EpmtsPreview.local) {
            EpmtsPreview.openPack().then(EpmtsPreview.showPack, function () {
                container.textContent = 'No pack found at "' + EpmtsPreview.packUrl() + '". Click "Choose a pack folder…" '
                    + 'and select the folder of your pack (the one holding tags.sqlite), for example packs/main.';
            });
            return;
        }
        EpmtsPreview.call('GET', '/tags').then(EpmtsPreview.renderTags, function (error) {
            container.textContent = 'Cannot load the tags (' + error.message + '). Check the API key.';
        });
    },

    // Shows the catalogue of the opened local pack.
    showPack: function (pack) {
        var count = pack.column('SELECT COUNT(*) FROM media')[0];
        document.getElementById('mode_note').textContent = 'Local mode, no server needed: ' + count + ' media in the pack. '
            + 'Files are shown as stored (convert is ignored).';
        EpmtsPreview.renderTags({tags: pack.tags().map(EpmtsPreview.toApiTag)});
    },

    // Opens the pack folder the user picked.
    handlePickFolder: function (event) {
        var container = document.getElementById('tags');
        container.textContent = 'Reading the folder…';
        EpmtsPack.fromFileList(event.target.files).then(function (pack) {
            EpmtsPreview.pack = pack;
            EpmtsPreview.persons = {};
            EpmtsPreview.showPack(pack);
        }, function (error) {
            container.textContent = 'Cannot open this folder: ' + error.message + '.';
        });
    },

    // Returns the pack URL typed in the form, ending with "/".
    packUrl: function () {
        var url = document.getElementById('pack_path').value.trim() || '../packs/main/';
        return url.slice(-1) === '/' ? url : url + '/';
    },

    // Opens the local pack once.
    openPack: function () {
        if (EpmtsPreview.pack) {
            return Promise.resolve(EpmtsPreview.pack);
        }
        return EpmtsPack.load(EpmtsPreview.packUrl()).then(function (pack) {
            EpmtsPreview.pack = pack;
            return pack;
        });
    },

    // Turns a pack tag row into the shape of the API catalogue.
    toApiTag: function (row) {
        return {
            id: row.id,
            name: row.name || '',
            description: row.description || '',
            descriptionFr: row.description_fr || '',
            typeId: row.type_tag,
            typeName: row.type_name || '',
            logoBase64: row.logo && EpmtsPreview.local ? '../catalogue/logos/' + row.id + '.png' : null
        };
    },

    // Answers a request from the local pack, like the server would (person packs included).
    selectLocal: function (body) {
        var options = {
            include: body.includeTagImg,
            exclude: body.excludeTagImg,
            excludeTypes: body.excludeTypeTag,
            format: body.format,
            maxVideoTime: body.max_video_time
        };
        return EpmtsPreview.openPack().then(function (pack) {
            if (!body.referenceHash) {
                return pack;
            }
            var hash = body.referenceHash.toLowerCase();
            if (!EpmtsPreview.persons[hash]) {
                EpmtsPreview.persons[hash] = pack.personByHash(hash);
            }
            return EpmtsPreview.persons[hash];
        }).then(function (source) {
            var media = source ? source.select(options) : null;
            if (!media) {
                return {found: false};
            }
            var answer = {found: true, format: /^video|gif$/.test(media.type) ? 'video' : 'img', converted: true, url: media.url, type: media.type, tags: source.mediaTags(media.hash)};
            return source.person(media).then(function (person) {
                answer.url = media.url;
                if (person) {
                    answer.referenceHash = media.hash;
                }
                return answer;
            });
        });
    },

    // Draws the catalogue grouped by type.
    renderTags: function (answer) {
        var container = document.getElementById('tags');
        var groups = {};
        var order = [];
        container.textContent = '';
        answer.tags.forEach(function (tag) {
            var key = tag.typeId === null ? 0 : tag.typeId;
            if (!groups[key]) {
                groups[key] = {name: tag.typeName || '-', tags: []};
                order.push(key);
            }
            groups[key].tags.push(tag);
        });
        order.sort(function (a, b) { return a - b; });
        order.forEach(function (typeId) {
            var block = document.createElement('div');
            var title = document.createElement('span');
            block.className = 'type';
            title.className = 'type-name';
            title.dataset.typeId = typeId;
            title.title = 'Click to exclude / include this whole type';
            title.textContent = '#' + typeId + ' ' + groups[typeId].name;
            block.appendChild(title);
            block.appendChild(document.createElement('br'));
            groups[typeId].tags.forEach(function (tag) {
                block.appendChild(EpmtsPreview.buildTagButton(tag));
            });
            container.appendChild(block);
        });
        EpmtsPreview.refreshMarks();
    },

    // Builds one tag chip.
    buildTagButton: function (tag) {
        var button = document.createElement('button');
        var id = document.createElement('span');
        button.type = 'button';
        button.className = 'tag';
        button.dataset.tagId = tag.id;
        button.dataset.search = (tag.name + ' ' + tag.description + ' ' + tag.descriptionFr + ' ' + tag.id).toLowerCase();
        button.title = tag.description || tag.name;
        if (tag.logoBase64) {
            var logo = document.createElement('img');
            logo.src = tag.logoBase64;
            logo.alt = '';
            button.appendChild(logo);
        }
        id.className = 'id';
        id.textContent = '#' + tag.id;
        button.appendChild(id);
        button.appendChild(document.createTextNode(' ' + tag.name));
        return button;
    },

    // Click includes a tag, right/Alt click excludes it, a type name toggles its exclusion.
    handleTagClick: function (event) {
        var type = event.target.closest('.type-name');
        var tag = event.target.closest('.tag');
        if (!type && !tag) {
            return;
        }
        event.preventDefault();
        EpmtsPreview.readLists();
        if (type) {
            EpmtsPreview.toggle('excludeTypes', parseInt(type.dataset.typeId, 10));
        } else if (event.type === 'contextmenu' || event.altKey) {
            EpmtsPreview.toggle('exclude', parseInt(tag.dataset.tagId, 10), 'include');
        } else {
            EpmtsPreview.toggle('include', parseInt(tag.dataset.tagId, 10), 'exclude');
        }
        EpmtsPreview.writeLists();
    },

    // Adds or removes an id from one list (and from its opposite list).
    toggle: function (list, id, opposite) {
        var values = EpmtsPreview.state[list];
        var position = values.indexOf(id);
        if (position === -1) {
            values.push(id);
        } else {
            values.splice(position, 1);
        }
        if (opposite && EpmtsPreview.state[opposite].indexOf(id) !== -1) {
            EpmtsPreview.state[opposite].splice(EpmtsPreview.state[opposite].indexOf(id), 1);
        }
    },

    // Reads the three id fields into the state.
    readLists: function () {
        EpmtsPreview.state.include = EpmtsPreview.parseIds(document.getElementById('include').value);
        EpmtsPreview.state.exclude = EpmtsPreview.parseIds(document.getElementById('exclude').value);
        EpmtsPreview.state.excludeTypes = EpmtsPreview.parseIds(document.getElementById('exclude_types').value);
    },

    // Writes the state into the fields and the chip colours.
    writeLists: function () {
        document.getElementById('include').value = EpmtsPreview.state.include.join(',');
        document.getElementById('exclude').value = EpmtsPreview.state.exclude.join(',');
        document.getElementById('exclude_types').value = EpmtsPreview.state.excludeTypes.join(',');
        EpmtsPreview.refreshMarks();
    },

    // Re-reads the fields after a manual edit.
    handleListEdit: function () {
        EpmtsPreview.readLists();
        EpmtsPreview.refreshMarks();
    },

    // Colours included / excluded chips and excluded types.
    refreshMarks: function () {
        var state = EpmtsPreview.state;
        document.querySelectorAll('#tags .tag').forEach(function (button) {
            var id = parseInt(button.dataset.tagId, 10);
            button.classList.toggle('is-included', state.include.indexOf(id) !== -1);
            button.classList.toggle('is-excluded', state.exclude.indexOf(id) !== -1);
        });
        document.querySelectorAll('#tags .type-name').forEach(function (title) {
            title.classList.toggle('is-excluded', state.excludeTypes.indexOf(parseInt(title.dataset.typeId, 10)) !== -1);
        });
    },

    // Hides the chips that do not match the filter text.
    handleFilter: function (event) {
        var text = event.target.value.trim().toLowerCase();
        document.querySelectorAll('#tags .tag').forEach(function (button) {
            button.style.display = !text || button.dataset.search.indexOf(text) !== -1 ? '' : 'none';
        });
    },

    // Builds the selection request from the form.
    buildRequest: function () {
        EpmtsPreview.readLists();
        var body = {
            format: document.getElementById('format').value,
            includeTagImg: EpmtsPreview.state.include,
            excludeTagImg: EpmtsPreview.state.exclude,
            excludeTypeTag: EpmtsPreview.state.excludeTypes,
            convert: document.getElementById('convert').value
        };
        var maxTime = parseInt(document.getElementById('max_video_time').value, 10);
        var reference = document.getElementById('reference_hash').value.trim();
        if (maxTime > 0) {
            body.max_video_time = maxTime;
        }
        if (reference) {
            body.referenceHash = reference;
        }
        return body;
    },

    // Sends /select and shows the answer.
    handleDraw: function (event) {
        event.preventDefault();
        var body = EpmtsPreview.buildRequest();
        EpmtsPreview.writeHash(body);
        EpmtsPreview.showMessage('Drawing…');
        var request = EpmtsPreview.local ? EpmtsPreview.selectLocal(body) : EpmtsPreview.call('POST', '/select', body);
        request.then(function (answer) {
            EpmtsPreview.showAnswer(body, answer);
        }, function (error) {
            EpmtsPreview.showMessage('Error: ' + error.message);
        });
    },

    // Shows a media answer, polling while a conversion runs.
    showAnswer: function (body, answer) {
        document.getElementById('exchange').textContent = 'POST /select ' + JSON.stringify(body, null, 1) + '\n\n' + JSON.stringify(answer, null, 1);
        if (!answer.found) {
            EpmtsPreview.showMessage('Nothing found for this request.');
            return;
        }
        if (!answer.converted && answer.statusUrl) {
            EpmtsPreview.showMessage('Converting… ' + answer.elapsedSeconds + ' s');
            setTimeout(EpmtsPreview.poll, answer.retryAfterSeconds * 1000, body, answer.statusUrl);
            return;
        }
        if (!answer.converted) {
            EpmtsPreview.showMessage('Conversion failed (' + answer.error + ').');
            return;
        }
        EpmtsPreview.renderMedia(answer);
    },

    // Polls the status address of a running conversion.
    poll: function (body, statusUrl) {
        EpmtsPreview.call('POST', statusUrl, {format: body.format, convert: body.convert}).then(function (answer) {
            EpmtsPreview.showAnswer(body, answer);
        });
    },

    // Puts the delivered file in the page.
    renderMedia: function (answer) {
        var box = document.getElementById('result');
        box.textContent = '';
        var path = EpmtsPreview.local ? answer.url : new URL(answer.url).pathname;
        if (/\.ivf$/.test(path)) {
            EpmtsPreview.showMessage('IVF (VP8) is a game format browsers cannot play: choose convert "none" to watch it here.');
            return;
        }
        var isVideo = EpmtsPreview.local ? /^video\//.test(answer.type) : answer.format === 'video' && !/\.gif$/.test(path);
        var element = document.createElement(isVideo ? 'video' : 'img');
        element.src = answer.url;
        if (element.tagName === 'VIDEO') {
            element.controls = true;
            element.loop = true;
            element.autoplay = true;
            element.muted = true;
        }
        box.appendChild(element);
        if (answer.tags) {
            var tags = document.createElement('div');
            tags.className = 'message';
            tags.textContent = 'Tags of this media: ' + answer.tags.join(', ');
            box.appendChild(tags);
        }
        if (answer.referenceHash) {
            var button = document.createElement('button');
            button.type = 'button';
            button.textContent = 'This is a person portrait: draw from this person';
            button.addEventListener('click', function () {
                document.getElementById('reference_hash').value = answer.referenceHash;
            });
            box.appendChild(button);
        }
    },

    // Shows a short text in the result area.
    showMessage: function (text) {
        var box = document.getElementById('result');
        var message = document.createElement('div');
        message.className = 'message';
        message.textContent = text;
        box.textContent = '';
        box.appendChild(message);
    },

    // Stores the request in the URL hash, for sharing.
    writeHash: function (body) {
        history.replaceState(null, '', '#' + encodeURIComponent(JSON.stringify(body)));
    },

    // Restores a request from the URL hash.
    readHash: function () {
        var body;
        try {
            body = JSON.parse(decodeURIComponent(location.hash.slice(1)));
        } catch (error) {
            return;
        }
        document.getElementById('include').value = (body.includeTagImg || []).join(',');
        document.getElementById('exclude').value = (body.excludeTagImg || []).join(',');
        document.getElementById('exclude_types').value = (body.excludeTypeTag || []).join(',');
        document.getElementById('format').value = body.format || 'img';
        document.getElementById('convert').value = body.convert || 'none';
        document.getElementById('max_video_time').value = body.max_video_time || '';
        document.getElementById('reference_hash').value = body.referenceHash || '';
        EpmtsPreview.readLists();
    },

    // Copies a link to this exact request.
    handleCopyLink: function () {
        EpmtsPreview.writeHash(EpmtsPreview.buildRequest());
        navigator.clipboard.writeText(location.href).then(function () {
            EpmtsPreview.showMessage('Link copied.');
        }, function () {
            EpmtsPreview.showMessage(location.href);
        });
    },

    // Empties the request.
    handleClear: function () {
        EpmtsPreview.state = {include: [], exclude: [], excludeTypes: []};
        document.getElementById('reference_hash').value = '';
        EpmtsPreview.writeLists();
        document.getElementById('result').textContent = '';
        document.getElementById('exchange').textContent = '';
    }
};
