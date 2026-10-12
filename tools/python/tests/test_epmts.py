"""Tests of the rules, the pack format and the HTTP server.

Run from the repository root:  python -m unittest discover -s tools/python/tests
(the server tests need flask and Pillow; the video test needs ffmpeg).
"""

import base64
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "server"))

from epmts import rules  # noqa: E402
from epmts import media as media_tools  # noqa: E402
from epmts.pack import Pack, PackError  # noqa: E402

PORN_ACTION = 6       # "Blowjob": action type, porn = 1
SOFT_ACTION = 1       # "Woman": gender type, porn = 0
HYPNO = 66            # one of the liftable default exclusions
AGE_OTHER = rules.PROTECTED_AGE_TAG_ID


# Writes a small PNG with a text chunk (metadata that the import must remove).
def make_png(path, color):
    from PIL import Image, PngImagePlugin
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "original-name-should-vanish")
    Image.new("RGB", (40, 30), color).save(path, "PNG", pnginfo=info)


# Writes a small JPEG carrying an EXIF block.
def make_jpeg(path, color):
    from PIL import Image
    image = Image.new("RGB", (20, 10), color)
    exif = Image.Exif()
    exif[0x010E] = "secret description"
    image.save(path, "JPEG", exif=exif.tobytes())


class RulesTest(unittest.TestCase):
    """Default exclusions and the protected-age rule."""

    # Every default is excluded when nothing special is included.
    def test_defaults_excluded(self):
        excluded = rules.resolve_exclusions([SOFT_ACTION], [], {PORN_ACTION})
        self.assertTrue(set(rules.LIFTABLE_DEFAULT_EXCLUSIONS) <= excluded)
        self.assertIn(AGE_OTHER, excluded)

    # Including a liftable default lifts the others but never the protected age tag.
    def test_lifting_keeps_protected_excluded(self):
        excluded = rules.resolve_exclusions([HYPNO], [], {PORN_ACTION})
        self.assertNotIn(47, excluded)
        self.assertIn(AGE_OTHER, excluded)

    # The protected age tag with a porn action can never match.
    def test_protected_with_porn_action_is_refused(self):
        self.assertIsNone(rules.resolve_exclusions([AGE_OTHER, PORN_ACTION], [], {PORN_ACTION}))
        sql, _ = rules.build_selection_sql([AGE_OTHER, PORN_ACTION], [], [], "img", None, {PORN_ACTION})
        self.assertIsNone(sql)

    # Including the protected age tag excludes every porn action.
    def test_protected_included_excludes_porn(self):
        excluded = rules.resolve_exclusions([AGE_OTHER], [], {PORN_ACTION, 14})
        self.assertTrue({PORN_ACTION, 14} <= excluded)

    # A media tag set pairing both is refused.
    def test_check_media_tags(self):
        with self.assertRaises(rules.RuleViolation):
            rules.check_media_tags([AGE_OTHER, PORN_ACTION], {PORN_ACTION})
        rules.check_media_tags([AGE_OTHER, SOFT_ACTION], {PORN_ACTION})

    # Tag lists follow the standard limits.
    def test_parse_tag_list(self):
        self.assertEqual(rules.parse_tag_list(["3", 1, 3], "x"), [1, 3])
        for bad in ([0], [True], ["a"], "1", list(range(1, 34))):
            with self.assertRaises(rules.RuleViolation):
                rules.parse_tag_list(bad, "x")


class FfmpegTest(unittest.TestCase):
    # The constant frame rate option follows the ffmpeg version: -vsync before 5.1 only.
    def test_frame_rate_mode_follows_the_version(self):
        old, new = ["-vsync", "cfr"], ["-fps_mode", "cfr"]
        cases = {
            "ffmpeg version 4.3.6-0+deb11u1 Copyright (c) 2000-2023": old,
            "ffmpeg version 5.0.1": old,
            "ffmpeg version 5.1.2-3ubuntu1": new,
            "ffmpeg version n7.1 Copyright": new,
            "ffmpeg version 9.0": new,
            "ffmpeg version N-118000-g1234abcd": new,
            "ffmpeg version 2024-03-07-git-97beb63a66-full_build-www.gyan.dev": new,
        }
        for output, expected in cases.items():
            self.assertEqual(media_tools.frame_rate_mode_args(output), expected, output)


