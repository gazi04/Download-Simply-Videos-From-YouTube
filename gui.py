import customtkinter as ctk
import os
import threading
import sys
import urllib.request
import io
from pathlib import Path
from tkinter import messagebox, filedialog
from PIL import Image, ImageDraw, ImageFont

from download import download_youtube_content
from search import search_youtube

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Grid constants
COLS = 3          # cards per row
CARD_W = 220      # card width  (px)
THUMB_W = 210     # thumbnail width  inside card
THUMB_H = 118     # thumbnail height (16:9 of THUMB_W)


def _make_placeholder(w: int, h: int) -> Image.Image:
    """Dark grey placeholder with a play-triangle, sized w×h."""
    img = Image.new("RGB", (w, h), color=(40, 40, 40))
    draw = ImageDraw.Draw(img)
    # simple triangle
    cx, cy = w // 2, h // 2
    size = min(w, h) // 4
    draw.polygon(
        [(cx - size, cy - size), (cx - size, cy + size), (cx + size, cy)],
        fill=(100, 100, 100)
    )
    return img


class VideoCard(ctk.CTkFrame):
    """
    YouTube-style vertical card:
      ┌──────────────────┐
      │   thumbnail      │  ← full-width, 16:9, checkbox top-right
      │  [✓] overlay     │
      ├──────────────────┤
      │  Title (bold)    │
      │  Channel · dur   │
      └──────────────────┘
    Clicking anywhere on the card toggles the checkbox.
    """

    def __init__(self, master, result: dict, **kwargs):
        super().__init__(master, corner_radius=10, width=CARD_W, **kwargs)
        self.result = result
        self.selected = ctk.BooleanVar(value=False)

        self.scrollable_frame = master

        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        # ── Thumbnail ────────────────────────────────────────────
        placeholder = _make_placeholder(THUMB_W, THUMB_H)
        self._ctk_img = ctk.CTkImage(
            light_image=placeholder, dark_image=placeholder,
            size=(THUMB_W, THUMB_H)
        )
        self.thumb_label = ctk.CTkLabel(
            self, text="", image=self._ctk_img,
            width=THUMB_W, height=THUMB_H, corner_radius=8
        )
        self.thumb_label.grid(row=0, column=0, padx=5, pady=(6, 0))
        threading.Thread(target=self._load_thumb, daemon=True).start()

        # ── Checkbox overlaid top-right of thumbnail ─────────────
        self.checkbox = ctk.CTkCheckBox(
            self, text="", variable=self.selected,
            width=24, height=24,
            checkbox_width=22, checkbox_height=22
        )
        self.checkbox.place(relx=0.93, rely=0.02, anchor="ne")

        # ── Title ────────────────────────────────────────────────
        title = result.get("title", "Unknown Title")
        self.title_label = ctk.CTkLabel(
            self, text=title,
            wraplength=CARD_W - 16,
            justify="left", anchor="nw",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=CARD_W - 16
        )
        self.title_label.grid(row=1, column=0, padx=8, pady=(6, 1), sticky="ew")

        # ── Channel · duration ───────────────────────────────────
        channel = result.get("channel", "")
        duration = result.get("duration_str", "")
        meta = f"{channel}  ·  {duration}" if channel and duration else channel or duration
        self.meta_label = ctk.CTkLabel(
            self, text=meta,
            wraplength=CARD_W - 16,
            justify="left", anchor="nw",
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray65"),
            width=CARD_W - 16
        )
        self.meta_label.grid(row=2, column=0, padx=8, pady=(0, 10), sticky="ew")

        # We need to bind BOTH the click (toggle) AND the scroll event
        all_widgets = (self, self.thumb_label, self.title_label, self.meta_label)
        
        for widget in all_widgets:
            # Existing toggle binding
            widget.bind("<Button-1>", self._toggle)
            
            # NEW: Mouse wheel bindings for Windows/MacOS and Linux
            widget.bind("<MouseWheel>", self._on_mousewheel)  # Windows/Mac
            widget.bind("<Button-4>", self._on_mousewheel)    # Linux scroll up
            widget.bind("<Button-5>", self._on_mousewheel)    # Linux scroll down

    def _toggle(self, _event=None):
        self.selected.set(not self.selected.get())

    def _on_mousewheel(self, event):
        """Passes the scroll event from the card to the scrollable frame."""
        if event.num == 4: # Linux Up
            self.scrollable_frame._parent_canvas.yview_scroll(-1, "units")
        elif event.num == 5: # Linux Down
            self.scrollable_frame._parent_canvas.yview_scroll(1, "units")
        else: # Windows/Mac (event.delta)
            # Dividing by -120 is standard for Tkinter scroll steps
            self.scrollable_frame._parent_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _load_thumb(self):
        url = self.result.get("thumbnail")
        if not url:
            return
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).resize((THUMB_W, THUMB_H), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(THUMB_W, THUMB_H))
            self._ctk_img = ctk_img  # keep reference
            self.thumb_label.after(
                0, lambda i=ctk_img: self.thumb_label.configure(image=i)
            )
        except Exception:
            pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Simply YouTube Downloader")
        self.geometry("860x780")
        self.minsize(720, 600)

        self._custom_download_path = None
        self._cards: list[VideoCard] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # results area expands

        # ── Header ───────────────────────────────────────────────
        ctk.CTkLabel(
            self, text="Simply YouTube Downloader",
            font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10))

        # ── Search bar ───────────────────────────────────────────
        sf = ctk.CTkFrame(self, fg_color="transparent")
        sf.grid(row=1, column=0, padx=20, pady=(0, 6), sticky="ew")
        sf.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            sf, placeholder_text="🔍  Search for a song, artist or video…",
            height=44, font=ctk.CTkFont(size=14)
        )
        self.search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.search_entry.bind("<Return>", lambda _: self.do_search())

        self.search_btn = ctk.CTkButton(
            sf, text="Search", width=100, height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.do_search
        )
        self.search_btn.grid(row=0, column=1)

        # ── Format + result count row ────────────────────────────
        cf = ctk.CTkFrame(self)
        cf.grid(row=2, column=0, padx=20, pady=(0, 6), sticky="ew")
        cf.grid_columnconfigure(2, weight=1)

        self.format_var = ctk.StringVar(value="MP4")
        ctk.CTkRadioButton(cf, text="MP4 Video", variable=self.format_var, value="MP4").grid(
            row=0, column=0, padx=(16, 8), pady=10
        )
        ctk.CTkRadioButton(cf, text="MP3 Audio", variable=self.format_var, value="MP3").grid(
            row=0, column=1, padx=(0, 16), pady=10
        )
        self.results_info = ctk.CTkLabel(
            cf, text="", anchor="e",
            font=ctk.CTkFont(size=12), text_color=("gray45", "gray65")
        )
        self.results_info.grid(row=0, column=2, padx=16, pady=10, sticky="e")

        # ── Scrollable grid of results ───────────────────────────
        self.results_scroll = ctk.CTkScrollableFrame(self)
        self.results_scroll.grid(row=3, column=0, padx=20, pady=(0, 6), sticky="nsew")
        # configure COLS equal-weight columns
        for c in range(COLS):
            self.results_scroll.grid_columnconfigure(c, weight=1, uniform="card")

        self.empty_label = ctk.CTkLabel(
            self.results_scroll,
            text="Search for a song or video above to get started  ☝",
            font=ctk.CTkFont(size=13), text_color=("gray50", "gray60")
        )
        self.empty_label.grid(row=0, column=0, columnspan=COLS, pady=60)

        # ── Download directory ───────────────────────────────────
        df = ctk.CTkFrame(self)
        df.grid(row=4, column=0, padx=20, pady=(0, 6), sticky="ew")
        df.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(df, text="📁 Save to:", font=ctk.CTkFont(size=13)).grid(
            row=0, column=0, padx=(14, 6), pady=8, sticky="w"
        )
        self.dir_path_label = ctk.CTkLabel(
            df, text=self._fmt_path(self.get_download_path()),
            anchor="w", font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        self.dir_path_label.grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        ctk.CTkButton(df, text="Change…", width=90, command=self.choose_directory).grid(
            row=0, column=2, padx=(4, 8), pady=8
        )
        ctk.CTkButton(
            df, text="Reset", width=70, fg_color="transparent", border_width=1,
            command=self.reset_directory
        ).grid(row=0, column=3, padx=(0, 14), pady=8)

        # ── Progress ─────────────────────────────────────────────
        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.grid(row=5, column=0, padx=20, pady=(0, 4), sticky="ew")
        pf.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            pf, text="Ready", font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray70")
        )
        self.status_label.grid(row=0, column=0, sticky="w", pady=(0, 3))

        self.progress_bar = ctk.CTkProgressBar(pf, mode="indeterminate")
        self.progress_bar.grid(row=1, column=0, sticky="ew")
        self.progress_bar.set(0)

        # ── Action buttons ────────────────────────────────────────
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=6, column=0, padx=20, pady=(6, 16), sticky="ew")
        bf.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(
            bf, text="Select All", fg_color="transparent", border_width=1,
            command=self.select_all, height=40
        ).grid(row=0, column=0, padx=6, pady=4, sticky="ew")

        ctk.CTkButton(
            bf, text="Deselect All", fg_color="transparent", border_width=1,
            command=self.deselect_all, height=40
        ).grid(row=0, column=1, padx=6, pady=4, sticky="ew")

        self.download_button = ctk.CTkButton(
            bf, text="⬇  Download Selected",
            fg_color="#28a745", hover_color="#218838",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.start_download, height=40
        )
        self.download_button.grid(row=0, column=2, padx=6, pady=4, sticky="ew")

        ctk.CTkButton(
            bf, text="📂  Open Folder",
            command=self.open_downloads, height=40
        ).grid(row=0, column=3, padx=6, pady=4, sticky="ew")

        # ── Scrollable grid of results ───────────────────────────
        self.results_scroll = ctk.CTkScrollableFrame(self)
        self.results_scroll.grid(row=3, column=0, padx=20, pady=(0, 6), sticky="nsew")
        
        # FIX: Bind the scrollable frame itself (the "gap") to the scroll handler
        self.results_scroll.bind("<MouseWheel>", self._on_results_scroll)
        self.results_scroll.bind("<Button-4>", self._on_results_scroll) # Linux
        self.results_scroll.bind("<Button-5>", self._on_results_scroll) # Linux

        for c in range(COLS):
            self.results_scroll.grid_columnconfigure(c, weight=1, uniform="card")

        self.download_in_progress = False

    def _on_results_scroll(self, event):
        """Allows scrolling when the mouse is over the empty space (the gap)."""
        if event.num == 4: # Linux Up
            self.results_scroll._parent_canvas.yview_scroll(-1, "units")
        elif event.num == 5: # Linux Down
            self.results_scroll._parent_canvas.yview_scroll(1, "units")
        else: # Windows/Mac
            self.results_scroll._parent_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # ── Search ────────────────────────────────────────────────────────────────

    def do_search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        self._clear_results()
        self._set_status("Searching…")
        self.progress_bar.start()
        self.search_btn.configure(state="disabled")
        threading.Thread(target=self._run_search, args=(query,), daemon=True).start()

    def _run_search(self, query: str):
        try:
            results = search_youtube(query, max_results=30)
            self.after(0, self._show_results, results)
        except Exception as e:
            self.after(0, self._search_error, str(e))

    def _show_results(self, results: list):
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.search_btn.configure(state="normal")

        if not results:
            self._set_status("No results found.")
            self.empty_label.configure(text="No results found. Try a different search.")
            self.empty_label.grid()
            return

        self._set_status("Click cards to select, then press  ⬇ Download Selected")
        self.results_info.configure(text=f"{len(results)} results")

        for idx, r in enumerate(results):
            row, col = divmod(idx, COLS)
            card = VideoCard(self.results_scroll, r)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="n")
            self._cards.append(card)

    def _search_error(self, msg: str):
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.search_btn.configure(state="normal")
        self._set_status(f"Search failed: {msg}")

    def _clear_results(self):
        for card in self._cards:
            card.destroy()
        self._cards.clear()
        self.results_info.configure(text="")
        self.empty_label.grid_remove()

    # ── Selection ─────────────────────────────────────────────────────────────

    def select_all(self):
        for c in self._cards:
            c.selected.set(True)

    def deselect_all(self):
        for c in self._cards:
            c.selected.set(False)

    # ── Download ──────────────────────────────────────────────────────────────

    def start_download(self):
        if self.download_in_progress:
            messagebox.showwarning("Warning", "A download is already in progress!")
            return

        urls = [c.result["url"] for c in self._cards if c.selected.get()]
        if not urls:
            messagebox.showerror("Nothing selected",
                                 "Please select at least one video to download.")
            return

        audio_only = (self.format_var.get() == "MP3")
        Path(self.get_download_path()).mkdir(parents=True, exist_ok=True)

        n = len(urls)
        self._set_status(f"Downloading {n} item{'s' if n != 1 else ''}…")
        self.progress_bar.start()
        self.download_button.configure(state="disabled", text="Downloading…")
        self.download_in_progress = True

        threading.Thread(
            target=self._run_download, args=(urls, audio_only), daemon=True
        ).start()

    def _run_download(self, urls, audio_only):
        try:
            download_youtube_content(
                urls=urls,
                output_path=self.get_download_path(),
                audio_only=audio_only,
                logger=None
            )
            self.after(0, self._finish_download, True, "Download complete! 🎉")
        except Exception as e:
            self.after(0, self._finish_download, False, f"Error: {str(e)}")

    def _finish_download(self, success: bool, message: str):
        self.progress_bar.stop()
        self.progress_bar.set(1 if success else 0)
        self._set_status(message)
        self.download_button.configure(state="normal", text="⬇  Download Selected")
        self.download_in_progress = False
        if success:
            messagebox.showinfo("Done", message)
        else:
            messagebox.showerror("Failed", message)

    # ── Directory ─────────────────────────────────────────────────────────────

    def _default_download_path(self) -> str:
        p = Path.home() / "Music" / "YouTube Downloads"
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    def get_download_path(self) -> str:
        return self._custom_download_path or self._default_download_path()

    @staticmethod
    def _fmt_path(path: str) -> str:
        try:
            return f"~/{Path(path).relative_to(Path.home())}"
        except ValueError:
            return path

    def _refresh_dir_label(self):
        self.dir_path_label.configure(text=self._fmt_path(self.get_download_path()))

    def choose_directory(self):
        chosen = filedialog.askdirectory(title="Select Download Folder",
                                         initialdir=self.get_download_path())
        if chosen:
            self._custom_download_path = chosen
            self._refresh_dir_label()

    def reset_directory(self):
        self._custom_download_path = None
        self._refresh_dir_label()

    def open_downloads(self):
        path = self.get_download_path()
        Path(path).mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')

    def _set_status(self, text: str):
        self.status_label.configure(text=text)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
