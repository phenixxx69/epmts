"""EPMTS pack editor: browse a media pack, import media, tag them, manage person packs.

Tags come from the shared catalogue and cannot be created here (only in the EPMTS repository).
Every change is written to tags.sqlite and exported to tags.sql / tags.sql.js at once.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from collections import OrderedDict
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image, ImageOps, ImageSequence, ImageTk  # noqa: E402

from epmts import REPO_ROOT, rules  # noqa: E402
from epmts import media as media_tools  # noqa: E402
from epmts.importer import ImportRefused, create_pack_zip, import_pack, slugify  # noqa: E402
from epmts.pack import Pack, PackError  # noqa: E402
from thumbnail_grid import MediaThumbnailGrid  # noqa: E402

try:
    from tkVideoPlayer import TkinterVideo
except ImportError:  # optional: without it, videos show a still frame and open in the system player
    TkinterVideo = None

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
DEFAULT_PACK_DIR = os.path.join(REPO_ROOT, "packs", "main")
IMPORTABLE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".m4v", ".webm", ".mov", ".mkv")
MEDIA_KINDS = OrderedDict((("All media", None), ("Images", "still"), ("GIF", "gif"), ("Videos", "film")))
ALL_TAGS = "All tags"
ALL_ORIGINS = "All origins"
LOCAL_ORIGIN = "Local (added by me)"


# Reads the editor settings (last opened pack).
def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


# Saves the editor settings.
def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)


# Opens a file in the system default application.
def open_externally(path):
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606 - local user file
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class Application(tk.Tk):
    PAGE_SIZE = 80
    THUMBNAIL_SIZE = (150, 96)
    PREVIEW_SIZE = (460, 520)

    # Opens the last pack (or packs/main) and builds the window.
    def __init__(self, pack_dir=None):
        super().__init__()
        self.title("EPMTS pack editor")
        self.geometry("1380x820")
        self.minsize(1050, 650)
        self.settings = load_settings()
        self.root_pack = None
        self.pack = None
        self.person_hash = None
        self.selected_media_ids = set()
        self.visible_media_limit = self.PAGE_SIZE
        self.thumbnail_cache = OrderedDict()
        self.tag_filter_options = {ALL_TAGS: None}
        self.video_player = None
        self.gif_job_id = None
        self.preview_path = None
        self.current_import_dir = None
        self.create_menu()
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_quit)
        self.after(50, self.open_initial_pack, pack_dir)

    # Opens the pack given on the command line, the last one, or offers to create packs/main.
    def open_initial_pack(self, pack_dir):
        candidate = pack_dir or self.settings.get("last_pack") or DEFAULT_PACK_DIR
        if os.path.isfile(os.path.join(candidate, "tags.sqlite")):
            self.load_pack(candidate)
            return
        if candidate == DEFAULT_PACK_DIR and messagebox.askyesno(
            "Welcome", "No pack is open yet.\n\nCreate an empty pack in packs/main?\n(Choose No to open an existing pack folder.)"
        ):
            self.create_pack_at(DEFAULT_PACK_DIR)
        else:
            self.open_pack_dialog()

    # -------------------------------------------------------------------------
    # Window
    # -------------------------------------------------------------------------
    # Creates the application menus.
    def create_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open pack folder…", command=self.open_pack_dialog)
        file_menu.add_command(label="New empty pack…", command=self.new_pack_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Import a downloaded pack (.zip)…", command=self.import_zip_dialog)
        file_menu.add_command(label="Import a pack folder…", command=self.import_folder_dialog)
        file_menu.add_command(label="Update the tag catalogue", command=self.update_catalogue)
        file_menu.add_command(label="Check the pack", command=self.validate_pack)
        file_menu.add_separator()
        file_menu.add_command(label="Create a pack from my local media…", command=lambda: self.create_pack_dialog(True))
        file_menu.add_command(label="Create a pack from all media…", command=lambda: self.create_pack_dialog(False))
        file_menu.add_command(label="Show the pack folder", command=self.show_pack_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.on_quit)
        menubar.add_cascade(label="File", menu=file_menu)
        person_menu = tk.Menu(menubar, tearoff=0)
        person_menu.add_command(label="New person pack from a portrait…", command=self.new_person_dialog)
        menubar.add_cascade(label="Person", menu=person_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Getting started", command=lambda: open_externally(os.path.join(REPO_ROOT, "docs", "en", "getting-started.md")))
        help_menu.add_command(label="How to tag", command=lambda: open_externally(os.path.join(REPO_ROOT, "docs", "en", "tagging.md")))
        help_menu.add_command(label="Tag list", command=lambda: open_externally(os.path.join(REPO_ROOT, "catalogue", "TAGS.md")))
        help_menu.add_command(label="The standard", command=lambda: open_externally(os.path.join(REPO_ROOT, "standard", "EPMTS-HTTP.md")))
        menubar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menubar)

    # Creates the browse tab, the import tab and the preview pane.
    def create_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.project_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.project_frame, text="Pack")
        self.import_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.import_frame, text="Import")

        filter_frame = ttk.Frame(self.project_frame, padding=(8, 8, 8, 4))
        filter_frame.pack(fill="x")
        ttk.Label(filter_frame, text="Tag:").pack(side="left")
        self.tag_filter_var = tk.StringVar(value=ALL_TAGS)
        self.tag_filter_combo = ttk.Combobox(filter_frame, textvariable=self.tag_filter_var, state="readonly", width=40)
        self.tag_filter_combo.pack(side="left", padx=(4, 12))
        self.tag_filter_combo.bind("<<ComboboxSelected>>", self.on_filter_changed)
        ttk.Label(filter_frame, text="Type:").pack(side="left")
        self.kind_filter_var = tk.StringVar(value="All media")
        kind_combo = ttk.Combobox(filter_frame, textvariable=self.kind_filter_var, values=tuple(MEDIA_KINDS), state="readonly", width=14)
        kind_combo.pack(side="left", padx=(4, 12))
        kind_combo.bind("<<ComboboxSelected>>", self.on_filter_changed)
        ttk.Label(filter_frame, text="Origin:").pack(side="left")
        self.origin_filter_var = tk.StringVar(value=ALL_ORIGINS)
        self.origin_filter_combo = ttk.Combobox(filter_frame, textvariable=self.origin_filter_var, state="readonly", width=22)
        self.origin_filter_combo.pack(side="left", padx=(4, 12))
        self.origin_filter_combo.bind("<<ComboboxSelected>>", self.on_filter_changed)
        ttk.Button(filter_frame, text="Reset", command=self.reset_filters).pack(side="left")
        self.status_label = ttk.Label(filter_frame, text="")
        self.status_label.pack(side="right")

        action_frame = ttk.Frame(self.project_frame, padding=(8, 4, 8, 8))
        action_frame.pack(fill="x")
        ttk.Button(action_frame, text="Edit tags…", command=self.on_tags_click).pack(side="left", padx=(0, 3))
        ttk.Button(action_frame, text="Delete media", command=self.on_delete_media).pack(side="left", padx=3)
        ttk.Button(action_frame, text="Open in system viewer", command=self.on_open_external).pack(side="left", padx=3)
        self.location_label = ttk.Label(action_frame, text="")
        self.location_label.pack(side="left", padx=16)

        main = ttk.Frame(self.project_frame)
        main.pack(fill="both", expand=True)
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        self.grid_view = MediaThumbnailGrid(left, self.on_person_click, self.on_media_click, self.leave_person)
        self.grid_view.pack(fill="both", expand=True)
        self.load_more_button = ttk.Button(left, text="Show more", command=self.load_more)
        right = tk.Frame(main, width=480, background="#111111")
        right.pack(side="right", fill="both", padx=(6, 8), pady=(0, 8))
        right.pack_propagate(False)
        self.preview_label = tk.Label(right, text="Select a thumbnail", background="#111111", foreground="#d7d7d7")
        self.preview_label.pack(fill="both", expand=True)

        top = ttk.Frame(self.import_frame)
        top.pack(fill="x")
        ttk.Button(top, text="Choose a folder…", command=self.select_import_directory).pack(side="left", padx=5, pady=5)
        self.import_target_label = ttk.Label(top, text="")
        self.import_target_label.pack(side="left", padx=18)
        ttk.Label(
            self.import_frame,
            text="Select one or several files (Ctrl/Shift click) and import them. Metadata is removed and files are renamed "
                 "by their SHA-256: original names never enter the pack. A single imported file opens the tag window.",
            wraplength=900, foreground="#555555",
        ).pack(fill="x", padx=8)
        body = ttk.Frame(self.import_frame)
        body.pack(fill="both", expand=True)
        list_frame = ttk.Frame(body)
        list_frame.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical")
        self.import_listbox = tk.Listbox(list_frame, yscrollcommand=scroll.set, selectmode=tk.EXTENDED)
        scroll.config(command=self.import_listbox.yview)
        scroll.pack(side="right", fill="y")
        self.import_listbox.pack(side="left", fill="both", expand=True)
        self.import_listbox.bind("<<ListboxSelect>>", self.on_select_import)
        self.import_listbox.bind("<Double-Button-1>", self.on_import_double_click)
        ttk.Button(list_frame, text="Import selected files", command=self.on_import_files).pack(side="bottom", fill="x", padx=5, pady=5)
        self.import_preview_label = ttk.Label(body, text="(preview)")
        self.import_preview_label.pack(side="left", fill="both", expand=True)

    # -------------------------------------------------------------------------
    # Packs
    # -------------------------------------------------------------------------
    # Opens a pack as the root pack (upgrading older layouts), keeping the current one on failure.
    def load_pack(self, directory):
        try:
            pack = Pack(directory, upgrade=True)
        except (PackError, OSError) as error:
            messagebox.showerror("Cannot open the pack", str(error))
            return False
        for opened in {self.pack, self.root_pack} - {None}:
            opened.close()
        self.root_pack = self.pack = pack
        self.person_hash = None
        self.settings["last_pack"] = pack.directory
        save_settings(self.settings)
        self.after_pack_change()
        return True

    # Creates an empty pack in a folder and opens it.
    def create_pack_at(self, directory):
        try:
            Pack.create(directory).close()
        except (PackError, OSError) as error:
            messagebox.showerror("Cannot create the pack", str(error))
            return
        self.load_pack(directory)

    # Asks for a pack folder and opens it.
    def open_pack_dialog(self):
        directory = filedialog.askdirectory(title="Choose a pack folder (it holds tags.sqlite)", initialdir=os.path.join(REPO_ROOT, "packs"))
        if directory:
            self.load_pack(directory)

    # Asks for an empty folder and creates a pack in it.
    def new_pack_dialog(self):
        directory = filedialog.askdirectory(title="Choose an EMPTY folder for the new pack", initialdir=os.path.join(REPO_ROOT, "packs"))
        if directory:
            self.create_pack_at(directory)

    # Enters a person pack.
    def on_person_click(self, portrait_hash, event=None):
        directory = self.root_pack.person_directory(portrait_hash)
        if directory is None:
            return
        try:
            person = Pack(directory, upgrade=True)
        except PackError as error:
            messagebox.showerror("Cannot open the person pack", str(error))
            return
        if self.pack is not self.root_pack:
            self.pack.close()
        self.pack = person
        self.person_hash = portrait_hash
        self.after_pack_change()

    # Goes back from a person pack to the main pack.
    def leave_person(self):
        if self.pack is not self.root_pack:
            self.pack.close()
        self.pack = self.root_pack
        self.person_hash = None
        self.after_pack_change()

    # Resets the view after the active pack changed.
    def after_pack_change(self):
        self.selected_media_ids.clear()
        self.visible_media_limit = self.PAGE_SIZE
        self.thumbnail_cache = OrderedDict()
        where = "Main pack: {}".format(self.root_pack.directory)
        if self.person_hash:
            where = "Person pack {}… (inside the main pack)".format(self.person_hash[:12])
        self.location_label.configure(text=where)
        self.import_target_label.configure(text="Import into: " + ("person pack " + self.person_hash[:12] + "…" if self.person_hash else "main pack"))
        self.title("EPMTS pack editor — " + os.path.basename(self.root_pack.directory))
        self.refresh_filter_options()
        self.refresh_grid()

    # Writes tags.sql and tags.sql.js of the active pack (and the main pack for portraits).
    def export_active(self):
        self.pack.export()
        if self.pack is not self.root_pack:
            self.root_pack.export()

    # Asks for a pack zip and imports it into the open pack.
    def import_zip_dialog(self):
        path = filedialog.askopenfilename(title="Choose the downloaded pack (.zip)", filetypes=[("Zip archive", "*.zip"), ("All files", "*")])
        if path:
            self.start_import(path)

    # Asks for a pack folder and imports it into the open pack.
    def import_folder_dialog(self):
        path = filedialog.askdirectory(title="Choose the pack folder to import (it holds tags.sqlite)")
        if path:
            self.start_import(path)

    # Runs the checked import in the background (hashing every file can take a while).
    def start_import(self, source):
        if self.root_pack is None:
            messagebox.showwarning("Import", "Open or create the pack to import into first (File menu).")
            return
        self.leave_person()
        directory = self.root_pack.directory
        self.root_pack.close()
        self.root_pack = self.pack = None
        outcome = {}
        worker = threading.Thread(target=self.run_import, args=(directory, source, outcome), daemon=True)
        busy = tk.Toplevel(self)
        busy.title("Import")
        busy.transient(self)
        busy.protocol("WM_DELETE_WINDOW", lambda: None)  # the import cannot be interrupted halfway
        ttk.Label(busy, text="Checking and importing the pack…\nEvery file is verified against its SHA-256.", padding=24).pack()
        busy.grab_set()
        worker.start()
        self.after(300, self.finish_import, worker, directory, outcome, busy)

    # Imports in the worker thread and stores the result.
    @staticmethod
    def run_import(directory, source, outcome):
        try:
            outcome["report"] = import_pack(directory, source)
        except ImportRefused as error:
            outcome["refused"] = error
        except (PackError, OSError, ValueError) as error:
            outcome["error"] = error

    # Waits for the worker, then reopens the pack and reports.
    def finish_import(self, worker, directory, outcome, busy):
        if worker.is_alive():
            self.after(300, self.finish_import, worker, directory, outcome, busy)
            return
        busy.destroy()
        self.load_pack(directory)
        if "refused" in outcome:
            error = outcome["refused"]
            messagebox.showerror("Import refused", str(error) + ("\n\n" + "\n".join(error.problems[:25]) if error.problems else ""))
        elif "error" in outcome:
            messagebox.showerror("Import failed", str(outcome["error"]))
        else:
            report = outcome["report"]
            message = "{} media checked.\n{} added, {} already present (tags united), {} person pack(s).".format(
                report["checked"], report["added"], report["updated"], report["persons"])
            if report["skipped"]:
                message += "\n\nSkipped:\n" + "\n".join("{}…: {}".format(h[:12], why) for h, why in report["skipped"][:20])
            messagebox.showinfo("Import", message)

    # Replaces the tag catalogue of every pack with the repository one.
    def update_catalogue(self):
        try:
            for portrait_hash in [None] + self.root_pack.person_hashes():
                if portrait_hash is None:
                    target = self.root_pack
                else:
                    target = Pack(self.root_pack.person_directory(portrait_hash), upgrade=True)
                target.sync_catalogue()
                target.export()
                if target is not self.root_pack:
                    target.close()
        except (PackError, OSError) as error:
            messagebox.showerror("Update failed", str(error))
            return
        messagebox.showinfo("Catalogue", "The tag catalogue of the pack is up to date.")
        self.leave_person()

    # Asks the pack details, builds the zip in the background, then reports.
    def create_pack_dialog(self, local_only):
        if self.root_pack is None:
            return
        dialog = PackDetailsWindow(self, local_only)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        manifest = dialog.result
        zip_path = filedialog.asksaveasfilename(
            title="Save the pack as", defaultextension=".zip", filetypes=[("Zip archive", "*.zip")],
            initialfile=slugify("{}-{}".format(manifest["name"], manifest["version"])) + ".zip",
        )
        if not zip_path:
            return
        self.leave_person()
        directory = self.root_pack.directory
        self.root_pack.close()
        self.root_pack = self.pack = None
        outcome = {}
        busy = tk.Toplevel(self)
        busy.title("Creating the pack")
        busy.transient(self)
        busy.protocol("WM_DELETE_WINDOW", lambda: None)
        ttk.Label(busy, text="Creating the pack…", padding=24).pack()
        busy.grab_set()
        worker = threading.Thread(target=self.run_create_pack, args=(directory, manifest, local_only, zip_path, outcome), daemon=True)
        worker.start()
        self.after(300, self.finish_create_pack, worker, directory, outcome, busy, zip_path)

    # Builds the pack zip in the worker thread.
    @staticmethod
    def run_create_pack(directory, manifest, local_only, zip_path, outcome):
        try:
            outcome["count"] = create_pack_zip(directory, manifest, local_only, zip_path)
        except (PackError, OSError, ValueError) as error:
            outcome["error"] = error

    # Reopens the pack and reports the created zip.
    def finish_create_pack(self, worker, directory, outcome, busy, zip_path):
        if worker.is_alive():
            self.after(300, self.finish_create_pack, worker, directory, outcome, busy, zip_path)
            return
        busy.destroy()
        self.load_pack(directory)
        if "error" in outcome:
            messagebox.showerror("Pack not created", str(outcome["error"]))
            return
        messagebox.showinfo("Pack created", "{} media saved in\n{}\n\nYou can share this zip: it holds pack.json (name, author, version, date, project link). "
                            "Your local media in it are now marked as coming from this pack.".format(outcome["count"], zip_path))

    # Shows the result of the pack validation.
    def validate_pack(self):
        problems = self.root_pack.validate(deep=True)
        if problems:
            messagebox.showwarning("Check", "{} problem(s):\n\n".format(len(problems)) + "\n".join(problems[:30]))
        else:
            messagebox.showinfo("Check", "The pack is valid.")

    # Opens the pack folder in the file manager.
    def show_pack_folder(self):
        open_externally(self.root_pack.directory)

    # Creates a person pack from a portrait picture.
    def new_person_dialog(self):
        if self.root_pack is None:
            return
        path = filedialog.askopenfilename(title="Choose the PORTRAIT of the person (jpeg, png or webp)")
        if not path:
            return
        window = TagSelectionWindow(self, None, title="Tags of the portrait (gender, age group, kink status…)")
        self.wait_window(window)
        if window.result is None:
            return
        try:
            portrait_hash = self.root_pack.create_person(path, window.result)
            self.root_pack.export()
        except (PackError, rules.RuleViolation, ValueError, OSError) as error:
            messagebox.showerror("Cannot create the person pack", str(error))
            return
        self.leave_person()
        self.on_person_click(portrait_hash)
        messagebox.showinfo("Person pack", "Person pack created. Import this person's media now: they go into the person pack.")
        self.notebook.select(self.import_frame)

    # -------------------------------------------------------------------------
    # Grid
    # -------------------------------------------------------------------------
    # Reloads the tag filter from the active pack.
    def refresh_filter_options(self):
        options = OrderedDict(((ALL_TAGS, None),))
        for tag in self.pack.tags():
            options["{} · {} (#{})".format(tag["type_name"] or "-", tag["name"], tag["id"])] = int(tag["id"])
        self.tag_filter_options = options
        self.tag_filter_combo.configure(values=tuple(options))
        if self.tag_filter_var.get() not in options:
            self.tag_filter_var.set(ALL_TAGS)
        origins = [row[0] for row in self.pack.conn.execute("SELECT DISTINCT origin FROM media WHERE origin IS NOT NULL ORDER BY origin COLLATE NOCASE")]
        values = (ALL_ORIGINS, LOCAL_ORIGIN) + tuple(origins)
        self.origin_filter_combo.configure(values=values)
        if self.origin_filter_var.get() not in values:
            self.origin_filter_var.set(ALL_ORIGINS)

    # Returns the filtered media rows of the active pack and their total.
    def query_media(self):
        where, params = [], []
        tag_id = self.tag_filter_options.get(self.tag_filter_var.get())
        if tag_id:
            where.append("EXISTS (SELECT 1 FROM media_has_tag_media f WHERE f.media_id = m.id AND f.tag_media_id = ?)")
            params.append(tag_id)
        origin = self.origin_filter_var.get()
        if origin == LOCAL_ORIGIN:
            where.append("m.origin IS NULL")
        elif origin != ALL_ORIGINS:
            where.append("m.origin = ?")
            params.append(origin)
        kind = MEDIA_KINDS.get(self.kind_filter_var.get())
        if kind:
            types = rules.MEDIA_FAMILIES[kind]
            where.append("m.type IN ({})".format(", ".join("?" for _ in types)))
            params.extend(types)
        clause = " WHERE " + " AND ".join(where) if where else ""
        total = self.pack.conn.execute("SELECT COUNT(*) FROM media m" + clause, params).fetchone()[0]
        rows = self.pack.conn.execute(
            "SELECT m.id, m.hash, m.type, m.origin, GROUP_CONCAT(tm.name, ', ') AS tags FROM media m "
            "LEFT JOIN media_has_tag_media mm ON mm.media_id = m.id LEFT JOIN tag_media tm ON tm.id = mm.tag_media_id"
            + clause + " GROUP BY m.id ORDER BY m.id DESC LIMIT ?",
            params + [self.visible_media_limit],
        ).fetchall()
        return rows, total

    # Lists the person packs of the main pack with their media count.
    def list_persons(self):
        persons = []
        for portrait_hash in self.root_pack.person_hashes():
            try:
                with Pack(self.root_pack.person_directory(portrait_hash), upgrade=True) as person:
                    count = person.conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
            except PackError:
                continue
            persons.append({"hash": portrait_hash, "media_count": count})
        return persons

    # Redraws the grid from the active filters.
    def refresh_grid(self, preserve_scroll=False):
        position = self.grid_view.canvas.yview()[0] if preserve_scroll else 0.0
        rows, total = self.query_media()
        persons = [] if self.person_hash else self.list_persons()
        self.selected_media_ids.intersection_update({int(row["id"]) for row in rows})
        self.grid_view.render(persons, rows, self.load_thumbnail, self.selected_media_ids, show_parent=bool(self.person_hash), person_thumbnail_loader=self.load_person_thumbnail)
        if preserve_scroll:
            self.grid_view.update_idletasks()
            self.grid_view.canvas.yview_moveto(position)
        self.status_label.configure(text="{} shown of {}".format(len(rows), total))
        if len(rows) < total:
            self.load_more_button.pack(fill="x", padx=5, pady=5)
        else:
            self.load_more_button.pack_forget()

    # Resets paging after a filter change.
    def on_filter_changed(self, event=None):
        self.visible_media_limit = self.PAGE_SIZE
        self.selected_media_ids.clear()
        self.refresh_grid()

    # Clears the filters.
    def reset_filters(self):
        self.tag_filter_var.set(ALL_TAGS)
        self.kind_filter_var.set("All media")
        self.origin_filter_var.set(ALL_ORIGINS)
        self.on_filter_changed()

    # Shows the next page of thumbnails.
    def load_more(self):
        self.visible_media_limit += self.PAGE_SIZE
        self.refresh_grid(preserve_scroll=True)

    # Selects a thumbnail (Ctrl+click adds to the selection) and previews it.
    def on_media_click(self, media_id, event=None):
        additive = bool(event and (event.state & 0x0004))
        if not additive:
            self.selected_media_ids.clear()
        if additive and media_id in self.selected_media_ids:
            self.selected_media_ids.remove(media_id)
        else:
            self.selected_media_ids.add(media_id)
        row = self.pack.get_media(media_id)
        if row is not None:
            self.show_preview(self.pack.media_file(row["hash"]), row["type"], self.preview_label)
        self.refresh_grid(preserve_scroll=True)

    # Returns a cached thumbnail of a media row.
    def load_thumbnail(self, media):
        key = (self.pack.directory, media["hash"])
        if key not in self.thumbnail_cache:
            self.thumbnail_cache[key] = self.make_thumbnail(self.pack.media_file(media["hash"]), media["type"])
            while len(self.thumbnail_cache) > 400:
                self.thumbnail_cache.popitem(last=False)
        return self.thumbnail_cache[key]

    # Returns the portrait thumbnail of a person pack.
    def load_person_thumbnail(self, person):
        key = ("person", person["hash"])
        if key not in self.thumbnail_cache:
            row = self.root_pack.get_media_by_hash(person["hash"])
            self.thumbnail_cache[key] = self.make_thumbnail(self.root_pack.media_file(person["hash"]), row["type"] if row else "image/jpeg")
        return self.thumbnail_cache[key]

    # Builds a letterboxed thumbnail, using ffmpeg for video frames.
    def make_thumbnail(self, path, media_type):
        if not path:
            return None
        try:
            image = media_tools.first_frame(path, media_type)
        except Exception:
            image = None
        if image is None:
            return None
        fitted = ImageOps.contain(image, self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        background = Image.new("RGB", self.THUMBNAIL_SIZE, "#151515")
        background.paste(fitted, ((self.THUMBNAIL_SIZE[0] - fitted.width) // 2, (self.THUMBNAIL_SIZE[1] - fitted.height) // 2))
        return ImageTk.PhotoImage(background)

    # -------------------------------------------------------------------------
    # Preview
    # -------------------------------------------------------------------------
    # Stops the GIF animation and the video player before a new preview.
    def clear_preview(self, label):
        label.config(image="", text="")
        label.image = None
        if self.gif_job_id is not None:
            self.after_cancel(self.gif_job_id)
            self.gif_job_id = None
        if self.video_player is not None:
            self.video_player.destroy()
            self.video_player = None

    # Shows a picture, an animated GIF or a video (player or still frame).
    def show_preview(self, path, media_type, label):
        self.clear_preview(label)
        self.preview_path = (path, media_type)
        if not path or not os.path.isfile(path):
            label.config(text="Media file not found.")
            return
        family = media_tools.family(media_type)
        try:
            if family == "gif":
                with Image.open(path) as image:
                    frames = [(ImageTk.PhotoImage(ImageOps.contain(frame.convert("RGBA"), self.PREVIEW_SIZE)), max(20, frame.info.get("duration", 100)))
                              for frame in ImageSequence.Iterator(image)]
                self.animate_gif(label, frames, 0)
            elif family == "still":
                with Image.open(path) as image:
                    photo = ImageTk.PhotoImage(ImageOps.contain(image.convert("RGBA"), self.PREVIEW_SIZE, Image.Resampling.LANCZOS))
                label.config(image=photo)
                label.image = photo
            elif family == "film" and TkinterVideo is not None:
                self.video_player = TkinterVideo(label, scaled=True, keep_aspect=True)
                self.video_player.pack(fill="both", expand=True)
                self.video_player.load(path)
                self.video_player.play()
            elif family == "film":
                frame = media_tools.first_frame(path, media_type)
                if frame is None:
                    label.config(text="Video (install ffmpeg to see a frame).\nUse 'Open in system viewer' to play it.")
                    return
                photo = ImageTk.PhotoImage(ImageOps.contain(frame, self.PREVIEW_SIZE, Image.Resampling.LANCZOS))
                label.config(image=photo, text="▶ use 'Open in system viewer' to play", compound="bottom")
                label.image = photo
            else:
                label.config(text="Unsupported media type.")
        except Exception:
            label.config(text="Cannot display this media.")

    # Shows the next GIF frame after the previous one's delay.
    def animate_gif(self, label, frames, index):
        photo, delay = frames[index]
        label.config(image=photo)
        label.image = photo
        if len(frames) > 1:
            self.gif_job_id = self.after(delay, self.animate_gif, label, frames, (index + 1) % len(frames))

    # Opens the previewed media in the system viewer (a temporary copy gets its extension back).
    def on_open_external(self):
        if not self.preview_path or not self.preview_path[0]:
            messagebox.showwarning("Open", "Select a media first.")
            return
        path, media_type = self.preview_path
        extension = media_tools.EXTENSIONS.get(media_type)
        if extension and not path.lower().endswith("." + extension):
            copy = os.path.join(tempfile.gettempdir(), "epmts-preview." + extension)
            shutil.copyfile(path, copy)
            path = copy
        open_externally(path)

    # -------------------------------------------------------------------------
    # Editing
    # -------------------------------------------------------------------------
    # Opens the tag window for the single selected media.
    def on_tags_click(self):
        if len(self.selected_media_ids) != 1:
            messagebox.showwarning("Tags", "Select exactly one media (click on a thumbnail).")
            return
        media_id = next(iter(self.selected_media_ids))
        self.edit_tags(media_id)

    # Edits and saves the tags of one media of the active pack.
    def edit_tags(self, media_id):
        window = TagSelectionWindow(self, self.pack.media_tags(media_id), title="Tags of media #{}".format(media_id))
        self.wait_window(window)
        if window.result is None:
            return
        try:
            self.pack.set_tags(media_id, window.result)
            self.sync_portrait_tags(self.pack.get_media(media_id)["hash"], window.result)
            self.export_active()
        except rules.RuleViolation as error:
            messagebox.showerror("Tags refused", str(error))
        self.refresh_grid(preserve_scroll=True)

    # Copies the tags of a portrait to its other row: it exists in the main pack and in its person pack.
    def sync_portrait_tags(self, media_hash, tag_ids):
        if self.person_hash == media_hash:
            self.root_pack.set_tags(self.root_pack.get_media_by_hash(media_hash)["id"], tag_ids)
        elif self.pack is self.root_pack and self.root_pack.person_directory(media_hash):
            with Pack(self.root_pack.person_directory(media_hash)) as person:
                person.set_tags(person.get_media_by_hash(media_hash)["id"], tag_ids)
                person.export()

    # Deletes the selected media after one confirmation.
    def on_delete_media(self):
        if not self.selected_media_ids:
            messagebox.showwarning("Delete", "Select the media to delete first.")
            return
        if not messagebox.askyesno("Delete", "Delete {} media from the pack, files included?".format(len(self.selected_media_ids))):
            return
        try:
            for media_id in tuple(self.selected_media_ids):
                self.pack.delete_media(media_id)
        except PackError as error:
            messagebox.showerror("Delete", str(error))
        self.export_active()
        self.selected_media_ids.clear()
        self.clear_preview(self.preview_label)
        self.refresh_grid()

    # -------------------------------------------------------------------------
    # Import
    # -------------------------------------------------------------------------
    # Chooses the folder to import from.
    def select_import_directory(self):
        directory = filedialog.askdirectory(title="Folder holding the media to import")
        if directory:
            self.list_import_directory(directory)

    # Lists sub-folders and importable files of a folder.
    def list_import_directory(self, directory):
        self.current_import_dir = directory
        self.import_listbox.delete(0, tk.END)
        if os.path.dirname(directory) != directory:
            self.import_listbox.insert(tk.END, "[..]")
        entries = sorted(os.listdir(directory), key=str.casefold)
        for name in entries:
            if os.path.isdir(os.path.join(directory, name)):
                self.import_listbox.insert(tk.END, "[folder] " + name)
        for name in entries:
            if os.path.isfile(os.path.join(directory, name)) and name.lower().endswith(IMPORTABLE_EXTENSIONS):
                self.import_listbox.insert(tk.END, name)

    # Previews the first selected file.
    def on_select_import(self, event=None):
        selection = self.import_listbox.curselection()
        if not selection or self.current_import_dir is None:
            return
        item = self.import_listbox.get(selection[0])
        if item == "[..]" or item.startswith("[folder] "):
            return
        path = os.path.join(self.current_import_dir, item)
        self.show_preview(path, media_tools.sniff_type(path), self.import_preview_label)

    # Enters a folder on double click.
    def on_import_double_click(self, event=None):
        selection = self.import_listbox.curselection()
        if not selection:
            return
        item = self.import_listbox.get(selection[0])
        if item == "[..]":
            self.list_import_directory(os.path.dirname(self.current_import_dir))
        elif item.startswith("[folder] "):
            self.list_import_directory(os.path.join(self.current_import_dir, item[len("[folder] "):]))

    # Imports the selected files into the active pack.
    def on_import_files(self):
        selection = [self.import_listbox.get(i) for i in self.import_listbox.curselection()]
        files = [os.path.join(self.current_import_dir, item) for item in selection if item != "[..]" and not item.startswith("[folder] ")]
        if not files:
            messagebox.showwarning("Import", "Select one or more files in the list.")
            return
        imported, failures = [], []
        self.config(cursor="watch")
        self.update_idletasks()
        for path in files:
            try:
                media_id, created = self.pack.add_media(path)
                if created:
                    imported.append(media_id)
            except (OSError, ValueError, RuntimeError, rules.RuleViolation) as error:
                failures.append("{}: {}".format(os.path.basename(path), error))
        self.config(cursor="")
        self.export_active()
        self.refresh_grid()
        message = "{} file(s) imported, {} already in the pack.".format(len(imported), len(files) - len(imported) - len(failures))
        if failures:
            message += "\n\nFailed:\n" + "\n".join(failures[:15])
        if len(imported) == 1 and not failures:
            self.notebook.select(self.project_frame)
            self.selected_media_ids = {imported[0]}
            self.edit_tags(imported[0])
        else:
            messagebox.showinfo("Import", message + "\n\nNew media have no tag yet: select each one and use 'Edit tags…'.")

    # Closes the packs and the window.
    def on_quit(self):
        for opened in {self.pack, self.root_pack} - {None}:
            opened.close()
        self.destroy()


class TagSelectionWindow(tk.Toplevel):
    """Modal tag picker grouped by type; result is the chosen tag id set, or None when cancelled."""

    # Builds the window from the active pack catalogue.
    def __init__(self, parent, selected, title):
        super().__init__(parent)
        self.title(title)
        self.geometry("980x700")
        self.transient(parent)
        self.result = None
        self.selected = set(selected or ())
        self.porn_actions = parent.pack.porn_actions()
        self.groups = OrderedDict()
        for tag in parent.pack.tags():
            self.groups.setdefault((tag["type_tag"], tag["type_name"] or "-"), []).append(tag)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", self.on_filter_change)
        entry = ttk.Entry(top, textvariable=self.filter_var)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.focus_set()
        self.warning_label = tk.Label(self, text="", foreground="#b00020", anchor="w", justify="left")
        self.warning_label.pack(fill="x", padx=8)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=8)
        self.canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self.on_inner_configure)

        buttons = ttk.Frame(self, padding=8)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save", command=self.on_save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=4)
        ttk.Label(buttons, text="🔞 = porn action tag.").pack(side="right")
        self.build_tag_list("")
        self.update_warning()
        self.grab_set()

    # Keeps the scroll region in line with the content.
    def on_inner_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # Builds the grouped tag buttons matching the filter text.
    def build_tag_list(self, filter_text):
        for widget in self.inner.winfo_children():
            widget.destroy()
        filter_text = filter_text.lower()
        for (type_id, type_name), tags in self.groups.items():
            shown = [tag for tag in tags if not filter_text or filter_text in (tag["name"] or "").lower()
                     or filter_text in (tag["description"] or "").lower() or filter_text in (tag["description_fr"] or "").lower()]
            if not shown:
                continue
            ttk.Label(self.inner, text="{} — {}".format(type_id, type_name), font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(10, 2))
            row_frame = None
            for index, tag in enumerate(shown):
                if index % 6 == 0:
                    row_frame = ttk.Frame(self.inner)
                    row_frame.pack(fill="x", padx=16)
                label = "{}{} #{}".format("🔞 " if tag["id"] in self.porn_actions else "", tag["name"], tag["id"])
                button = tk.Button(row_frame, text=label, padx=5, pady=2, relief="raised")
                button.configure(command=lambda t=tag["id"], b=button: self.on_toggle(t, b))
                self.paint(button, tag["id"] in self.selected)
                button.pack(side="left", padx=4, pady=3)

    # Colours a tag button by its state.
    @staticmethod
    def paint(button, selected):
        button.configure(background="lightgreen" if selected else "SystemButtonFace" if sys.platform.startswith("win") else "#d9d9d9",
                         relief="sunken" if selected else "raised")

    # Rebuilds the list when the filter changes.
    def on_filter_change(self, *args):
        self.build_tag_list(self.filter_var.get().strip())

    # Toggles one tag.
    def on_toggle(self, tag_id, button):
        if tag_id in self.selected:
            self.selected.remove(tag_id)
        else:
            self.selected.add(tag_id)
        self.paint(button, tag_id in self.selected)
        self.update_warning()

    # Warns at once when the selection breaks the protected-age rule.
    def update_warning(self):
        try:
            rules.check_media_tags(self.selected, self.porn_actions)
            self.warning_label.configure(text="")
        except rules.RuleViolation as error:
            self.warning_label.configure(text="⚠ " + str(error))

    # Returns the selection when it respects the rules.
    def on_save(self):
        try:
            rules.check_media_tags(self.selected, self.porn_actions)
        except rules.RuleViolation as error:
            messagebox.showerror("Tags refused", str(error), parent=self)
            return
        self.result = set(self.selected)
        self.destroy()


# Starts the editor, optionally on a pack folder given as first argument.
def main():
    pack_dir = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else None
    Application(pack_dir).mainloop()


if __name__ == "__main__":
    main()


class PackDetailsWindow(tk.Toplevel):
    """Asks the name, author, version, date and description of a new pack."""

    # Builds the form.
    def __init__(self, parent, local_only):
        super().__init__(parent)
        self.title("New pack from " + ("my local media" if local_only else "all media"))
        self.transient(parent)
        self.result = None
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, wraplength=420, text=(
            "The pack will hold the media you added yourself (not those imported from other packs)."
            if local_only else "The pack will hold every media of the open pack, imported ones included."
        )).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.values = {}
        defaults = {"name": "", "author": "", "version": "1.0", "date": datetime.date.today().isoformat()}
        for row, (key, label) in enumerate((("name", "Pack name"), ("author", "Author"), ("version", "Version"), ("date", "Date (YYYY-MM-DD)")), start=1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=3)
            self.values[key] = tk.StringVar(value=defaults[key])
            ttk.Entry(frame, textvariable=self.values[key], width=40).grid(row=row, column=1, sticky="we", pady=3)
        ttk.Label(frame, text="Description").grid(row=5, column=0, sticky="nw", pady=3)
        self.description = tk.Text(frame, width=40, height=4)
        self.description.grid(row=5, column=1, sticky="we", pady=3)
        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Create", command=self.on_create).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left")
        self.grab_set()

    # Checks the values and closes with the manifest.
    def on_create(self):
        from epmts.pack import check_manifest
        manifest = {key: var.get() for key, var in self.values.items()}
        manifest["description"] = self.description.get("1.0", "end").strip()
        try:
            self.result = check_manifest(manifest)
        except PackError as error:
            messagebox.showerror("Pack details", str(error), parent=self)
            return
        self.destroy()