class PackTest(unittest.TestCase):
    """Creation, import, tagging, persons, merge, validation and export."""

    # Creates a scratch folder with two source pictures.
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.png = os.path.join(self.tmp, "holiday photo.png")
        self.jpg = os.path.join(self.tmp, "IMG_0001.jpg")
        make_png(self.png, "red")
        make_jpeg(self.jpg, "blue")

    # Removes the scratch folder.
    def tearDown(self):
        shutil.rmtree(self.tmp)

    # A new pack is valid, holds the catalogue and no media.
    def test_create_is_valid(self):
        with Pack.create(os.path.join(self.tmp, "pack")) as pack:
            self.assertEqual(pack.validate(), [])
            self.assertEqual(pack.conn.execute("SELECT COUNT(*) FROM media").fetchone()[0], 0)
            self.assertGreater(len(pack.tags()), 400)

    # Import strips metadata, names the file by hash and keeps no original name.
    def test_add_media_strips_metadata(self):
        with Pack.create(os.path.join(self.tmp, "pack")) as pack:
            media_id, created = pack.add_media(self.png, [SOFT_ACTION])
            jpeg_id, _ = pack.add_media(self.jpg, [SOFT_ACTION])
            self.assertTrue(created)
            row = pack.get_media(media_id)
            stored = pack.media_file(row["hash"])
            self.assertEqual(os.path.basename(stored), row["hash"])
            self.assertEqual(media_tools.sha256_file(stored), row["hash"])
            with open(stored, "rb") as handle:
                self.assertNotIn(b"original-name-should-vanish", handle.read())
            with open(pack.media_file(pack.get_media(jpeg_id)["hash"]), "rb") as handle:
                self.assertNotIn(b"secret description", handle.read())
            self.assertIsNone(row["path"])
            self.assertEqual(pack.add_media(self.png)[1], False)
            pack.export()
            self.assertEqual(pack.validate(deep=True), [])

    # The tools refuse the protected age tag with a porn action, and unknown tags.
    def test_tag_rules_enforced(self):
        with Pack.create(os.path.join(self.tmp, "pack")) as pack:
            with self.assertRaises(rules.RuleViolation):
                pack.add_media(self.png, [AGE_OTHER, PORN_ACTION])
            media_id, _ = pack.add_media(self.png, [AGE_OTHER])
            with self.assertRaises(rules.RuleViolation):
                pack.set_tags(media_id, [AGE_OTHER, PORN_ACTION])
            with self.assertRaises(rules.RuleViolation):
                pack.set_tags(media_id, [99999])

    # A person pack keeps the portrait once, inside it, and is valid.
    def test_person_pack(self):
        with Pack.create(os.path.join(self.tmp, "pack")) as pack:
            portrait = pack.create_person(self.jpg, [SOFT_ACTION])
            pack.export()
            self.assertIsNotNone(pack.person_directory(portrait))
            self.assertFalse(os.path.isfile(os.path.join(pack.directory, "medias", portrait + ".jpg")))
            with Pack(pack.person_directory(portrait)) as person:
                person.add_media(self.png, [SOFT_ACTION])
                person.export()
            self.assertEqual(pack.validate(deep=True), [])
            with self.assertRaises(PackError):
                pack.delete_media(pack.get_media_by_hash(portrait)["id"])

    # Merging unions media by hash and tags, and copies person packs.
    def test_merge(self):
        with Pack.create(os.path.join(self.tmp, "a")) as first:
            first.add_media(self.png, [SOFT_ACTION])
            first.export()
        with Pack.create(os.path.join(self.tmp, "b")) as second:
            second.add_media(self.png, [HYPNO])
            second.add_media(self.jpg, [SOFT_ACTION])
            second.create_person(self._other_portrait(), [SOFT_ACTION])
            second.export()
        with Pack(os.path.join(self.tmp, "a")) as first:
            report = first.merge_from(os.path.join(self.tmp, "b"))
            first.export()
            self.assertEqual(report["persons"], 1)
            self.assertEqual(first.media_tags(1), {SOFT_ACTION, HYPNO})
            self.assertEqual(first.validate(deep=True), [])

    # Makes a third picture used as a portrait.
    def _other_portrait(self):
        path = os.path.join(self.tmp, "portrait.png")
        make_png(path, "green")
        return path

    # tags.sql rebuilds the database and tags.sql.js carries it as UTF-8.
    def test_export_round_trip(self):
        with Pack.create(os.path.join(self.tmp, "pack")) as pack:
            pack.add_media(self.png, [SOFT_ACTION])
            pack.export()
            with open(os.path.join(pack.directory, "tags.sql"), encoding="utf-8") as handle:
                sql = handle.read()
            with open(os.path.join(pack.directory, "tags.sql.js"), encoding="utf-8") as handle:
                script = handle.read()
        rebuilt = sqlite3.connect(":memory:")
        rebuilt.executescript(sql)
        self.assertEqual(rebuilt.execute("SELECT COUNT(*) FROM media_has_tag_media").fetchone()[0], 1)
        encoded = script.split('"')[1]
        self.assertEqual(base64.b64decode(encoded).decode("utf-8"), sql)


