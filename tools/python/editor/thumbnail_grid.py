"""Scrollable grid of person-pack cards and media thumbnails for the editor."""

import tkinter as tk
from functools import partial
from tkinter import ttk


class MediaThumbnailGrid(ttk.Frame):
    CARD_WIDTH = 176
    CARD_HEIGHT = 164

    # Creates a scrollable, ratio-safe pack and media grid.
    def __init__(self, parent, on_pack_click, on_media_click, on_parent_click):
        super().__init__(parent)
        self.on_pack_click = on_pack_click
        self.on_media_click = on_media_click
        self.on_parent_click = on_parent_click
        self.image_references = []

        self.canvas = tk.Canvas(self, background="#202124", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, background="#202124")
        self.inner_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self.update_scroll_region)
        self.canvas.bind("<Configure>", self.resize_inner)
        self.canvas.bind("<MouseWheel>", self.handle_mousewheel)
        self.canvas.bind("<Button-4>", self.handle_mousewheel)
        self.canvas.bind("<Button-5>", self.handle_mousewheel)

    # Keeps the canvas scroll region aligned with its contents.
    def update_scroll_region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # Makes the grid content follow the available canvas width.
    def resize_inner(self, event):
        self.canvas.itemconfigure(self.inner_window, width=event.width)

    # Scrolls consistently on Windows and Linux mouse wheel events.
    def handle_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction * 3, "units")

    # Rebuilds the visible cards: parent card, person packs, then media thumbnails.
    def render(self, persons, media_rows, thumbnail_loader, selected_media_ids, show_parent=False, person_thumbnail_loader=None):
        for child in self.inner.winfo_children():
            child.destroy()
        self.image_references = []

        columns = max(2, max(self.canvas.winfo_width(), 720) // self.CARD_WIDTH)
        item_index = 0
        if show_parent:
            self.render_parent_card(item_index, columns)
            item_index += 1
        for person in persons:
            self.render_person_card(person, item_index, columns, person_thumbnail_loader)
            item_index += 1
        for media in media_rows:
            self.render_media_card(media, item_index, columns, thumbnail_loader, int(media["id"]) in selected_media_ids)
            item_index += 1

        if item_index == 0:
            tk.Label(
                self.inner, text="No media for these filters. Use the Import tab to add some.",
                background="#202124", foreground="#d7d7d7", padx=20, pady=30,
            ).grid(row=0, column=0, sticky="w")
        self.canvas.yview_moveto(0)

    # Creates one fixed-size card frame at a grid position.
    def _card(self, item_index, columns, background, active=False):
        row_index, column_index = divmod(item_index, columns)
        card = tk.Frame(
            self.inner, width=self.CARD_WIDTH - 10, height=self.CARD_HEIGHT - 10, background=background,
            cursor="hand2", relief="sunken" if active else "raised", borderwidth=3 if active else 1,
        )
        card.grid(row=row_index, column=column_index, padx=5, pady=5, sticky="nsew")
        card.grid_propagate(False)
        return card

    # Renders the card that goes back to the enclosing pack.
    def render_parent_card(self, item_index, columns):
        background = "#d69b2d"
        card = self._card(item_index, columns, background)
        visual = tk.Label(card, text="BACK", background="#8d6115", foreground="#ffffff", width=20, height=6, font=("TkDefaultFont", 10, "bold"))
        visual.pack(fill="x", padx=5, pady=(5, 2))
        details = tk.Label(card, text="Back to the main pack", background=background, foreground="#211500")
        details.pack(side="bottom", pady=5)
        for widget in (card, visual, details):
            widget.bind("<Button-1>", lambda event: self.on_parent_click())

    # Renders one person-pack card with its portrait.
    def render_person_card(self, person, item_index, columns, thumbnail_loader):
        background = "#d69b2d"
        card = self._card(item_index, columns, background)
        thumbnail = thumbnail_loader(person) if thumbnail_loader is not None else None
        if thumbnail is not None:
            self.image_references.append(thumbnail)
            visual = tk.Label(card, image=thumbnail, background="#151515")
        else:
            visual = tk.Label(card, text="PERSON", background="#8d6115", foreground="#ffffff", width=20, height=6, font=("TkDefaultFont", 10, "bold"))
        visual.pack(fill="x", padx=5, pady=(5, 2))
        details = tk.Label(card, text="Person · {} media".format(person["media_count"]), background=background, foreground="#211500")
        details.pack(side="bottom", pady=5)
        callback = partial(self.on_pack_click, person["hash"])
        for widget in (card, visual, details):
            widget.bind("<Button-1>", callback)

    # Renders one selectable media card and its cached thumbnail.
    def render_media_card(self, media, item_index, columns, thumbnail_loader, selected):
        background = "#375a7f" if selected else "#303134"
        card = self._card(item_index, columns, background, active=selected)
        thumbnail = thumbnail_loader(media)
        if thumbnail is not None:
            self.image_references.append(thumbnail)
            visual = tk.Label(card, image=thumbnail, background="#151515")
        else:
            visual = tk.Label(card, text=(media["type"] or "media").split("/")[-1].upper(), background="#151515", foreground="#d7d7d7", width=20, height=6)
        visual.pack(fill="x", padx=5, pady=(5, 2))
        origin = media["origin"] if "origin" in media.keys() and media["origin"] else "local"
        details = tk.Label(card, text="#{} · {} · {}".format(media["id"], media["type"].split("/")[-1], origin[:16]), background=background, foreground="#ffffff", anchor="w")
        details.pack(fill="x", padx=6)
        tag_label = tk.Label(card, text=media["tags"] or "No tag yet", background=background, foreground="#bfc4ca", anchor="w", wraplength=148, justify="left")
        tag_label.pack(fill="x", padx=6, pady=(1, 5))
        callback = partial(self.on_media_click, int(media["id"]))
        for widget in (card, visual, details, tag_label):
            widget.bind("<Button-1>", callback)
