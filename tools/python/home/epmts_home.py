"""EPMTS home window: the one place a beginner needs.

Shows how many media the pack holds and where they come from, and offers four buttons:
import a pack (.zip), open the media manager, start/stop the server, preview the media.
"""

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from epmts import REPO_ROOT  # noqa: E402
from epmts.importer import ImportRefused, import_pack  # noqa: E402
from epmts.pack import Pack, PackError  # noqa: E402

PACK_DIR = os.path.join(REPO_ROOT, "packs", "main")
EDITOR_SCRIPT = os.path.join(REPO_ROOT, "tools", "python", "editor", "epmts_editor.py")
SERVER_SCRIPT = os.path.join(REPO_ROOT, "tools", "python", "server", "epmts_server.py")
SERVER_CONFIG = os.path.join(REPO_ROOT, "tools", "python", "server", "config.json")
SERVER_LOG = os.path.join(REPO_ROOT, "cache", "server.log")
PREVIEW_PAGE = os.path.join(REPO_ROOT, "web", "preview.html")
GUIDE = os.path.join(REPO_ROOT, "docs", "en", "getting-started.md")
NO_CONSOLE = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW


# Opens a file or folder with the system default application.
def open_externally(path):
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606 - local repository file
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class HomeWindow(tk.Tk):
    """The summary window."""

    # Builds the window and shows the pack status.
    def __init__(self):
        super().__init__()
        self.title("EPMTS — Easy Porn Media Tag System")
        self.geometry("720x600")
        self.minsize(620, 520)
        self.server = None
        self.server_info = None
        self.editor = None
        self.status_signature = None
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<FocusIn>", self.on_focus)
        self.refresh_status()

    # Creates the status area and the big buttons.
    def create_widgets(self):
        style = ttk.Style(self)
        style.configure("Big.TButton", font=("TkDefaultFont", 12), padding=10)
        style.configure("Count.TLabel", font=("TkDefaultFont", 20, "bold"))
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Your media", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.count_label = ttk.Label(frame, text="", style="Count.TLabel")
        self.count_label.pack(anchor="w", pady=(4, 0))
        self.detail_label = ttk.Label(frame, text="", wraplength=660, justify="left", foreground="#555555")
        self.detail_label.pack(anchor="w", pady=(2, 14))

        ttk.Button(frame, text="📦  Import a media pack (.zip)…", style="Big.TButton", command=self.on_import).pack(fill="x", pady=4)
        ttk.Button(frame, text="🖼  Open the media manager (browse, tag, create packs)", style="Big.TButton", command=self.on_editor).pack(fill="x", pady=4)
        self.server_button = ttk.Button(frame, text="▶  Start the server (for games)", style="Big.TButton", command=self.on_server)
        self.server_button.pack(fill="x", pady=4)

        server_box = ttk.Frame(frame)
        server_box.pack(fill="x", pady=(0, 6))
        self.server_label = ttk.Label(server_box, text="Server stopped.", wraplength=660, justify="left")
        self.server_label.pack(anchor="w")
        buttons = ttk.Frame(server_box)
        buttons.pack(anchor="w", pady=(4, 0))
        self.copy_url_button = ttk.Button(buttons, text="Copy the game address", command=self.copy_url)
        self.copy_key_button = ttk.Button(buttons, text="Copy the key", command=self.copy_key)

        ttk.Button(frame, text="👁  Preview the media in your browser", style="Big.TButton", command=self.on_preview).pack(fill="x", pady=4)
        links = ttk.Frame(frame)
        links.pack(fill="x", pady=(12, 0))
        ttk.Button(links, text="Help", command=lambda: open_externally(GUIDE)).pack(side="left")
        ttk.Button(links, text="Tag list", command=lambda: open_externally(os.path.join(REPO_ROOT, "catalogue", "TAGS.md"))).pack(side="left", padx=6)
        ttk.Button(links, text="Open the pack folder", command=self.on_open_folder).pack(side="left")

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------
    # Makes sure packs/main exists (an empty pack the first time).
    def ensure_pack(self):
        if not os.path.isfile(os.path.join(PACK_DIR, "tags.sqlite")):
            Pack.create(PACK_DIR).close()

    # Returns the modification times of the pack databases: the count is redone only when one
    # changed. The person pack list is read again only when the medias folder itself changed.
    def pack_signature(self):
        medias = os.path.join(PACK_DIR, "medias")
        medias_time = os.path.getmtime(medias) if os.path.isdir(medias) else 0
        if getattr(self, "person_list_time", None) != medias_time:
            self.person_databases = []
            if os.path.isdir(medias):
                with os.scandir(medias) as entries:
                    self.person_databases = [os.path.join(entry.path, "tags.sqlite") for entry in entries
                                             if entry.is_dir() and os.path.isfile(os.path.join(entry.path, "tags.sqlite"))]
            self.person_list_time = medias_time
        databases = [os.path.join(PACK_DIR, "tags.sqlite")] + self.person_databases
        return [medias_time] + [os.path.getmtime(path) for path in databases if os.path.isfile(path)]

    # Shows how many media the pack holds, by origin (only when a database changed, or when forced).
    def refresh_status(self, force=False):
        try:
            self.ensure_pack()
            signature = self.pack_signature()
            if signature == self.status_signature and not force:
                return
            with Pack(PACK_DIR) as pack:
                counts = pack.origin_counts()
            self.status_signature = signature
        except (PackError, OSError) as error:
            self.count_label.configure(text="The pack cannot be read")
            self.detail_label.configure(text=str(error))
            return
        total = sum(counts.values())
        if total == 0:
            self.count_label.configure(text="No media found")
            self.detail_label.configure(text="Start with \"Import a media pack (.zip)\", or add your own files in the media manager.")
            return
        self.count_label.configure(text="{} media found".format(total))
        parts = []
        if counts.get(None):
            parts.append("{} local (added by you)".format(counts[None]))
        for origin, count in sorted(((o, c) for o, c in counts.items() if o), key=lambda item: item[0].lower()):
            parts.append("{} from \"{}\"".format(count, origin))
        self.detail_label.configure(text=" · ".join(parts) + "\nPack folder: " + os.path.relpath(PACK_DIR, REPO_ROOT))

    # Refreshes the status when the window comes back to the front.
    def on_focus(self, event=None):
        if event is None or event.widget is self:
            self.refresh_status()

    # -------------------------------------------------------------------------
    # Import
    # -------------------------------------------------------------------------
    # Asks for a pack zip and imports it with all checks, then comes back here.
    def on_import(self):
        path = filedialog.askopenfilename(title="Choose the media pack you downloaded (.zip)", filetypes=[("Zip archive", "*.zip"), ("All files", "*")])
        if not path:
            return
        self.ensure_pack()
        outcome = {}
        busy = tk.Toplevel(self)
        busy.title("Importing")
        busy.transient(self)
        busy.protocol("WM_DELETE_WINDOW", lambda: None)
        ttk.Label(busy, text="Checking and importing the pack…\nEvery file is verified. This can take a few minutes.", padding=24).pack()
        progress = ttk.Progressbar(busy, mode="indeterminate", length=320)
        progress.pack(padx=24, pady=(0, 24))
        progress.start(12)
        busy.grab_set()
        worker = threading.Thread(target=self.run_import, args=(path, outcome), daemon=True)
        worker.start()
        self.after(300, self.finish_import, worker, outcome, busy)

    # Runs the import in the background.
    @staticmethod
    def run_import(path, outcome):
        try:
            outcome["report"] = import_pack(PACK_DIR, path)
        except ImportRefused as error:
            outcome["refused"] = error
        except (PackError, OSError, ValueError) as error:
            outcome["error"] = error

    # Shows the import result and refreshes the status.
    def finish_import(self, worker, outcome, busy):
        if worker.is_alive():
            self.after(300, self.finish_import, worker, outcome, busy)
            return
        busy.destroy()
        if "refused" in outcome:
            error = outcome["refused"]
            details = "\n".join(error.problems[:20])
            messagebox.showerror("Import refused", "Nothing was imported.\n\n{}\n\n{}".format(error, details).strip())
        elif "error" in outcome:
            messagebox.showerror("Import failed", "Nothing was imported.\n\n{}".format(outcome["error"]))
        else:
            report = outcome["report"]
            manifest = report.get("manifest") or {}
            title = "\"{}\"".format(report["origin"])
            if manifest:
                title += " version {} by {} ({})".format(manifest["version"], manifest["author"], manifest["date"])
            message = "Pack {} imported.\n\n{} new media, {} already present.".format(title, report["added"], report["updated"])
            if report["skipped"]:
                message += "\n{} media left out (tagging rule or missing file).".format(len(report["skipped"]))
            messagebox.showinfo("Import done", message)
        self.refresh_status(force=True)

    # -------------------------------------------------------------------------
    # Media manager
    # -------------------------------------------------------------------------
    # Starts the media manager on the pack (once).
    def on_editor(self):
        if self.editor is not None and self.editor.poll() is None:
            messagebox.showinfo("Media manager", "The media manager is already open.")
            return
        self.ensure_pack()
        self.editor = subprocess.Popen([sys.executable, EDITOR_SCRIPT, PACK_DIR])

    # -------------------------------------------------------------------------
    # Server
    # -------------------------------------------------------------------------
    # Starts or stops the server.
    def on_server(self):
        if self.server is not None and self.server.poll() is None:
            self.stop_server()
            return
        answer = messagebox.askyesnocancel(
            "Private key?",
            "Should games and programs need a private key to get media?\n\n"
            "Yes — only programs that know the key (recommended when other people can reach this computer).\n"
            "No — any program on this computer can ask, nothing to configure.",
        )
        if answer is None:
            return
        self.ensure_pack()
        os.makedirs(os.path.dirname(SERVER_LOG), exist_ok=True)
        log = open(SERVER_LOG, "w", encoding="utf-8")
        self.server = subprocess.Popen(
            [sys.executable, SERVER_SCRIPT, PACK_DIR, "--key" if answer else "--no-key"],
            stdout=log, stderr=subprocess.STDOUT, creationflags=NO_CONSOLE,
        )
        log.close()
        self.server_info = {"key_required": answer}
        self.server_button.configure(text="Starting…", state="disabled")
        self.after(500, self.wait_for_server, 30)

    # Waits until the server answers, then shows its address and key.
    def wait_for_server(self, attempts_left):
        config = self.read_server_config()
        port = int(config.get("port", 5055))
        try:
            with urllib.request.urlopen("http://127.0.0.1:{}/health".format(port), timeout=1) as response:
                ready = response.status == 200
        except OSError:
            ready = False
        if not ready and self.server.poll() is None and attempts_left > 0:
            self.after(500, self.wait_for_server, attempts_left - 1)
            return
        self.server_button.configure(state="normal")
        if not ready:
            self.stop_server()
            messagebox.showerror("Server", "The server could not start.\n\n" + self.read_log_tail()
                                 + "\n\nIf another program uses port {}, change \"port\" in tools/python/server/config.json.".format(port))
            return
        self.server_info["url"] = "http://127.0.0.1:{}/select".format(port)
        self.server_info["key"] = (config.get("api_keys") or [""])[0] if self.server_info["key_required"] else ""
        text = "✅ Server running. Give your game this address:\n    {}".format(self.server_info["url"])
        if self.server_info["key"]:
            text += "\nand this private key:\n    {}".format(self.server_info["key"])
        else:
            text += "\nNo key needed (leave the key empty in your game)."
        text += "\nKeep this window open while you play."
        self.server_label.configure(text=text)
        self.server_button.configure(text="■  Stop the server")
        self.copy_url_button.pack(side="left")
        if self.server_info["key"]:
            self.copy_key_button.pack(side="left", padx=6)

    # Stops the server.
    def stop_server(self):
        if self.server is not None and self.server.poll() is None:
            self.server.terminate()
            try:
                self.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server.kill()
        self.server = None
        self.server_label.configure(text="Server stopped.")
        self.server_button.configure(text="▶  Start the server (for games)", state="normal")
        self.copy_url_button.pack_forget()
        self.copy_key_button.pack_forget()

    # Reads the server configuration (created by the server on its first start).
    @staticmethod
    def read_server_config():
        try:
            with open(SERVER_CONFIG, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    # Returns the last lines of the server log.
    @staticmethod
    def read_log_tail():
        try:
            with open(SERVER_LOG, "r", encoding="utf-8", errors="replace") as handle:
                return "".join(handle.readlines()[-8:])
        except OSError:
            return ""

    # Copies a text to the clipboard.
    def copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    # Copies the game address.
    def copy_url(self):
        self.copy(self.server_info["url"])

    # Copies the private key.
    def copy_key(self):
        self.copy(self.server_info["key"])

    # -------------------------------------------------------------------------
    # Other
    # -------------------------------------------------------------------------
    # Opens the preview page, which reads the pack without any server.
    def on_preview(self):
        webbrowser.open("file:///" + PREVIEW_PAGE.replace(os.sep, "/").lstrip("/"))

    # Opens the pack folder.
    def on_open_folder(self):
        self.ensure_pack()
        open_externally(PACK_DIR)

    # Stops the server before closing.
    def on_close(self):
        if self.server is not None and self.server.poll() is None:
            if not messagebox.askyesno("Quit", "The server will stop and games will no longer get media. Quit?"):
                return
            self.stop_server()
        self.destroy()


# Starts the home window.
def main():
    HomeWindow().mainloop()


if __name__ == "__main__":
    main()