class ImportTest(unittest.TestCase):
    """Import of a pack folder or zip, with full checks."""

    # Builds a source pack with one media and a person, and an empty target pack.
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.source = os.path.join(self.tmp, "source")
        self.target = os.path.join(self.tmp, "target")
        picture = os.path.join(self.tmp, "a.png")
        portrait = os.path.join(self.tmp, "p.png")
        make_png(picture, "red")
        make_png(portrait, "blue")
        with Pack.create(self.source) as pack:
            self.hash = pack.get_media(pack.add_media(picture, [SOFT_ACTION])[0])["hash"]
            pack.create_person(portrait, [SOFT_ACTION])
            pack.export()
        Pack.create(self.target).close()

    # Removes the scratch folder.
    def tearDown(self):
        shutil.rmtree(self.tmp)

    # Zips the source pack inside a top folder, as a download would.
    def make_zip(self, extra=None):
        import zipfile
        path = os.path.join(self.tmp, "pack.zip")
        with zipfile.ZipFile(path, "w") as archive:
            for root, _, files in os.walk(self.source):
                for name in files:
                    full = os.path.join(root, name)
                    archive.write(full, os.path.join("my-pack", os.path.relpath(full, self.source)))
            archive.writestr("__MACOSX/._junk", "x")
            if extra:
                archive.writestr(*extra)
        return path

    # A valid zip is checked and merged, person pack included; the source stays untouched.
    def test_import_zip(self):
        from epmts.importer import import_pack
        report = import_pack(self.target, self.make_zip())
        self.assertEqual((report["added"], report["persons"], report["checked"]), (2, 1, 2))
        with Pack(self.target) as target:
            self.assertEqual(target.validate(deep=True), [])

    # A file whose content does not match its hash refuses the whole import.
    def test_bad_hash_refused(self):
        from epmts.importer import ImportRefused, import_pack
        with open(os.path.join(self.source, "medias", self.hash), "ab") as handle:
            handle.write(b"tampered")
        with self.assertRaises(ImportRefused) as refused:
            import_pack(self.target, self.source)
        self.assertTrue(any("does not match its hash" in problem for problem in refused.exception.problems))
        with Pack(self.target) as target:
            self.assertEqual(target.conn.execute("SELECT COUNT(*) FROM media").fetchone()[0], 0)

    # Unsafe zip paths and incomplete packs are refused.
    def test_unsafe_and_incomplete(self):
        from epmts.importer import ImportRefused, import_pack
        with self.assertRaises(ImportRefused):
            import_pack(self.target, self.make_zip(("../evil.txt", "x")))
        os.unlink(os.path.join(self.source, "medias", self.hash))
        with self.assertRaises(ImportRefused) as refused:
            import_pack(self.target, self.source)
        self.assertTrue(any("file missing" in problem for problem in refused.exception.problems))

    # A source breaking the protected-age rule is refused.
    def test_safety_rule_refused(self):
        from epmts.importer import ImportRefused, import_pack
        with Pack(self.source) as pack:
            pack.conn.execute("INSERT INTO media_has_tag_media VALUES (1, ?), (1, ?)", (AGE_OTHER, PORN_ACTION))
            pack.conn.commit()
        with self.assertRaises(ImportRefused):
            import_pack(self.target, self.source)


