"""Selection and tagging rules of the EPMTS-HTTP standard (sections 4 and 12).

Every reader (HTTP server, pack reader, editor) goes through these functions, so the
default exclusions and the protected-age rule can never differ between surfaces.
"""

MAX_TAGS_PER_LIST = 32

# Excluded unless the request includes at least one of them; including one lifts them all.
LIFTABLE_DEFAULT_EXCLUSIONS = (47, 48, 66, 135, 143, 163, 168)

# "Age other". Excluded unless explicitly included, and never combined with a porn action.
PROTECTED_AGE_TAG_ID = 291

# The tag type whose porn-flagged tags make a media sexually explicit.
ACTION_TYPE_ID = 6

MEDIA_FAMILIES = {
    "still": ("image/jpeg", "image/png", "image/webp"),
    "gif": ("image/gif",),
    "film": ("video/webm", "video/mp4", "video/x-m4v"),
}
MEDIA_FAMILIES["animated"] = MEDIA_FAMILIES["gif"] + MEDIA_FAMILIES["film"]

FORMAT_TYPES = {
    "img": MEDIA_FAMILIES["still"],
    "gif": MEDIA_FAMILIES["gif"],
    "video": MEDIA_FAMILIES["animated"],
    "animated": MEDIA_FAMILIES["animated"],
    "all": MEDIA_FAMILIES["still"] + MEDIA_FAMILIES["animated"],
}

# The SQL predicate that finds the porn-flagged action tags of the catalogue.
PORN_ACTION_SQL = "SELECT id FROM tag_media WHERE type_tag = {} AND porn = 1".format(ACTION_TYPE_ID)


class RuleViolation(ValueError):
    """A tag set or a request that the standard forbids."""


# Returns the porn-flagged action tag ids of an open DB-API connection.
def porn_action_ids(connection):
    cursor = connection.cursor()
    cursor.execute(PORN_ACTION_SQL)
    return {int(row[0]) for row in cursor.fetchall()}


# Refuses a media tag set that pairs the protected age tag with a porn action tag.
def check_media_tags(tag_ids, porn_actions):
    tag_ids = {int(tag_id) for tag_id in tag_ids}
    if PROTECTED_AGE_TAG_ID in tag_ids and tag_ids & set(porn_actions):
        raise RuleViolation(
            "Tag {} (Age other) can never be set on a media that has a porn action tag ({}).".format(
                PROTECTED_AGE_TAG_ID, ", ".join(str(t) for t in sorted(tag_ids & set(porn_actions)))
            )
        )


# Resolves include/exclude lists into the effective exclusions, or None when nothing may match.
def resolve_exclusions(include, exclude, porn_actions):
    include = set(include)
    exclude = set(exclude)
    porn_actions = set(porn_actions)
    if PROTECTED_AGE_TAG_ID in include and include & porn_actions:
        return None
    if not include & set(LIFTABLE_DEFAULT_EXCLUSIONS):
        exclude.update(LIFTABLE_DEFAULT_EXCLUSIONS)
    if PROTECTED_AGE_TAG_ID in include:
        exclude.update(porn_actions)
    else:
        exclude.add(PROTECTED_AGE_TAG_ID)
    return exclude


# Builds the random-selection query and its parameters for SQLite ("?") or MySQL ("%s").
def build_selection_sql(include, exclude, exclude_types, media_format, max_video_time, porn_actions, dialect="sqlite"):
    effective_exclude = resolve_exclusions(include, exclude, porn_actions)
    if effective_exclude is None:
        return None, None
    mark = "?" if dialect == "sqlite" else "%s"
    random_function = "RANDOM()" if dialect == "sqlite" else "RAND()"
    where = []
    params = []

    # Fills a list of placeholders and appends the matching values.
    def placeholders(values):
        values = sorted(values)
        params.extend(values)
        return ", ".join(mark for _ in values)

    where.append("m.type IN ({})".format(placeholders(FORMAT_TYPES[media_format])))
    for tag_id in sorted(set(include)):
        where.append("EXISTS (SELECT 1 FROM media_has_tag_media li WHERE li.media_id = m.id AND li.tag_media_id = {})".format(mark))
        params.append(tag_id)
    if effective_exclude:
        where.append(
            "NOT EXISTS (SELECT 1 FROM media_has_tag_media le WHERE le.media_id = m.id AND le.tag_media_id IN ({}))".format(
                placeholders(effective_exclude)
            )
        )
    if exclude_types:
        clause = (
            "NOT EXISTS (SELECT 1 FROM media_has_tag_media lt JOIN tag_media tt ON tt.id = lt.tag_media_id "
            "WHERE lt.media_id = m.id AND tt.type_tag IN ({})".format(placeholders(set(exclude_types)))
        )
        if include:
            clause += " AND lt.tag_media_id NOT IN ({})".format(placeholders(set(include)))
        where.append(clause + ")")
    if max_video_time is not None:
        where.append(
            "(m.type NOT IN ({}) OR m.duration IS NULL OR m.duration <= {})".format(
                placeholders(MEDIA_FAMILIES["film"]), mark
            )
        )
        params.append(max_video_time)
    # Invariant, whatever the request: never a media holding the protected tag and a porn action.
    where.append(
        "NOT (EXISTS (SELECT 1 FROM media_has_tag_media lm WHERE lm.media_id = m.id AND lm.tag_media_id = {protected}) "
        "AND EXISTS (SELECT 1 FROM media_has_tag_media lp JOIN tag_media tp ON tp.id = lp.tag_media_id "
        "WHERE lp.media_id = m.id AND tp.type_tag = {action} AND tp.porn = 1))".format(
            protected=PROTECTED_AGE_TAG_ID, action=ACTION_TYPE_ID
        )
    )
    sql = "SELECT m.id, m.hash, m.type, m.duration FROM media m WHERE {} ORDER BY {} LIMIT 1".format(
        " AND ".join(where), random_function
    )
    return sql, params


# Validates a tagIdList value from a request and returns distinct positive ints.
def parse_tag_list(value, name):
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuleViolation("{} must be an array".format(name))
    ids = set()
    for item in value:
        if isinstance(item, bool):
            raise RuleViolation("{} holds an invalid tag id".format(name))
        if isinstance(item, int) and item > 0:
            ids.add(item)
        elif isinstance(item, str) and item.isdigit() and int(item) > 0:
            ids.add(int(item))
        else:
            raise RuleViolation("{} holds an invalid tag id".format(name))
    if len(ids) > MAX_TAGS_PER_LIST:
        raise RuleViolation("{} holds more than {} tags".format(name, MAX_TAGS_PER_LIST))
    return sorted(ids)
