"""TapeInk desktop UI — Hebrew audio transcription."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox

import customtkinter as ctk

from tapeink.cleanup import DEFAULT_FILLERS
from tapeink.device import detect_device
from tapeink.export import segments_to_display
from tapeink.pipeline import PipelineOptions, run_pipeline
from tapeink.transcribe import DEFAULT_GLOSSARY
from tapeink import textdir

APP_TITLE = "TapeInk"
APP_SUBTITLE = "תמלול אודיו בעברית · הפרדת דוברים · חותמות זמן · ניקוי מילוי"
AUTHOR_HANDLE = "@doron477"
# Written handle-first so Tk's left-to-right run order lands the Hebrew on the
# right, where a Hebrew reader starts the line.
CREDIT = f"© {AUTHOR_HANDLE} · כל הזכויות שמורות"
DEFAULT_OUTPUT = Path.home() / "Documents" / "TapeInk"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS_DIR / "tapeink.ico"
LOGO_PATH = ASSETS_DIR / "tapeink_256.png"

AUDIO_PATTERNS = "*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.wma"
VIDEO_PATTERNS = "*.mp4 *.mkv *.mov *.avi *.webm"
AUDIO_TYPES = [
    ("אודיו ווידאו", f"{AUDIO_PATTERNS} {VIDEO_PATTERNS}"),
    ("אודיו", AUDIO_PATTERNS),
    ("וידאו", VIDEO_PATTERNS),
    ("All files", "*.*"),
]

CARD = ("gray92", "gray17")
CARD_INNER = ("gray86", "gray22")
MUTED = ("gray38", "gray62")
ACCENT = "#F0A431"
ACCENT_HOVER = "#D98E1F"
GHOST_TEXT = ("gray20", "gray90")
GHOST_BORDER = ("gray68", "gray45")
GHOST_HOVER = ("gray82", "gray28")

# Families that actually ship Hebrew glyphs, best first.
HEBREW_FONTS = ("Segoe UI", "Arial", "Tahoma", "David")

DIRECTION_LABELS = {
    "אוטומטי": textdir.AUTO,
    "ימין לשמאל": textdir.RTL,
    "שמאל לימין": textdir.LTR,
}
LANGUAGE_LABELS = {
    "עברית": "he",
    "אנגלית": "en",
    "זיהוי אוטומטי": "",
}


class TapeInkApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self._apply_hebrew_font()

        self.title(APP_TITLE)
        self.geometry("1080x940")
        self.minsize(940, 640)
        self.configure(fg_color=("gray96", "gray12"))
        self._apply_icon()

        self.audio_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.mode = tk.StringVar(value="simple")
        self.model_size = tk.StringVar(value="small")
        self.language_label = tk.StringVar(value="עברית")
        self.direction_label = tk.StringVar(value="אוטומטי")
        self.prefer_cuda = tk.BooleanVar(value=True)
        self.do_diarize = tk.BooleanVar(value=True)
        self.clean_fillers = tk.BooleanVar(value=True)
        self.include_timestamps = tk.BooleanVar(value=True)
        self.num_speakers = tk.StringVar(value="אוטומטי")
        self.status = tk.StringVar(value="מוכן")

        self._busy = False
        self._last_text = ""
        self._last_segments: list[dict] = []
        self._last_language = "he"
        self._last_output_dir: Path | None = None

        device = detect_device(prefer_cuda=True)
        self.device_text = tk.StringVar(value=device.label)

        self._logo_image: ctk.CTkImage | None = None
        self._build()

    # ---------- window chrome ----------

    def _apply_hebrew_font(self) -> None:
        """Pick a font family that covers Hebrew, for every widget in the app.

        CustomTkinter defaults to Roboto, which has no Hebrew glyphs. Tk then
        substitutes a fallback font word by word and lays those runs out left to
        right, so a Hebrew sentence shows up with its words in reverse order.
        One family covering the whole line keeps it a single run, and Tk applies
        BiDi to it correctly.
        """
        available = set(tkfont.families(self))
        for family in HEBREW_FONTS:
            if family in available:
                ctk.ThemeManager.theme["CTkFont"]["family"] = family
                return

    def _apply_icon(self) -> None:
        if not ICON_PATH.exists():
            return
        for attempt in (lambda: self.iconbitmap(default=str(ICON_PATH)), lambda: self.iconbitmap(str(ICON_PATH))):
            try:
                attempt()
                return
            except Exception:
                continue

    def _load_logo(self) -> ctk.CTkImage | None:
        if not LOGO_PATH.exists():
            return None
        try:
            from PIL import Image

            img = Image.open(LOGO_PATH)
            return ctk.CTkImage(light_image=img, dark_image=img, size=(52, 52))
        except Exception:
            return None

    # ---------- layout ----------

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        # Keep the transcript able to shrink, so the status bar and the credit
        # line stay on screen in pro mode on shorter displays.
        self.grid_rowconfigure(2, weight=1, minsize=180)

        self._build_header()
        self._build_controls()
        self._build_results()
        self._build_statusbar()
        self._build_footer()
        self._on_mode_change("פשוט")

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(1, weight=1)

        self._logo_image = self._load_logo()
        if self._logo_image is not None:
            ctk.CTkLabel(header, image=self._logo_image, text="").grid(
                row=0, column=0, rowspan=2, sticky="w", padx=(0, 14)
            )

        ctk.CTkLabel(
            header,
            text=APP_TITLE,
            font=ctk.CTkFont(size=30, weight="bold"),
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            header,
            text=APP_SUBTITLE,
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        ).grid(row=1, column=1, sticky="w", pady=(1, 0))

        badge = ctk.CTkFrame(header, fg_color=CARD, corner_radius=16)
        badge.grid(row=0, column=2, rowspan=2, sticky="e")
        ctk.CTkLabel(
            badge,
            text="מעבד",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).grid(row=0, column=0, padx=(16, 8), pady=(8, 0), sticky="e")
        ctk.CTkLabel(
            badge,
            textvariable=self.device_text,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=1, column=0, padx=(16, 8), pady=(0, 10), sticky="e")

        ctk.CTkSwitch(
            badge,
            text="בהיר",
            width=48,
            command=self._toggle_theme,
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=1, rowspan=2, padx=(4, 14))

    def _build_controls(self) -> None:
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        card.grid(row=1, column=0, sticky="ew", padx=24, pady=8)
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))
        top.grid_columnconfigure(0, weight=1)

        self.mode_switch = ctk.CTkSegmentedButton(
            top,
            values=["פשוט", "מקצועי"],
            command=self._on_mode_change,
            font=ctk.CTkFont(size=13),
            height=32,
        )
        self.mode_switch.grid(row=0, column=0, sticky="w")
        self.mode_switch.set("פשוט")

        ctk.CTkLabel(
            top, text="מצב עבודה", font=ctk.CTkFont(size=13, weight="bold"), anchor="e"
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        # RTL layout: label on the right, entry in the middle, button on the left.
        rows = ctk.CTkFrame(card, fg_color="transparent")
        rows.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 6))
        rows.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            rows, text="בחר קובץ", width=118, height=36, corner_radius=10, command=self._pick_audio
        ).grid(row=0, column=0, padx=(0, 10), pady=6)
        ctk.CTkEntry(
            rows,
            textvariable=self.audio_path,
            height=36,
            corner_radius=10,
            placeholder_text="לא נבחר קובץ",
        ).grid(row=0, column=1, sticky="ew", pady=6)
        ctk.CTkLabel(rows, text="קובץ אודיו", width=100, anchor="e").grid(
            row=0, column=2, sticky="e", padx=(10, 0), pady=6
        )

        ctk.CTkButton(
            rows,
            text="בחר תיקייה",
            width=118,
            height=36,
            corner_radius=10,
            command=self._pick_output,
        ).grid(row=1, column=0, padx=(0, 10), pady=6)
        ctk.CTkEntry(rows, textvariable=self.output_dir, height=36, corner_radius=10).grid(
            row=1, column=1, sticky="ew", pady=6
        )
        ctk.CTkLabel(rows, text="תיקיית שמירה", width=100, anchor="e").grid(
            row=1, column=2, sticky="e", padx=(10, 0), pady=6
        )

        self.pro_card = ctk.CTkFrame(card, fg_color=CARD_INNER, corner_radius=12)
        self._build_pro(self.pro_card)

        action = ctk.CTkFrame(card, fg_color="transparent")
        action.grid(row=3, column=0, sticky="ew", padx=18, pady=(6, 16))
        action.grid_columnconfigure(0, weight=1)

        self.run_btn = ctk.CTkButton(
            action,
            text="התחל תמלול",
            height=44,
            corner_radius=12,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#1B1B1B",
            command=self._start,
        )
        self.run_btn.grid(row=0, column=0, sticky="ew")

    def _build_pro(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure((0, 1, 2), weight=1)

        selectors = [
            ("גודל מודל", self.model_size, ["tiny", "base", "small", "medium", "large-v3"]),
            ("שפת מקור", self.language_label, list(LANGUAGE_LABELS)),
            ("מספר דוברים", self.num_speakers, ["אוטומטי", "1", "2", "3", "4", "5", "6"]),
        ]
        # Right-to-left reading order for the selector columns.
        for col, (label, var, values) in enumerate(reversed(selectors)):
            ctk.CTkLabel(
                parent, text=label, font=ctk.CTkFont(size=12), text_color=MUTED, anchor="e"
            ).grid(row=0, column=col, sticky="e", padx=14, pady=(14, 2))
            ctk.CTkOptionMenu(
                parent, variable=var, values=values, height=34, corner_radius=10
            ).grid(row=1, column=col, sticky="ew", padx=14, pady=(0, 10))

        toggles = ctk.CTkFrame(parent, fg_color="transparent")
        toggles.grid(row=2, column=0, columnspan=3, sticky="e", padx=14, pady=(0, 10))
        for text, var in (
            ("העדף GPU", self.prefer_cuda),
            ("הפרדת דוברים", self.do_diarize),
            ("ניקוי מילות מילוי", self.clean_fillers),
        ):
            ctk.CTkCheckBox(
                toggles, text=text, variable=var, checkbox_width=20, checkbox_height=20
            ).pack(side="right", padx=(18, 0))

        # Right-hand box first, to keep the reading order.
        self.fillers_box = self._build_list_box(
            parent, "מילות מילוי לניקוי (שורה לכל מילה)", DEFAULT_FILLERS, column=1, span=2
        )
        self.glossary_box = self._build_list_box(
            parent, "מונחים ושמות (שורה לכל מונח)", DEFAULT_GLOSSARY, column=0, span=1
        )

    def _build_list_box(
        self, parent: ctk.CTkFrame, title: str, values: list[str], *, column: int, span: int
    ) -> ctk.CTkTextbox:
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            anchor="e",
        ).grid(row=3, column=column, columnspan=span, sticky="e", padx=14, pady=(0, 4))

        box = ctk.CTkTextbox(parent, height=76, corner_radius=10, font=ctk.CTkFont(size=13))
        box.grid(row=4, column=column, columnspan=span, sticky="ew", padx=14, pady=(0, 14))
        box.insert("1.0", "\n".join(values))
        try:
            box.tag_config("rtl", justify="right")
            box.tag_add("rtl", "1.0", "end")
        except Exception:
            pass
        return box

    def _build_results(self) -> None:
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        card.grid(row=2, column=0, sticky="nsew", padx=24, pady=8)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="תמלול", font=ctk.CTkFont(size=15, weight="bold"), anchor="e").grid(
            row=0, column=2, sticky="e"
        )

        tools = ctk.CTkFrame(bar, fg_color="transparent")
        tools.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            tools,
            text="פתח תיקייה",
            width=104,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=GHOST_BORDER,
            text_color=GHOST_TEXT,
            hover_color=GHOST_HOVER,
            command=self._open_output,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            tools, text="העתק", width=76, height=30, corner_radius=8, command=self._copy_text
        ).pack(side="left", padx=(0, 14))
        ctk.CTkSegmentedButton(
            tools,
            values=list(DIRECTION_LABELS),
            variable=self.direction_label,
            command=self._on_display_change,
            height=30,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(tools, text="כיוון טקסט", font=ctk.CTkFont(size=12), text_color=MUTED).pack(
            side="left", padx=(0, 18)
        )
        ctk.CTkSwitch(
            tools,
            text="חותמות זמן",
            variable=self.include_timestamps,
            onvalue=True,
            offvalue=False,
            command=self._on_display_change,
            font=ctk.CTkFont(size=12),
            switch_width=38,
            switch_height=18,
        ).pack(side="left")

        self.output_box = ctk.CTkTextbox(
            card,
            wrap="word",
            corner_radius=12,
            height=200,
            font=ctk.CTkFont(size=15),
        )
        self.output_box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(4, 18))
        self._render_placeholder()

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 10))
        bar.grid_columnconfigure(1, weight=1)

        self.status_dot = ctk.CTkLabel(bar, text="●", text_color=MUTED, font=ctk.CTkFont(size=14))
        self.status_dot.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkLabel(bar, textvariable=self.status, anchor="w", font=ctk.CTkFont(size=12)).grid(
            row=0, column=1, sticky="w"
        )
        self.progress = ctk.CTkProgressBar(bar, height=6, corner_radius=3, width=260)
        self.progress.grid(row=0, column=2, sticky="e")
        self.progress.set(0)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 12))
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkFrame(footer, height=1, fg_color=CARD_INNER).grid(
            row=0, column=0, sticky="ew", pady=(0, 8)
        )
        ctk.CTkLabel(
            footer, text=CREDIT, font=ctk.CTkFont(size=11), text_color=MUTED
        ).grid(row=1, column=0)

    # ---------- interactions ----------

    def _toggle_theme(self) -> None:
        current = ctk.get_appearance_mode()
        ctk.set_appearance_mode("Light" if current == "Dark" else "Dark")

    def _on_mode_change(self, value: str) -> None:
        if value == "מקצועי":
            self.mode.set("pro")
            self.pro_card.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 4))
            self._grow_to_fit()
        else:
            self.mode.set("simple")
            self.pro_card.grid_forget()

    def _grow_to_fit(self) -> None:
        """Give the pro panel room, so the status bar and credit stay on screen.

        Only the height is touched, and it is read from the requested geometry
        rather than winfo_width/height, which still report stale values when the
        mode is switched before the window manager has applied a resize.
        """
        self.update_idletasks()
        wanted = min(self.winfo_reqheight(), self.winfo_screenheight() - 80)

        size, _, position = self.wm_geometry().partition("+")
        width, _, height = size.partition("x")
        if height.isdigit() and int(height) >= wanted:
            return
        self.geometry(f"{width}x{wanted}" + (f"+{position}" if position else ""))

    def _on_display_change(self, _value: str | None = None) -> None:
        """Re-render the transcript after a direction or timestamp change."""
        if self._last_text:
            self._render_transcript()
        else:
            self._render_placeholder()

    def _current_direction(self, text: str) -> str:
        mode = DIRECTION_LABELS.get(self.direction_label.get(), textdir.AUTO)
        return textdir.resolve_direction(mode, text, self._last_language)

    def _render_transcript(self) -> None:
        """Tk applies BiDi itself; we pick line layout and alignment per direction."""
        direction = self._current_direction(self._last_text)
        rtl = textdir.is_rtl(direction)

        if self._last_segments:
            body = segments_to_display(
                self._last_segments,
                rtl=rtl,
                include_timestamps=self.include_timestamps.get(),
                include_speakers=self.do_diarize.get(),
            )
        else:
            body = self._last_text

        self.output_box.delete("1.0", "end")
        self.output_box.insert("1.0", body)
        self._apply_justify(direction)

    def _apply_justify(self, direction: str) -> None:
        try:
            self.output_box.tag_config("dir", justify=textdir.justify_for(direction))
            self.output_box.tag_add("dir", "1.0", "end")
        except Exception:
            pass

    def _render_placeholder(self) -> None:
        self._last_text = ""
        self.output_box.delete("1.0", "end")
        self.output_box.insert("1.0", "התמלול יופיע כאן…")
        self._apply_justify(textdir.RTL)

    def _pick_audio(self) -> None:
        path = filedialog.askopenfilename(title="בחר קובץ אודיו", filetypes=AUDIO_TYPES)
        if path:
            self.audio_path.set(path)

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(title="בחר תיקיית שמירה")
        if path:
            self.output_dir.set(path)

    def _copy_text(self) -> None:
        if not self._last_text:
            return
        self.clipboard_clear()
        self.clipboard_append(self._last_text)
        self.status.set("התמלול הועתק ללוח")

    def _open_output(self) -> None:
        target = self._last_output_dir or Path(self.output_dir.get() or DEFAULT_OUTPUT)
        if not target.exists():
            messagebox.showinfo(APP_TITLE, "התיקייה עוד לא נוצרה.")
            return
        if sys.platform == "win32":
            os.startfile(str(target))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(target)])

    def _parse_speakers(self) -> int | None:
        raw = self.num_speakers.get().strip()
        if raw == "אוטומטי":
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def _box_lines(self, box: ctk.CTkTextbox, fallback: list[str]) -> list[str]:
        if self.mode.get() != "pro":
            return list(fallback)
        lines = box.get("1.0", "end").splitlines()
        return [line.strip() for line in lines if line.strip()]

    def _fillers_list(self) -> list[str]:
        return self._box_lines(self.fillers_box, DEFAULT_FILLERS)

    def _glossary_list(self) -> list[str]:
        return self._box_lines(self.glossary_box, DEFAULT_GLOSSARY)

    # ---------- pipeline ----------

    def _start(self) -> None:
        if self._busy:
            return
        audio = self.audio_path.get().strip()
        if not audio:
            messagebox.showwarning(APP_TITLE, "בחר קובץ אודיו קודם.")
            return
        if not Path(audio).exists():
            messagebox.showerror(APP_TITLE, "קובץ האודיו לא נמצא.")
            return

        out = Path(self.output_dir.get().strip() or DEFAULT_OUTPUT)
        out.mkdir(parents=True, exist_ok=True)
        self._last_output_dir = out

        simple = self.mode.get() == "simple"
        language = "he" if simple else LANGUAGE_LABELS.get(self.language_label.get(), "he")
        options = PipelineOptions(
            model_size="small" if simple else self.model_size.get(),
            language=language,
            prefer_cuda=True if simple else self.prefer_cuda.get(),
            diarize=True if simple else self.do_diarize.get(),
            num_speakers=None if simple else self._parse_speakers(),
            clean_fillers=True if simple else self.clean_fillers.get(),
            fillers=self._fillers_list(),
            glossary=self._glossary_list(),
            include_timestamps=self.include_timestamps.get(),
            include_speakers=True,
        )

        self._busy = True
        self.run_btn.configure(state="disabled", text="מתמלל…")
        self.status_dot.configure(text_color=ACCENT)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status.set("מתחיל…")
        self._last_text = ""
        self._last_segments = []
        self.output_box.delete("1.0", "end")

        threading.Thread(target=self._worker, args=(audio, out, options), daemon=True).start()

    def _worker(self, audio: str, out: Path, options: PipelineOptions) -> None:
        try:

            def on_progress(msg: str) -> None:
                self.after(0, lambda: self.status.set(msg))

            result = run_pipeline(audio, out, options, on_progress=on_progress)
            files = " · ".join(p.name for p in result.saved_files)
            summary = (
                f"נשמר: {files} · "
                f"מעבד: {result.device.label} · מודל: {result.transcript.model_size}"
            )
            self.after(
                0,
                lambda: self._done(
                    True,
                    result.plain_text or "(אין טקסט)",
                    result.transcript.language,
                    summary,
                    result.segments,
                ),
            )
        except Exception as exc:  # noqa: BLE001 — surface any pipeline failure in the UI
            self.after(0, lambda: self._done(False, str(exc), self._last_language, "", []))

    def _done(
        self,
        ok: bool,
        text: str,
        language: str,
        summary: str,
        segments: list[dict] | None = None,
    ) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1.0 if ok else 0.0)
        self._busy = False
        self.run_btn.configure(state="normal", text="התחל תמלול")

        if ok:
            self._last_language = language or "he"
            self._last_text = text
            self._last_segments = segments or []
            self._render_transcript()
            self.status.set(summary or "הושלם")
            self.status_dot.configure(text_color="#4CAF50")
        else:
            self.status.set("שגיאה בתמלול")
            self.status_dot.configure(text_color="#E53935")
            self._last_text = ""
            self._last_segments = []
            self.output_box.delete("1.0", "end")
            self.output_box.insert("1.0", f"שגיאה: {text}")
            self._apply_justify(textdir.RTL)
            messagebox.showerror(APP_TITLE, text)


def main() -> None:
    app = TapeInkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