class OriginTest(unittest.TestCase):
    """Media provenance, pack.json and shareable pack creation."""

    # Builds a pack with one local media and one imported from "Pack A" (with a person).
    def setUp(self):
        from epmts.importer import create_pack_zip
        self.tmp = tempfile.mkdtemp()
        self.pictures = []
        for index, color in enumerate(("red", "green", "blue", "white")):
            path = os.path.join(self.tmp, "{}.png".format(index))
            make_png(path, color)
            self.pictures.append(path)
        author = os.path.join(self.tmp, "author")
        with Pack.create(author) as pack:
            pack.add_media(self.pictures[0], [SOFT_ACTION])
            pack.create_person(self.pictures[1], [SOFT_ACTION])
            pack.export()
        self.zip_a = os.path.join(self.tmp, "a.zip")
        manifest = {"name": "Pack A", "author": "Someone", "version": "2.1", "date": "2026-01-02"}
        self.assertEqual(create_pack_zip(author, manifest, True, self.zip_a), 2)
        self.main = os.path.join(self.tmp, "main")
        with Pack.create(self.main) as pack:
            pack.add_media(self.pictures[2], [SOFT_ACTION])
            pack.export()

    # Removes the scratch folder.
    def tearDown(self):
        shutil.rmtree(self.tmp)

    # The zip carries pack.json; the author's local media are now marked with the pack name.
    def test_created_zip(self):
        import zipfile
        with zipfile.ZipFile(self.zip_a) as archive:
            manifest = json.loads(archive.read("Pack-A-2.1/pack.json"))
        self.assertEqual((manifest["name"], manifest["author"], manifest["media_count"]), ("Pack A", "Someone", 2))
        self.assertEqual(manifest["project"], "https://github.com/phenixxx69/epmts")
        with Pack(os.path.join(self.tmp, "author")) as pack:
            self.assertEqual(pack.origin_counts(), {"Pack A": 2})
            self.assertEqual(pack.validate(), [])

    # Imported media get the pack name; local ones stay local; a new pack can hold only local media.
    def test_import_then_local_pack(self):
        from epmts.importer import create_pack_zip, import_pack
        report = import_pack(self.main, self.zip_a)
        self.assertEqual((report["origin"], report["manifest"]["version"]), ("Pack A", "2.1"))
        with Pack(self.main) as pack:
            self.assertEqual(pack.origin_counts(), {None: 1, "Pack A": 2})
            with Pack(pack.person_directory(pack.person_hashes()[0])) as person:
                self.assertEqual({row[0] for row in person.conn.execute("SELECT origin FROM media")}, {"Pack A"})
            self.assertEqual(pack.validate(deep=True), [])
        mine = os.path.join(self.tmp, "mine.zip")
        count = create_pack_zip(self.main, {"name": "Mine", "author": "Me", "version": "1.0", "date": "2026-10-11"}, True, mine)
        self.assertEqual(count, 1)
        with Pack(self.main) as pack:
            self.assertEqual(pack.origin_counts(), {"Mine": 1, "Pack A": 2})
        everything = os.path.join(self.tmp, "all.zip")
        self.assertEqual(create_pack_zip(self.main, {"name": "All", "author": "Me", "version": "1", "date": "2026-10-11"}, False, everything), 3)
        other = os.path.join(self.tmp, "other")
        Pack.create(other).close()
        import_pack(other, everything)
        with Pack(other) as pack:
            self.assertEqual(pack.origin_counts(), {"Mine": 1, "Pack A": 2})  # provenance survives the merge

    # The media count of a created pack includes the media of its person packs (portrait once).
    def test_count_includes_person_media(self):
        import zipfile
        from epmts.importer import create_pack_zip
        with Pack(os.path.join(self.tmp, "author")) as pack:
            with Pack(pack.person_directory(pack.person_hashes()[0])) as person:
                person.add_media(self.pictures[3], [SOFT_ACTION])
                person.export()
        path = os.path.join(self.tmp, "count.zip")
        self.assertEqual(create_pack_zip(os.path.join(self.tmp, "author"), {"name": "C", "author": "A", "version": "1", "date": "2026-10-11"}, False, path), 3)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(json.loads(archive.read("C-1/pack.json"))["media_count"], 3)

    # A pack without pack.json is named after its zip; a bad pack.json is refused.
    def test_manifest_fallback_and_errors(self):
        from epmts.importer import ImportRefused, import_pack
        report = import_pack(self.main, os.path.join(self.tmp, "author"))
        self.assertEqual(report["origin"], "author")
        with open(os.path.join(self.tmp, "author", "pack.json"), "w") as handle:
            handle.write('{"name": "x"}')
        with self.assertRaises(ImportRefused):
            import_pack(self.main, os.path.join(self.tmp, "author"))
        # A manifest must name the original project, exactly.
        valid = {"name": "x", "author": "a", "version": "1", "date": "2026-10-11"}
        for project in (None, "https://github.com/someone/fork"):
            with open(os.path.join(self.tmp, "author", "pack.json"), "w") as handle:
                json.dump(dict(valid, project=project) if project else valid, handle)
            with self.assertRaises(ImportRefused):
                import_pack(self.main, os.path.join(self.tmp, "author"))
        from epmts.importer import create_pack_zip
        empty = os.path.join(self.tmp, "empty")
        Pack.create(empty).close()
        with self.assertRaises(PackError):
            create_pack_zip(empty, {"name": "Empty", "author": "Me", "version": "1", "date": "2026-10-11"}, True, os.path.join(self.tmp, "x.zip"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "x.zip")))


