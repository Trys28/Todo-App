"""Dark, monospace TO DO board: task cards on a grid, status pills, drag to reorder,
overlays for adding / editing. Standard library only."""
import json
import sys
import time
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from pathlib import Path

SAVE_FILE = Path.home() / ".modern_todo.json"

# ---------- palette (dark only) ----------
BG = "#000000"            # main background: black
SURFACE = "#0D0D10"       # secondary background: slightly less black
SURFACE_2 = "#16161B"     # hover / input fields
BTN = "#20202A"           # small in-card buttons
BORDER = "#222229"
BORDER_HOVER = "#3A3A46"
TEXT = "#FFFFFF"
MUTED = "#8A8A96"
FAINT = "#55555F"
BLUE = "#1E3A8A"          # buttons: dark blue
BLUE_HOVER = "#2547A8"
BLUE_PRESS = "#16296B"
GLOW = "#3B63E8"
MAROON = "#8A1C2B"
MAROON_HOVER = "#A3263A"
MAROON_PRESS = "#651421"
RED_GLOW = "#E0475C"
DANGER = "#FF5C5C"
PAD = 20                  # button padding in pixels

# Status pills: (label, border colour, text colour). The fill is the border colour
# mixed ~15% into the card colour, which gives the see-through look.
STATUS_ORDER = ("todo", "doing", "done")
STATUS = {
    "todo": ("To Do", "#FFFFFF", "#FFFFFF"),     # white
    "doing": ("Doing", "#3B63E8", "#8FAAFF"),    # blue
    "done": ("Done", "#22B35E", "#6BE39B"),      # green
}
PILL_TINT = 0.15

GAP = 16                  # space between cards (matches the stat cards)
DIM = 0.55                # how dark the board gets behind an overlay (0 to 1)
_dim_level = 0.0          # current dim level, read by dimmable buttons

# Button colour schemes: resting colour, hover colour, pressed colour, glow colours
BUTTON_STYLES = {
    "blue": dict(base=BLUE, hover=BLUE_HOVER, press=BLUE_PRESS, glow=GLOW, glow_hover=GLOW),
    "danger": dict(base=MAROON, hover=MAROON_HOVER, press=MAROON_PRESS,
                   glow=RED_GLOW, glow_hover=RED_GLOW),
    # blue normally, turns maroon red when hovered
    "blue_to_maroon": dict(base=BLUE, hover=MAROON, press=MAROON_PRESS,
                           glow=GLOW, glow_hover=RED_GLOW),
}

if sys.platform == "win32":  # crisper text on high-DPI Windows screens
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