@unittest.skipUnless(__import__("importlib").util.find_spec("flask"), "flask is not installed")
class ServerTest(unittest.TestCase):
    """The EPMTS-HTTP routes over a pack."""

    # Builds a pack with a few media and a person, and a test client.
    def setUp(self):
        from epmts_server import create_app
        self.tmp = tempfile.mkdtemp()
        pack_dir = os.path.join(self.tmp, "pack")
        with Pack.create(pack_dir) as pack:
            for index, (color, tags) in enumerate((("red", [SOFT_ACTION]), ("blue", [SOFT_ACTION, PORN_ACTION]), ("white", [SOFT_ACTION, AGE_OTHER, HYPNO]))):
                path = os.path.join(self.tmp, "{}.png".format(index))
                make_png(path, color)
                pack.add_media(path, tags)
            portrait = os.path.join(self.tmp, "portrait.jpg")
            make_jpeg(portrait, "yellow")
            self.portrait = pack.create_person(portrait, [SOFT_ACTION, 8])
            with Pack(pack.person_directory(self.portrait)) as person:
                path = os.path.join(self.tmp, "person.png")
                make_png(path, "purple")
                person.add_media(path, [SOFT_ACTION, PORN_ACTION])
                person.export()
            pack.export()
        app = create_app({"pack_dir": pack_dir, "cache_dir": os.path.join(self.tmp, "cache"), "api_keys": ["k"], "link_secret": "s"})
        self.client = app.test_client()
        self.auth = {"Authorization": "Bearer k"}

    # Removes the scratch folder.
    def tearDown(self):
        shutil.rmtree(self.tmp)

    # Posts a selection request.
    def select(self, **body):
        return self.client.post("/select", data=json.dumps(body), headers=self.auth, content_type="application/json")

    # The owner may turn keys off.
    def test_no_key(self):
        from epmts_server import create_app
        app = create_app({"pack_dir": os.path.join(self.tmp, "pack"), "cache_dir": os.path.join(self.tmp, "cache"), "require_api_key": False})
        self.assertEqual(app.test_client().get("/tags").status_code, 200)

    # Keys are required except for the specification.
    def test_auth(self):
        self.assertEqual(self.client.get("/tags").status_code, 403)
        self.assertEqual(self.client.get("/specification").status_code, 200)

    # The catalogue has the documented members and logos.
    def test_tags(self):
        tags = self.client.get("/tags", headers=self.auth).get_json()["tags"]
        self.assertTrue(any("logoBase64" in tag for tag in tags))
        self.assertEqual(set(tags[0]) - {"logoBase64"}, {"id", "name", "keywords", "subcategory", "description", "descriptionFr", "typeId", "typeName"})

    # A selection returns a downloadable file; bad values get 400.
    def test_select_and_download(self):
        answer = self.select(includeTagImg=[PORN_ACTION], convert="none").get_json()
        self.assertTrue(answer["found"])
        self.assertTrue(answer["converted"])
        with self.client.get(answer["url"].replace("http://localhost", "")) as file_response:
            self.assertEqual(file_response.status_code, 200)
            self.assertEqual(file_response.mimetype, "image/png")
        self.assertEqual(self.select(format="bad").status_code, 400)
        self.assertEqual(self.select(includeTagImg=[0]).status_code, 400)

    # The protected-age media never comes with a porn request, nor without being asked for.
    def test_protected_age_rule(self):
        self.assertFalse(self.select(includeTagImg=[AGE_OTHER, PORN_ACTION]).get_json()["found"])
        # Including a liftable default (hypno) does not lift the protected-age exclusion.
        self.assertFalse(self.select(includeTagImg=[HYPNO]).get_json()["found"])
        self.assertTrue(self.select(includeTagImg=[AGE_OTHER, HYPNO]).get_json()["found"])
        seen = set()
        for _ in range(30):
            answer = self.select(includeTagImg=[SOFT_ACTION], convert="none").get_json()
            seen.add(answer.get("mediaId"))
        self.assertEqual(len(seen), 3)  # red, blue and the portrait; never the protected-age media

    # Auto conversion of a PNG for img is native; jpg is converted.
    def test_conversion_picture(self):
        answer = self.select(includeTagImg=[PORN_ACTION], convert="jpg").get_json()
        self.assertTrue(answer["url"].endswith(".jpg"))
        again = self.client.post("/media/" + answer["mediaId"], data="{}", headers=self.auth, content_type="application/json").get_json()
        self.assertEqual(again["mediaId"], answer["mediaId"])

    # PR-1: the portrait hands its reference, which draws only inside the person pack.
    def test_person_reference(self):
        answer = self.select(includeTagImg=[8], convert="none").get_json()
        self.assertEqual(answer["referenceHash"], self.portrait)
        person = self.select(includeTagImg=[PORN_ACTION], referenceHash=self.portrait.upper(), convert="none").get_json()
        self.assertTrue(person["found"])
        self.assertNotIn("referenceHash", person)
        self.assertFalse(self.select(referenceHash="0" * 64).get_json()["found"])
        self.assertEqual(self.select(referenceHash="xyz").status_code, 400)

    # A GIF asked as video is converted to VP8 IVF in the background.
    @unittest.skipUnless(media_tools.find_tool("ffmpeg"), "ffmpeg is not installed")
    def test_conversion_video(self):
        from PIL import Image
        frames = [Image.new("RGB", (32, 32), color) for color in ("red", "green", "blue")]
        path = os.path.join(self.tmp, "anim.gif")
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)
        with Pack(os.path.join(self.tmp, "pack")) as pack:
            pack.add_media(path, [SOFT_ACTION, 47])
            pack.export()
        answer = self.select(format="video", includeTagImg=[47])
        answer = answer.get_json()
        deadline = time.time() + 60
        while not answer.get("converted") and time.time() < deadline:
            self.assertNotIn("error", answer)
            time.sleep(answer["retryAfterSeconds"])
            answer = self.client.post(answer["statusUrl"].replace("http://localhost", ""), data='{"format":"video"}', headers=self.auth, content_type="application/json").get_json()
        self.assertTrue(answer["url"].endswith(".ivf"))
        with self.client.get(answer["url"].replace("http://localhost", "")) as video:
            self.assertEqual(video.data[8:12], b"VP80")


if __name__ == "__main__":
    unittest.main()