# ---------- helpers ----------
def lerp(c1, c2, t):
    """Blend two hex colours. t=0 -> c1, t=1 -> c2."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def animate(widget, ms, step, done=None, ease=ease_out_cubic):
    """Call step(progress) about 60 times a second for `ms` milliseconds."""
    start = time.perf_counter()

    def tick():
        p = min(1.0, (time.perf_counter() - start) * 1000 / ms)
        try:
            step(ease(p))
        except tk.TclError:   # widget was destroyed mid-animation
            return
        if p < 1:
            widget.after(16, tick)
        elif done:
            done()

    tick()


def pick_mono():
    available = set(tkfont.families())
    for name in ("Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono",
                 "Liberation Mono", "Ubuntu Mono", "Courier New"):
        if name in available:
            return name
    return tkfont.nametofont("TkFixedFont").actual("family")


def shorten(text, limit=30):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def draw_pencil(c, cx, cy, size, color, cut_color):
    """Vector pencil icon (no font glyph needed). Returns (item ids, eraser-gap id)."""
    ux, uy, vx, vy = 0.7071, -0.7071, 0.7071, 0.7071   # along / across the pencil
    half, w = size / 2, size * 0.17
    tip = (cx - ux * half, cy - uy * half)
    end = (cx + ux * half, cy + uy * half)
    base = (tip[0] + ux * size * 0.30, tip[1] + uy * size * 0.30)

    def pt(p, k):
        return p[0] + vx * w * k, p[1] + vy * w * k
    body = c.create_polygon(*pt(base, 1), *pt(end, 1), *pt(end, -1), *pt(base, -1),
                            fill=color, outline=color)
    point = c.create_polygon(*pt(base, 1), *pt(base, -1), *tip, fill=color, outline=color)
    cut = (end[0] - ux * size * 0.22, end[1] - uy * size * 0.22)
    gap = c.create_line(*pt(cut, 1.3), *pt(cut, -1.3), fill=cut_color,
                        width=max(1, round(size * 0.08)))
    return (body, point), gap


def wrap_lines(text, font, width, max_lines):
    """Word-wrap `text` to `width` pixels, at most `max_lines` lines, ending in … if cut."""
    lines = []
    for para in text.replace("\r", "").split("\n"):
        cur = ""
        for word in para.split():
            while font.measure(word) > width:       # a single word wider than the card
                k = len(word)
                while k > 1 and font.measure(word[:k]) > width:
                    k -= 1
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(word[:k])
                word = word[k:]
            trial = f"{cur} {word}" if cur else word
            if font.measure(trial) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and font.measure(last + "…") > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines or [""]


# ---------- custom button ----------
class RoundedButton(tk.Canvas):
    """Rounded button with an animated glow, colour fade on hover and a press effect.

    Pass `square=44` for a fixed square button instead of text + padding.
    `padx` sets the horizontal padding separately from `pad` (vertical).
    """

    def __init__(self, parent, text, command, parent_bg, font, scheme="blue",
                 pad=PAD, square=None, radius=14, glow=8, padx=None, dimmable=True):
        self.text, self.command, self.font = text, command, font
        self.dimmable = dimmable   # buttons behind an overlay get darkened with the board
        self.parent_bg, self.r, self.glow, self.drop = parent_bg, radius, glow, 4
        self.colors = BUTTON_STYLES[scheme]
        if square:
            self.w = self.h = square
        else:
            f = tkfont.Font(font=font)
            self.w = f.measure(text) + 2 * (pad if padx is None else padx)
            self.h = f.metrics("linespace") + 2 * pad
        super().__init__(parent, width=self.w + 2 * glow,
                         height=self.h + 2 * glow + self.drop,
                         highlightthickness=0, bd=0, bg=parent_bg, cursor="hand2")
        self.hover, self.target, self.pressed, self._job = 0.0, 0.0, False, None
        self.bind("<Enter>", lambda e: self._set_target(1.0))
        self.bind("<Leave>", lambda e: self._set_target(0.0))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _set_target(self, value):
        self.target = value
        if self._job is None:
            self._tick()

    def _tick(self):
        diff = self.target - self.hover
        if abs(diff) < 0.02:
            self.hover, self._job = self.target, None
        else:
            self.hover += diff * 0.25
            self._job = self.after(16, self._tick)
        try:
            self._draw()
        except tk.TclError:
            self._job = None

    def _press(self, e):
        self.pressed = True
        self._draw()

    def _release(self, e):
        self.pressed = False
        self._draw()
        if 0 <= e.x <= int(self["width"]) and 0 <= e.y <= int(self["height"]):
            self.after(70, self.command)   # tiny delay so the press effect is visible

    def _draw(self):
        self.delete("all")
        c, g, w, h = self.colors, self.glow, self.w, self.h
        dim = _dim_level if self.dimmable else 0.0

        def sh(col):
            return lerp(col, "#000000", dim)
        glow_color = lerp(c["glow"], c["glow_hover"], self.hover)
        intensity = 0.15 if self.pressed else 0.30 + 0.55 * self.hover
        # soft shadow/glow: stacked rounded rects fading out from the button edge
        for k in range(g, 0, -1):
            closeness = 1 - (k - 1) / g
            col = sh(lerp(self.parent_bg, glow_color, intensity * closeness ** 2 * 0.6))
            rounded_rect(self, g - k, g - k + self.drop, g + w + k, g + h + k + self.drop,
                         self.r + k, fill=col, outline=col)
        body = sh(c["press"] if self.pressed else lerp(c["base"], c["hover"], self.hover))
        inset = 1 if self.pressed else 0   # "squish" when pressed
        rounded_rect(self, g + inset, g + inset, g + w - inset, g + h - inset, self.r,
                     fill=body, outline=body)
        self.create_text(g + w / 2, g + h / 2 + inset, text=self.text, fill=sh(TEXT), font=self.font)


class StatusPicker(tk.Canvas):
    """Three selectable status pills (To Do / Doing / Done) for the overlay form."""

    def __init__(self, parent, mono, value, on_change, s):
        self.font = tkfont.Font(family=mono, size=10, weight="bold")
        self.s = s
        self.pw, self.ph, self.gap = s(104), s(36), s(10)
        super().__init__(parent, width=3 * self.pw + 2 * self.gap, height=self.ph + 4,
                         bg=SURFACE, highlightthickness=0, bd=0, cursor="hand2")
        self.value, self.on_change = value, on_change
        self.bind("<Button-1>", self._click)
        self._draw()

    def _click(self, e):
        i = int(e.x // (self.pw + self.gap))
        if 0 <= i < 3 and e.x - i * (self.pw + self.gap) <= self.pw:
            self.value = STATUS_ORDER[i]
            self.on_change(self.value)
            self._draw()

    def _draw(self):
        self.delete("all")
        for i, key in enumerate(STATUS_ORDER):
            label, line, fg = STATUS[key]
            x1 = i * (self.pw + self.gap)
            x2, cy = x1 + self.pw, 2 + self.ph / 2
            if key == self.value:     # translucent fill + solid border, like the card pills
                rounded_rect(self, x1 + 2, 2, x2 - 2, self.ph + 2, self.ph / 2,
                             fill=lerp(SURFACE, line, PILL_TINT + 0.05), outline=line, width=2)
                self.create_text((x1 + x2) / 2, cy, text=label, fill=fg, font=self.font)
            else:
                rounded_rect(self, x1 + 2, 2, x2 - 2, self.ph + 2, self.ph / 2,
                             fill=SURFACE_2, outline=BORDER_HOVER, width=1)
                r = self.s(4)
                self.create_oval(x1 + self.s(20) - r, cy - r, x1 + self.s(20) + r, cy + r,
                                 fill=line, outline=line)
                self.create_text((x1 + x2) / 2 + self.s(8), cy, text=label, fill=MUTED,
                                 font=self.font)


# ---------- overlays ----------
class Overlay(tk.Frame):
    """Modal panel floating over the board (inside the main window, not a separate
    window). The board behind it is darkened. It slides in, shakes, slides out, sizes
    itself to its contents, and grabs all input so nothing behind it can be clicked.
    Escape closes it."""
    W, MIN_H = 660, 600      # minimum size in 96-dpi pixels (scaled for the screen)

    def __init__(self, app):
        s = app.s
        super().__init__(app, bg=BG, padx=s(12), pady=s(12))   # black ring around the panel
        self.app, self.s = app, s
        self._closing = False
        self.body = tk.Frame(self, bg=SURFACE, highlightthickness=1,
                             highlightbackground=BORDER_HOVER)
        self.body.pack(fill="both", expand=True)

    def present(self, focus_widget):
        """Call once the contents are built."""
        self._focus = focus_widget
        self.update_idletasks()
        w = max(self.s(self.W), self.winfo_reqwidth())
        h = max(self.s(self.MIN_H), self.winfo_reqheight())
        w = min(w, max(200, self.app.winfo_width() - 40))
        h = min(h, max(200, self.app.winfo_height() - 40))
        self._dy = self.s(18)
        self.place(relx=0.5, rely=0.5, anchor="center", width=w, height=h, x=0, y=self._dy)
        self.lift()
        animate(self, 220, lambda p: self.place_configure(y=round(self._dy * (1 - p))))
        self.bind_all("<Escape>", lambda e: self.close())
        self.after(60, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self._focus.focus_force()
        except tk.TclError:
            pass

    def shake(self):
        offsets = [-10, 10, -8, 8, -5, 5, -2, 2, 0]

        def step(i):
            if i >= len(offsets):
                return
            try:
                self.place_configure(x=self.s(offsets[i]))
            except tk.TclError:
                return
            self.after(30, lambda: step(i + 1))
        step(0)

    def close(self):
        if self._closing:
            return
        self._closing = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.unbind_all("<Escape>")
        self.app.overlay_closed(self)
        animate(self, 120, lambda p: self.place_configure(y=round(self.s(10) * p)),
                done=self.destroy)


class TaskOverlay(Overlay):
    """Form overlay used for both 'New item' and 'Edit item': title, description, status."""
    W, MIN_H = 680, 640

    def __init__(self, app, mono, on_save, task=None):
        super().__init__(app)
        s = self.s
        self.on_save = on_save
        editing = task is not None
        b = self.body
        side = s(34)

        # Buttons are packed first so they are never pushed out of view
        buttons = tk.Frame(b, bg=SURFACE)
        buttons.pack(side="bottom", anchor="e", padx=s(22), pady=(0, s(20)))
        RoundedButton(buttons, "Cancel", self.close, SURFACE, (mono, 12, "bold"),
                      pad=s(14), padx=s(30), dimmable=False).pack(side="left", padx=(0, 10))
        RoundedButton(buttons, "Save changes" if editing else "Create item", self.submit,
                      SURFACE, (mono, 12, "bold"), pad=s(14), padx=s(30),
                      dimmable=False).pack(side="left")

        tk.Label(b, text="Edit item" if editing else "New item", font=(mono, 20, "bold"),
                 bg=SURFACE, fg=TEXT, anchor="w").pack(fill="x", padx=side, pady=(s(32), s(4)))
        tk.Label(b, text="Update the details below." if editing else "Fill in the details below.",
                 font=(mono, 11), bg=SURFACE, fg=MUTED, anchor="w").pack(fill="x", padx=side)

        def field_label(text):
            tk.Label(b, text=text, font=(mono, 9, "bold"), bg=SURFACE, fg=MUTED,
                     anchor="w").pack(fill="x", padx=side, pady=(s(24), s(8)))

        field_label("TITLE")
        self.entry = tk.Entry(b, font=(mono, 14), bg=SURFACE_2, fg=TEXT, insertbackground=TEXT,
                              relief="flat", bd=0, highlightthickness=2,
                              highlightbackground=BORDER, highlightcolor=BLUE_HOVER)
        self.entry.pack(fill="x", padx=side, ipady=s(12))

        field_label("DESCRIPTION")
        self.desc = tk.Text(b, height=6, wrap="word", font=(mono, 12), bg=SURFACE_2, fg=TEXT,
                            insertbackground=TEXT, relief="flat", bd=0, padx=s(12), pady=s(12),
                            highlightthickness=2, highlightbackground=BORDER,
                            highlightcolor=BLUE_HOVER)
        self.desc.pack(fill="x", padx=side)

        field_label("STATUS")
        self.picker = StatusPicker(b, mono, task["status"] if editing else "todo",
                                   lambda value: None, s)
        self.picker.pack(anchor="w", padx=side)

        if editing:
            self.entry.insert(0, task["title"])
            self.desc.insert("1.0", task["description"])
            self.entry.icursor("end")
        self.entry.bind("<Return>", lambda e: (self.desc.focus_set(), "break")[1])
        self.desc.bind("<Control-Return>", lambda e: (self.submit(), "break")[1])
        self.present(self.entry)

    def submit(self):
        title = self.entry.get().strip()
        if not title:   # empty title: shake the card and flash the field red
            self.entry.configure(highlightbackground=DANGER, highlightcolor=DANGER)
            self.after(450, self._reset_border)
            self.shake()
            return
        self.on_save(title, self.desc.get("1.0", "end").strip(), self.picker.value)
        self.close()

    def _reset_border(self):
        try:
            self.entry.configure(highlightbackground=BORDER, highlightcolor=BLUE_HOVER)
        except tk.TclError:
            pass


class ConfirmOverlay(Overlay):
    """'Are you sure?' overlay for destructive actions."""
    W, MIN_H = 560, 320

    def __init__(self, app, mono, message, confirm_text, on_confirm):
        super().__init__(app)
        s = self.s
        self.on_confirm = on_confirm
        b = self.body
        side = s(34)
        buttons = tk.Frame(b, bg=SURFACE)
        buttons.pack(side="bottom", anchor="e", padx=s(22), pady=(0, s(20)))
        RoundedButton(buttons, "Cancel", self.close, SURFACE, (mono, 12, "bold"),
                      pad=s(14), padx=s(30), dimmable=False).pack(side="left", padx=(0, 10))
        RoundedButton(buttons, confirm_text, self.confirm, SURFACE, (mono, 12, "bold"),
                      scheme="danger", pad=s(14), padx=s(30),
                      dimmable=False).pack(side="left")
        tk.Label(b, text="Are you sure?", font=(mono, 20, "bold"), bg=SURFACE, fg=TEXT,
                 anchor="w").pack(fill="x", padx=side, pady=(s(32), s(14)))
        tk.Label(b, text=message, font=(mono, 13), bg=SURFACE, fg=TEXT, anchor="w",
                 justify="left", wraplength=s(self.W) - 2 * side).pack(fill="x", padx=side)
        tk.Label(b, text="This can't be undone.", font=(mono, 10), bg=SURFACE, fg=MUTED,
                 anchor="w").pack(fill="x", padx=side, pady=(s(10), 0))
        self.present(b)

    def confirm(self):
        callback = self.on_confirm
        self.close()
        callback()


# ---------- main app ----------
class TodoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        # Everything measured in pixels is multiplied by this so the layout keeps its
        # proportions on high-DPI screens (fonts already scale on their own).
        try:
            self.ui_scale = max(1.0, float(self.tk.call("tk", "scaling")) * 72 / 96)
        except (tk.TclError, ValueError):
            self.ui_scale = 1.0
        self.s = lambda px: round(px * self.ui_scale)

        self.title("To Do")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(self.s(1040), int(sw * 0.92))}x{min(self.s(820), int(sh * 0.9))}")
        self.minsize(min(self.s(720), int(sw * 0.7)), min(self.s(700), int(sh * 0.8)))
        self.configure(bg=BG)

        self.tasks = []                 # [{"title", "description", "status", "done_at"}]
        self.cards = {}                 # id(task) -> card canvas
        self._overlay = None
        self._flash_task = None
        self._intro = True              # first render counts up from zero
        self._clear_visible = False
        self._ready = False             # first render waits until the grid has a real size
        self._cols, self._cw = 1, 300
        self._content_h = 0
        self._relayout_job = None
        self._press = None              # pointer-down state on a card (click or drag)
        self._order = []                # live task order while dragging
        self._dim_items, self._dim_buttons = [], []
        self._dim_f, self._dim_token = 0.0, 0
        self.stat_vars = {k: tk.StringVar(value="0") for k in ("total", "todo", "doing", "done")}
        self.stat_shown = {k: 0 for k in self.stat_vars}
        self.stat_token = {k: 0 for k in self.stat_vars}
        self._load()

        self.mono = pick_mono()
        self.f_title = (self.mono, 28, "bold")
        self.f_body = (self.mono, 12)
        self.f_small = (self.mono, 10)
        self.f_big = (self.mono, 28, "bold")
        self.f_ctitle = tkfont.Font(family=self.mono, size=14, weight="bold")
        self.f_ctitle_done = tkfont.Font(family=self.mono, size=14, weight="bold",
                                         overstrike=True)
        self.f_cdesc = tkfont.Font(family=self.mono, size=11)
        self.f_pill = tkfont.Font(family=self.mono, size=10, weight="bold")

        # Card geometry: padding, pill height, and a height that fits 2 title lines
        # plus 4 description lines
        s = self.s
        self.card_pad = s(24)
        self.pill_h = self.f_pill.metrics("linespace") + s(12)
        self.card_h = (2 * self.card_pad + self.pill_h + s(16)
                       + 2 * self.f_ctitle.metrics("linespace") + s(10)
                       + 4 * self.f_cdesc.metrics("linespace"))
        self.min_cw = s(380)

        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self._style_bar(0.0)

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style_bar(self, f):
        def d(c):
            return lerp(c, "#000000", f)
        self.style.configure("Blue.Horizontal.TProgressbar", troughcolor=d(SURFACE),
                             background=d(BLUE_HOVER), bordercolor=d(BG),
                             lightcolor=d(BLUE_HOVER), darkcolor=d(BLUE_HOVER), thickness=8)

    # ----- layout -----
    def card(self, parent):
        return tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=BORDER)

    def _build(self):
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=44, pady=36)

        # Header
        head = tk.Frame(main, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="To Do", font=self.f_title, bg=BG, fg=TEXT,
                 anchor="w").pack(fill="x")
        self.sub_lbl = tk.Label(head, font=self.f_body, bg=BG, fg=MUTED, anchor="w")
        self.sub_lbl.pack(fill="x", pady=(6, 0))

        # Stat cards
        row = tk.Frame(main, bg=BG)
        row.pack(fill="x", pady=(32, 0))
        stats = [("total", "Total"), ("todo", "To Do"), ("doing", "Doing"), ("done", "Done")]
        for i, (key, name) in enumerate(stats):
            row.columnconfigure(i, weight=1, uniform="stats")
            c = self.card(row)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else GAP, 0))
            tk.Label(c, text=name, font=self.f_small, bg=SURFACE, fg=MUTED,
                     anchor="w").pack(fill="x", padx=22, pady=(20, 0))
            tk.Label(c, textvariable=self.stat_vars[key], font=self.f_big, bg=SURFACE,
                     fg=TEXT, anchor="w").pack(fill="x", padx=22, pady=(4, 20))

        self.progress = ttk.Progressbar(main, maximum=100, style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=28)

        # Footer is packed before the grid so it never gets pushed off-screen
        self.footer = tk.Frame(main, bg=BG)
        self.footer.pack(side="bottom", fill="x")
        RoundedButton(self.footer, "New Item", self.open_new, BG, (self.mono, 12, "bold"),
                      pad=14, padx=44).pack(side="left", pady=(20, 0))
        self.clear_btn = RoundedButton(self.footer, "Clear completed", self.ask_clear, BG,
                                       self.f_small, scheme="blue_to_maroon")

        # Scrollable grid of task cards (cards are positioned with place())
        wrap = tk.Frame(main, bg=BG)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, highlightthickness=0, bd=0, bg=BG, yscrollincrement=40)
        self.canvas.pack(fill="both", expand=True)
        self.list_inner = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))
        self.bind_all("<Button-4>", lambda e: self._scroll(-1))
        self.bind_all("<Button-5>", lambda e: self._scroll(1))

    def _scroll(self, direction):
        if self._overlay_open():
            return
        try:
            if self._content_h > self.canvas.winfo_height():
                self.canvas.yview_scroll(direction, "units")
        except tk.TclError:
            pass

    # ----- grid geometry -----
    def _geometry(self):
        w = self.canvas.winfo_width()
        if w < 50:   # not on screen yet
            return 1, self.min_cw
        cols = max(1, (w + GAP) // (self.min_cw + GAP))
        return cols, (w - (cols - 1) * GAP) // cols

    def _slot(self, i):
        return (i % self._cols) * (self._cw + GAP), (i // self._cols) * (self.card_h + GAP)

    def _on_canvas_configure(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)
        if self._relayout_job:
            self.after_cancel(self._relayout_job)
        self._relayout_job = self.after(60, self._relayout)

    def _relayout(self):
        self._relayout_job = None
        if self._press and self._press["dragging"]:
            return
        if not self._ready or self._geometry() != (self._cols, self._cw):
            self._ready = True
            self.render()
        else:
            self._update_extent()

    def _update_extent(self):
        n = len(self.tasks)
        rows = -(-n // self._cols) if n else 0
        self._content_h = rows * self.card_h + max(0, rows - 1) * GAP
        h = max(self._content_h + 4, self.canvas.winfo_height())
        self.canvas.itemconfigure(self._win, height=h)
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), h))

    # ----- rendering -----
    def render(self):
        flash = self._flash_task
        self._flash_task = None
        for child in self.list_inner.winfo_children():
            child.destroy()
        self.cards = {}
        self._cols, self._cw = self._geometry()

        if not self.tasks:
            tk.Label(self.list_inner, text="Nothing here yet.\nPress New Item to add a task.",
                     font=self.f_body, bg=BG, fg=MUTED, justify="center"
                     ).place(relx=0.5, y=60, anchor="n")
        for i, t in enumerate(self.tasks):
            self._card(t, i, flash)
        self._update_extent()

        total = len(self.tasks)
        counts = {k: sum(1 for t in self.tasks if t["status"] == k) for k in STATUS_ORDER}
        n_done = counts["done"]
        self.sub_lbl.configure(text=f"{n_done} of {total} completed" if total
                               else "Nothing to do. Enjoy!")

        # "Clear completed" only appears when there is something to clear
        if n_done and not self._clear_visible:
            self.clear_btn.pack(side="right", pady=(20, 0))
            self._clear_visible = True
        elif not n_done and self._clear_visible:
            self.clear_btn.pack_forget()
            self._clear_visible = False

        # count-up numbers + smooth progress bar (slow on launch, quick afterwards)
        ms = 1200 if self._intro else 350
        self._intro = False
        self._tween_stat("total", total, ms)
        for k in STATUS_ORDER:
            self._tween_stat(k, counts[k], ms)
        target = (n_done / total * 100) if total else 0
        start = float(self.progress["value"])
        animate(self, ms, lambda p: self.progress.configure(value=start + (target - start) * p))

    def _tween_stat(self, key, target, ms):
        start = self.stat_shown[key]
        self.stat_token[key] += 1
        token = self.stat_token[key]

        def step(p):
            if token != self.stat_token[key]:   # a newer animation took over
                return
            value = round(start + (target - start) * p)
            self.stat_shown[key] = value
            self.stat_vars[key].set(str(value))
        animate(self, ms, step)

    # ----- cards -----
    def _card(self, task, i, flash):
        cw = self._cw
        c = tk.Canvas(self.list_inner, width=cw, height=self.card_h, bg=SURFACE, bd=0,
                      highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
        x, y = self._slot(i)
        c.place(x=x, y=y, width=cw, height=self.card_h)
        c.task, c.pos, c.target, c.tok, c.zone = task, (x, y), (x, y), 0, None
        c.hit, c.ids = {}, {}
        self.cards[id(task)] = c
        self._draw_card(c, task)

        c.bind("<Enter>", lambda e: self._card_enter(c))
        c.bind("<Leave>", lambda e: self._card_leave(c))
        c.bind("<Motion>", lambda e: self._card_motion(c, e))
        c.bind("<ButtonPress-1>", lambda e: self._card_press(c, e))
        c.bind("<B1-Motion>", lambda e: self._card_drag(c, e))
        c.bind("<ButtonRelease-1>", lambda e: self._card_release(c, e))

        if flash is task:   # new task: glows blue, then fades into place
            animate(c, 700, lambda p: c.configure(bg=lerp(BLUE, SURFACE, p)))

    def _draw_card(self, c, task):
        cw, pad, s = self._cw, self.card_pad, self.pill_h
        done = task["status"] == "done"
        label, line, fg = STATUS[task["status"]]

        # status pill: solid border, see-through tinted fill (click to cycle)
        pw = self.f_pill.measure(label) + self.s(30)
        rounded_rect(c, pad, pad, pad + pw, pad + s, s / 2, fill=lerp(SURFACE, line, PILL_TINT),
                     outline=line, width=max(1, self.s(1.5)))
        c.create_text(pad + pw / 2, pad + s / 2, text=label, fill=fg, font=self.f_pill)
        c.hit["pill"] = (pad, pad, pad + pw, pad + s)

        # delete (✕) and edit (pencil) buttons, top right
        r = self.s(9)
        dx2 = cw - pad
        dx1 = dx2 - s
        c.ids["del"] = rounded_rect(c, dx1, pad, dx2, pad + s, r, fill=BTN, outline=BTN)
        c.ids["del_x"] = c.create_text((dx1 + dx2) / 2, pad + s / 2, text="✕", fill=MUTED,
                                       font=self.f_pill)
        c.hit["del"] = (dx1, pad, dx2, pad + s)
        ex2 = dx1 - self.s(8)
        ex1 = ex2 - s
        c.ids["edit"] = rounded_rect(c, ex1, pad, ex2, pad + s, r, fill=BTN, outline=BTN)
        _, c.ids["cut"] = draw_pencil(c, (ex1 + ex2) / 2, pad + s / 2, s * 0.52, TEXT, BTN)
        c.hit["edit"] = (ex1, pad, ex2, pad + s)

        # title (max 2 lines) and description (as many lines as fit)
        tfont = self.f_ctitle_done if done else self.f_ctitle
        tlines = wrap_lines(task["title"], tfont, cw - 2 * pad, 2)
        ty = pad + s + self.s(16)
        c.create_text(pad, ty, text="\n".join(tlines), anchor="nw", font=tfont,
                      fill=MUTED if done else TEXT)
        ty += len(tlines) * tfont.metrics("linespace") + self.s(10)
        ls = self.f_cdesc.metrics("linespace")
        max_lines = max(1, (self.card_h - pad - ty) // ls)
        if task["description"]:
            dlines, dfill = wrap_lines(task["description"], self.f_cdesc, cw - 2 * pad,
                                       max_lines), MUTED
        else:
            dlines, dfill = ["No description"], FAINT
        c.create_text(pad, ty, text="\n".join(dlines), anchor="nw", font=self.f_cdesc,
                      fill=dfill)

    # ----- card hover -----
    def _zone(self, c, x, y):
        for name, (x1, y1, x2, y2) in c.hit.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return None

    def _card_motion(self, c, e):
        if not self._overlay_open():
            self._set_zone(c, self._zone(c, e.x, e.y))

    def _set_zone(self, c, zone):
        if zone == c.zone:
            return
        c.zone = zone
        try:
            edit_bg = BLUE_HOVER if zone == "edit" else BTN
            c.itemconfigure(c.ids["edit"], fill=edit_bg, outline=edit_bg)
            c.itemconfigure(c.ids["cut"], fill=edit_bg)
            c.itemconfigure(c.ids["del"], fill=MAROON_HOVER if zone == "del" else BTN,
                            outline=MAROON_HOVER if zone == "del" else BTN)
            c.itemconfigure(c.ids["del_x"], fill=TEXT if zone == "del" else MUTED)
            if not self._dragging(c):
                c.configure(cursor="hand2" if zone else "arrow")
        except tk.TclError:
            pass

    def _card_enter(self, c):
        if not self._dragging(c) and not self._overlay_open():
            c.configure(bg=SURFACE_2, highlightbackground=BORDER_HOVER)

    def _card_leave(self, c):
        if self._dragging(c) or self._overlay_open():
            return
        c.configure(bg=SURFACE, highlightbackground=BORDER)
        self._set_zone(c, None)

    @staticmethod
    def _index(items, task):
        """Position of `task` in `items` by identity (two tasks can have equal contents)."""
        return next(i for i, t in enumerate(items) if t is task)

    def _dragging(self, c):
        return bool(self._press and self._press["dragging"] and self._press["card"] is c)

    # ----- click + drag -----
    def _card_press(self, c, e):
        self._press = {"card": c, "zone": self._zone(c, e.x, e.y), "dragging": False,
                       "x0": e.x_root, "y0": e.y_root, "ox": e.x, "oy": e.y}

    def _card_drag(self, c, e):
        p = self._press
        if not p or p["card"] is not c:
            return
        if not p["dragging"]:
            # pressing on pill/pencil/✕ never drags; small wiggles don't count as a drag
            if p["zone"] or abs(e.x_root - p["x0"]) + abs(e.y_root - p["y0"]) < 6:
                return
            p["dragging"] = True
            self._order = list(self.tasks)
            c.tok += 1                      # cancel any glide in progress
            tk.Misc.lift(c)                 # (Canvas.lift would raise canvas items instead)
            c.configure(cursor="fleur", bg=SURFACE_2, highlightbackground=GLOW,
                        highlightcolor=GLOW)

        # follow the pointer (coordinates relative to the scrolling grid)
        x = e.x_root - self.list_inner.winfo_rootx() - p["ox"]
        y = e.y_root - self.list_inner.winfo_rooty() - p["oy"]
        c.place(x=round(x), y=round(y))
        c.pos = (x, y)

        # which slot is the card hovering over? the others slide out of the way
        col = min(self._cols - 1, max(0, int((x + self._cw / 2) // (self._cw + GAP))))
        row = max(0, int((y + self.card_h / 2) // (self.card_h + GAP)))
        idx = min(len(self._order) - 1, row * self._cols + col)
        cur = self._index(self._order, c.task)
        if idx != cur:
            self._order.insert(idx, self._order.pop(cur))
            for i, t in enumerate(self._order):
                other = self.cards.get(id(t))
                if other is None or other is c:
                    continue
                if other.target != self._slot(i):
                    self._glide(other, *self._slot(i))

        # auto-scroll when dragging near the top / bottom edge of the grid
        top = self.canvas.winfo_rooty()
        if e.y_root < top + 36:
            self._scroll(-1)
        elif e.y_root > top + self.canvas.winfo_height() - 36:
            self._scroll(1)

    def _card_release(self, c, e):
        p, self._press = self._press, None
        if not p or p["card"] is not c:
            return
        if p["dragging"]:
            task = c.task
            self.tasks = list(self._order)
            self._save()
            c.configure(cursor="arrow")
            self._glide(c, *self._slot(self._index(self.tasks, task)), ms=160, done=self.render)
            return
        zone = self._zone(c, e.x, e.y)
        if zone and zone == p["zone"]:
            if zone == "pill":
                self.cycle_status(c.task)
            elif zone == "edit":
                self.open_edit(c.task)
            elif zone == "del":
                self.ask_delete(c.task)

    def _glide(self, c, tx, ty, ms=180, done=None):
        """Slide a card to (tx, ty)."""
        sx, sy = c.pos
        c.target = (tx, ty)
        c.tok += 1
        tok = c.tok

        def step(p):
            if tok != c.tok:
                return
            x, y = sx + (tx - sx) * p, sy + (ty - sy) * p
            c.place(x=round(x), y=round(y))
            c.pos = (x, y)

        def fin():
            if tok == c.tok and done:
                done()
        animate(c, ms, step, done=fin)

    # ----- overlays (+ darkening the board behind them) -----
    def _overlay_open(self):
        o = self._overlay
        return o is not None and o.winfo_exists() and not o._closing

    def _open(self, factory):
        if self._overlay_open():
            self._overlay.lift()
            return
        for c in list(self.cards.values()):   # clear hover looks so they aren't frozen in
            try:
                self._card_leave(c)
            except tk.TclError:
                pass
        self._overlay = factory()
        self._dim(True)

    def overlay_closed(self, overlay):
        if self._overlay is overlay:
            self._overlay = None
            self._dim(False)

    def _collect_dim(self, widget, skip, items, buttons):
        """Remember the original colours of everything on the board (except the overlay)."""
        for child in widget.winfo_children():
            if child is skip:
                continue
            if isinstance(child, RoundedButton):   # these shade themselves (see _dim_level)
                if child.dimmable:
                    buttons.append(child)
                continue
            for opt in ("bg", "fg", "highlightbackground", "highlightcolor",
                        "insertbackground"):
                try:
                    r, g, b = child.winfo_rgb(str(child.cget(opt)))
                    items.append((child, opt, None, (r >> 8, g >> 8, b >> 8)))
                except tk.TclError:
                    pass
            if isinstance(child, tk.Canvas):
                for item in child.find_all():
                    for opt in ("fill", "outline"):
                        try:
                            r, g, b = child.winfo_rgb(child.itemcget(item, opt))
                            items.append((child, opt, item, (r >> 8, g >> 8, b >> 8)))
                        except tk.TclError:
                            pass
            self._collect_dim(child, skip, items, buttons)

    def _apply_dim(self, f):
        global _dim_level
        _dim_level = f
        for w, opt, item, (r, g, b) in self._dim_items:
            col = "#%02x%02x%02x" % (round(r * (1 - f)), round(g * (1 - f)), round(b * (1 - f)))
            try:
                if item is None:
                    w.configure(**{opt: col})
                else:
                    w.itemconfigure(item, **{opt: col})
            except tk.TclError:   # widget was rebuilt since we recorded it
                pass
        for btn in self._dim_buttons:
            try:
                btn._draw()
            except tk.TclError:
                pass
        self._style_bar(f)

    def _dim(self, on):
        if on and not self._dim_items:
            self._dim_items, self._dim_buttons = [], []
            self._collect_dim(self, self._overlay, self._dim_items, self._dim_buttons)
        start, end = self._dim_f, (DIM if on else 0.0)
        self._dim_token += 1
        token = self._dim_token

        def step(p):
            if token == self._dim_token:
                self._dim_f = start + (end - start) * p
                self._apply_dim(self._dim_f)

        def done():
            if not on and token == self._dim_token:
                self._dim_items, self._dim_buttons = [], []
        animate(self, 200, step, done=done)

    def open_new(self):
        self._open(lambda: TaskOverlay(self, self.mono, self.add_task))

    def open_edit(self, task):
        self._open(lambda: TaskOverlay(
            self, self.mono,
            lambda title, desc, status: self.edit_task(task, title, desc, status), task))

    def ask_delete(self, task):
        self._open(lambda: ConfirmOverlay(
            self, self.mono, f"Delete “{shorten(task['title'])}”?", "Delete",
            lambda: self.delete(task)))

    def ask_clear(self):
        n = sum(1 for t in self.tasks if t["status"] == "done")
        if n == 0:
            return
        self._open(lambda: ConfirmOverlay(
            self, self.mono, f"Clear {n} completed task{'s' if n != 1 else ''}?", "Clear",
            self.clear_done))

    # ----- actions -----
    def _set_status(self, task, status):
        if status != task["status"]:
            task["status"] = status
            task["done_at"] = time.time() if status == "done" else 0.0

    def add_task(self, title, description, status):
        task = {"title": title, "description": description, "status": "todo", "done_at": 0.0}
        self._set_status(task, status)
        self.tasks.append(task)
        self._flash_task = task
        self._changed()

    def edit_task(self, task, title, description, status):
        task["title"], task["description"] = title, description
        self._set_status(task, status)
        self._changed()

    def cycle_status(self, task):
        nxt = STATUS_ORDER[(STATUS_ORDER.index(task["status"]) + 1) % len(STATUS_ORDER)]
        self._set_status(task, nxt)
        self._changed()

    def delete(self, task):
        self.tasks = [t for t in self.tasks if t is not task]
        self._changed()

    def clear_done(self):
        self.tasks = [t for t in self.tasks if t["status"] != "done"]
        self._changed()

    def _changed(self):
        self._save()
        self.render()

    # ----- saving -----
    def _load(self):
        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
            tasks = []
            for t in data.get("tasks", []):
                status = t.get("status")
                if status not in STATUS_ORDER:   # older save files only had done / not done
                    status = "done" if t.get("done") else "todo"
                tasks.append({"title": str(t.get("title", t.get("text", ""))),
                              "description": str(t.get("description", "")),
                              "status": status,
                              "done_at": float(t.get("done_at", 0))})
            self.tasks = tasks
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass   # first run or unreadable file: start fresh

    def _save(self):
        # "text" and "done" are kept so the previous version of the app can still read the file
        out = [dict(t, text=t["title"], done=t["status"] == "done") for t in self.tasks]
        try:
            SAVE_FILE.write_text(json.dumps({"tasks": out}, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _on_close(self):
        self._save()
        self.destroy()


if __name__ == "__main__":
    TodoApp().mainloop()
