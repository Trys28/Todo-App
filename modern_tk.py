import json
import sys
import time
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from pathlib import Path

SAVE_FILE = Path.home() / ".modern_todo.json"

# ---------- palette (dark, premium matte aesthetic) ----------
BG = "#09090B"            # rich deep black/zinc background
SURFACE = "#121216"       # card background: soft dark grey
SURFACE_2 = "#1A1A22"     # hover / input fields / elevated layers
BORDER = "#272730"        # crisp subtle border
BORDER_HOVER = "#3F3F50"
TEXT = "#F4F4F5"          # bright primary text
MUTED = "#9B9BAF"         # muted secondary text
BLUE = "#2563EB"          # buttons: modern royal blue
BLUE_HOVER = "#3B82F6"
BLUE_PRESS = "#1D4ED8"
GLOW = "#3B82F633"
MAROON = "#9F1239"        # refined dark rose / maroon for danger
MAROON_HOVER = "#BE123C"
MAROON_PRESS = "#881337"
RED_GLOW = "#F43F5E33"
DANGER = "#FB7185"
PAD = 20                  # button padding in pixels

BUTTON_STYLES = {
    "blue": dict(base=BLUE, hover=BLUE_HOVER, press=BLUE_PRESS, glow="#1D4ED8", glow_hover="#3B82F6"),
    "danger": dict(base=MAROON, hover=MAROON_HOVER, press=MAROON_PRESS,
                   glow="#881337", glow_hover="#BE123C"),
    "blue_to_maroon": dict(base=BLUE, hover=MAROON, press=MAROON_PRESS,
                           glow="#1D4ED8", glow_hover="#881337"),
}

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


# ---------- helpers ----------
def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def ease_out_back(p):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def animate(widget, ms, step, done=None, ease=ease_out_cubic):
    start = time.perf_counter()

    def tick():
        p = min(1.0, (time.perf_counter() - start) * 1000 / ms)
        try:
            step(ease(p))
        except tk.TclError:
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


# ---------- custom button ----------
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, parent_bg, font, scheme="blue",
                 pad=PAD, square=None, radius=16, glow=6):
        self.text, self.command, self.font = text, command, font
        self.parent_bg, self.r, self.glow, self.drop = parent_bg, radius, glow, 3
        self.colors = BUTTON_STYLES[scheme]
        if square:
            self.w = self.h = square
        else:
            f = tkfont.Font(font=font)
            self.w = f.measure(text) + 2 * pad
            self.h = f.metrics("linespace") + int(pad * 1.2)
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
            self.after(70, self.command)

    def _rr(self, x1, y1, x2, y2, r, fill):
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, fill=fill, outline=fill)

    def _draw(self):
        self.delete("all")
        c, g, w, h = self.colors, self.glow, self.w, self.h
        glow_color = lerp(c["glow"], c["glow_hover"], self.hover)
        intensity = 0.12 if self.pressed else 0.25 + 0.45 * self.hover
        for k in range(g, 0, -1):
            closeness = 1 - (k - 1) / g
            col = lerp(self.parent_bg, glow_color, intensity * closeness ** 2 * 0.5)
            self._rr(g - k, g - k + self.drop, g + w + k, g + h + k + self.drop, self.r + k, col)
        body = c["press"] if self.pressed else lerp(c["base"], c["hover"], self.hover)
        inset = 1 if self.pressed else 0
        self._rr(g + inset, g + inset, g + w - inset, g + h - inset, self.r, body)
        self.create_text(g + w / 2, g + h / 2 + inset, text=self.text, fill=TEXT, font=self.font)


# ---------- popups ----------
class Dialog(tk.Toplevel):
    W, H = 520, 360

    def __init__(self, app, title):
        super().__init__(app, bg=BG)
        self._closing = False
        self.title(title)
        self.resizable(False, False)
        self.transient(app)
        app.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.W) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.H) // 2
        self.geometry(f"{self.W}x{self.H}{x:+d}{y:+d}")
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self.body = tk.Frame(self, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        self._place_body(0, 14)
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def present(self, focus_widget):
        self._focus = focus_widget
        focus_widget.focus_set()

        def step(p):
            try:
                self.attributes("-alpha", p)
            except tk.TclError:
                pass
            self._place_body(0, round(14 * (1 - p)))
        animate(self, 220, step)
        self.after(60, self._grab)

    def _place_body(self, dx, dy):
        self.body.place(x=24 + dx, y=24 + dy, relwidth=1, relheight=1, width=-48, height=-48)

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self._focus.focus_force()

    def shake(self):
        offsets = [-10, 10, -8, 8, -5, 5, -2, 2, 0]

        def step(i):
            if i >= len(offsets):
                return
            try:
                self._place_body(offsets[i], 0)
            except tk.TclError:
                return
            self.after(30, lambda: step(i + 1))
        step(0)

    def close(self):
        if self._closing:
            return
        self._closing = True

        def step(p):
            try:
                self.attributes("-alpha", 1 - p)
            except tk.TclError:
                pass
        animate(self, 120, step, done=self.destroy)


class TaskDialog(Dialog):
    def __init__(self, app, on_submit, mono):
        super().__init__(app, "New task")
        self.on_submit = on_submit
        
        container = tk.Frame(self.body, bg=SURFACE)
        container.pack(fill="both", expand=True, padx=32, pady=32)

        tk.Label(container, text="New task", font=(mono, 20, "bold"), bg=SURFACE,
                 fg=TEXT, anchor="w").pack(fill="x", pady=(0, 6))
        tk.Label(container, text="What needs doing?", font=(mono, 11), bg=SURFACE,
                 fg=MUTED, anchor="w").pack(fill="x", pady=(0, 20))
        
        self.entry = tk.Entry(container, font=(mono, 13), bg=SURFACE_2, fg=TEXT,
                              insertbackground=TEXT, relief="flat", bd=0,
                              highlightthickness=2, highlightbackground=BORDER,
                              highlightcolor=BLUE_HOVER)
        self.entry.pack(fill="x", pady=(0, 24), ipady=12)
        
        btn_frame = tk.Frame(container, bg=SURFACE)
        btn_frame.pack(fill="x", anchor="e")
        RoundedButton(btn_frame, "Submit", self.submit, SURFACE,
                      (mono, 11, "bold")).pack(side="right")
        
        self.entry.bind("<Return>", lambda e: self.submit())
        self.present(self.entry)

    def submit(self):
        text = self.entry.get().strip()
        if not text:
            self.entry.configure(highlightbackground=DANGER, highlightcolor=DANGER)
            self.after(450, self._reset_border)
            self.shake()
            return
        self.on_submit(text)
        self.close()

    def _reset_border(self):
        try:
            self.entry.configure(highlightbackground=BORDER, highlightcolor=BLUE_HOVER)
        except tk.TclError:
            pass


class ConfirmDialog(Dialog):
    H = 320

    def __init__(self, app, mono, message, confirm_text, on_confirm):
        super().__init__(app, "Are you sure?")
        self.on_confirm = on_confirm
        
        container = tk.Frame(self.body, bg=SURFACE)
        container.pack(fill="both", expand=True, padx=32, pady=32)

        buttons = tk.Frame(container, bg=SURFACE)
        buttons.pack(side="bottom", anchor="e", pady=(16, 0))
        RoundedButton(buttons, "Cancel", self.close, SURFACE,
                      (mono, 11, "bold")).pack(side="left", padx=(0, 12))
        RoundedButton(buttons, confirm_text, self.confirm, SURFACE,
                      (mono, 11, "bold"), scheme="danger").pack(side="left")

        tk.Label(container, text="Are you sure?", font=(mono, 20, "bold"), bg=SURFACE,
                 fg=TEXT, anchor="w").pack(fill="x", pady=(0, 12))
        tk.Label(container, text=message, font=(mono, 11), bg=SURFACE, fg=TEXT,
                 anchor="w", justify="left", wraplength=self.W - 104
                 ).pack(fill="x")
        tk.Label(container, text="This action cannot be undone.", font=(mono, 10), bg=SURFACE,
                 fg=MUTED, anchor="w").pack(fill="x", pady=(8, 0))
        self.present(self)

    def confirm(self):
        callback = self.on_confirm
        self.close()
        callback()


# ---------- main app ----------
class TodoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("To Do")
        self.geometry("860x800")
        self.minsize(700, 640)
        self.configure(bg=BG)

        self.tasks = []
        self.completed_open = True
        self._dialog = None
        self._flash_task = None
        self._pop_task = None
        self._intro = True
        self._clear_visible = False
        self.stat_vars = {k: tk.StringVar(value="0") for k in ("total", "active", "done")}
        self.stat_shown = {k: 0 for k in self.stat_vars}
        self.stat_token = {k: 0 for k in self.stat_vars}
        self._load()

        self.mono = pick_mono()
        self.f_title = (self.mono, 28, "bold")
        self.f_body = (self.mono, 12)
        self.f_small = (self.mono, 10)
        self.f_big = (self.mono, 28, "bold")
        self.f_done = tkfont.Font(family=self.mono, size=12, overstrike=True)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Blue.Horizontal.TProgressbar", troughcolor=SURFACE_2,
                        background=BLUE_HOVER, bordercolor=BG, lightcolor=BLUE_HOVER,
                        darkcolor=BLUE_HOVER, thickness=10)

        self._build()
        self.render()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def card(self, parent):
        return tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=BORDER)

    def _build(self):
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=40, pady=36)

        # Header
        head = tk.Frame(main, bg=BG)
        head.pack(fill="x")
        left = tk.Frame(head, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="To Do", font=self.f_title, bg=BG, fg=TEXT,
                 anchor="w").pack(fill="x")
        self.sub_lbl = tk.Label(left, font=self.f_body, bg=BG, fg=MUTED, anchor="w")
        self.sub_lbl.pack(fill="x", pady=(8, 0))
        RoundedButton(head, "+", self.open_task_dialog, BG, (self.mono, 20, "bold"),
                      square=48, radius=14).pack(side="right")

        # Stat cards
        row = tk.Frame(main, bg=BG)
        row.pack(fill="x", pady=(32, 0))
        for i, (key, name) in enumerate([("total", "Total tasks"), ("active", "Active"),
                                         ("done", "Completed")]):
            row.columnconfigure(i, weight=1, uniform="stats")
            c = self.card(row)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 16, 0))
            tk.Label(c, text=name, font=self.f_small, bg=SURFACE, fg=MUTED,
                     anchor="w").pack(fill="x", padx=24, pady=(20, 0))
            tk.Label(c, textvariable=self.stat_vars[key], font=self.f_big, bg=SURFACE,
                     fg=TEXT, anchor="w").pack(fill="x", padx=24, pady=(6, 20))

        self.progress = ttk.Progressbar(main, maximum=100, style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=32)

        # Footer
        self.footer = tk.Frame(main, bg=BG)
        self.footer.pack(side="bottom", fill="x")
        self.clear_btn = RoundedButton(self.footer, "Clear completed", self.ask_clear, BG,
                                       self.f_small, scheme="blue_to_maroon")

        # Scrollable list
        wrap = tk.Frame(main, bg=BG)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, highlightthickness=0, bd=0, bg=BG)
        self.canvas.pack(fill="both", expand=True)
        self.list_inner = tk.Frame(self.canvas, bg=BG)
        win = self.canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win, width=e.width))
        self.bind_all("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))
        self.bind_all("<Button-4>", lambda e: self._scroll(-1))
        self.bind_all("<Button-5>", lambda e: self._scroll(1))

    def _scroll(self, direction):
        try:
            if self.list_inner.winfo_height() > self.canvas.winfo_height():
                self.canvas.yview_scroll(direction, "units")
        except tk.TclError:
            pass

    def render(self):
        flash, pop = self._flash_task, self._pop_task
        self._flash_task = self._pop_task = None
        for child in self.list_inner.winfo_children():
            child.destroy()

        active = [t for t in self.tasks if not t["done"]]
        done = sorted((t for t in self.tasks if t["done"]),
                      key=lambda t: t["done_at"], reverse=True)

        if not self.tasks:
            empty_frame = tk.Frame(self.list_inner, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
            empty_frame.pack(fill="x", pady=20)
            tk.Label(empty_frame, text="Your list is empty.\nPress + to add your first task.",
                     font=self.f_body, bg=SURFACE, fg=MUTED, justify="center").pack(padx=30, pady=40)
        elif not active:
            tk.Label(self.list_inner, text="All tasks completed. Great job!", font=self.f_body, bg=BG,
                     fg=MUTED).pack(pady=(20, 10))
        for t in active:
            self._row(t, flash, pop)
        if done:
            self._accordion(len(done))
            if self.completed_open:
                for t in done:
                    self._row(t, flash, pop)

        total, n_done = len(self.tasks), len(done)
        self.sub_lbl.configure(text=f"{n_done} of {total} completed" if total
                               else "Ready when you are.")

        if done and not self._clear_visible:
            self.clear_btn.pack(side="right", pady=(24, 0))
            self._clear_visible = True
        elif not done and self._clear_visible:
            self.clear_btn.pack_forget()
            self._clear_visible = False

        ms = 1200 if self._intro else 350
        self._intro = False
        self._tween_stat("total", total, ms)
        self._tween_stat("active", len(active), ms)
        self._tween_stat("done", n_done, ms)
        target = (n_done / total * 100) if total else 0
        start = float(self.progress["value"])
        animate(self, ms, lambda p: self.progress.configure(value=start + (target - start) * p))

    def _tween_stat(self, key, target, ms):
        start = self.stat_shown[key]
        self.stat_token[key] += 1
        token = self.stat_token[key]

        def step(p):
            if token != self.stat_token[key]:
                return
            value = round(start + (target - start) * p)
            self.stat_shown[key] = value
            self.stat_vars[key].set(str(value))
        animate(self, ms, step)

    def _accordion(self, count):
        head = tk.Frame(self.list_inner, bg=BG, cursor="hand2")
        head.pack(fill="x", pady=(22, 16))
        arrow = "▾" if self.completed_open else "▸"
        lbl = tk.Label(head, text=f"{arrow}  Completed ({count})", font=self.f_small,
                       bg=BG, fg=MUTED, cursor="hand2")
        lbl.pack(side="left")
        line = tk.Frame(head, height=1, bg=BORDER)
        line.pack(side="left", fill="x", expand=True, padx=(16, 0))

        def toggle(e):
            self.completed_open = not self.completed_open
            self.render()

        def hover(inside):
            lbl.configure(fg=TEXT if inside else MUTED)
            line.configure(bg=BORDER_HOVER if inside else BORDER)

        for w in (head, lbl, line):
            w.bind("<Button-1>", toggle)
            w.bind("<Enter>", lambda e: hover(True))
            w.bind("<Leave>", lambda e: hover(False))

    def _row(self, task, flash, pop):
        row = tk.Frame(self.list_inner, bg=SURFACE, highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=BORDER)
        row.pack(fill="x", pady=(0, 12))

        box = tk.Canvas(row, width=30, height=30, highlightthickness=0, bd=0,
                        bg=SURFACE, cursor="hand2")
        box.pack(side="left", padx=(22, 0), pady=20)

        x = tk.Label(row, text="✕", font=self.f_small, bg=SURFACE, fg=MUTED, cursor="hand2")
        x.pack(side="right", padx=24)

        lbl = tk.Label(row, text=task["text"], anchor="w", justify="left", bg=SURFACE,
                       fg=MUTED if task["done"] else TEXT,
                       font=self.f_done if task["done"] else self.f_body)
        lbl.pack(side="left", fill="x", expand=True, padx=20)
        row.bind("<Configure>", lambda e: lbl.configure(wraplength=max(140, e.width - 150)))

        def draw(scale):
            box.delete("all")
            if task["done"]:
                r = 12 * scale
                box.create_oval(15 - r, 15 - r, 15 + r, 15 + r, fill=BLUE_HOVER, outline=BLUE_HOVER)
                if scale > 0.6:
                    box.create_text(15, 15, text="✓", fill=TEXT, font=(self.mono, 10, "bold"))
            else:
                box.create_oval(4, 4, 26, 26, outline=MUTED, width=2)

        draw(1)
        if pop is task and task["done"]:
            animate(box, 340, draw, ease=ease_out_back)

        for w in (box, lbl):
            w.bind("<Button-1>", lambda e: self.toggle(task))
        x.bind("<Button-1>", lambda e: self.ask_delete(task))
        x.bind("<Enter>", lambda e: x.configure(fg=DANGER))
        x.bind("<Leave>", lambda e: x.configure(fg=MUTED))

        widgets = [box, lbl, x]

        def on_enter(e):
            row.configure(bg=SURFACE_2, highlightbackground=BORDER_HOVER)
            for w in widgets:
                w.configure(bg=SURFACE_2)

        def on_leave(e):
            try:
                under = row.winfo_containing(*row.winfo_pointerxy())
            except (KeyError, tk.TclError):
                under = None
            if under is not None and (str(under) == str(row) or str(under).startswith(str(row) + ".")):
                return
            row.configure(bg=SURFACE, highlightbackground=BORDER)
            for w in widgets:
                w.configure(bg=SURFACE)

        for w in [row] + widgets:
            w.bind("<Enter>", on_enter, add="+")
            w.bind("<Leave>", on_leave, add="+")

        if flash is task:
            def step(p):
                c = lerp(BLUE, SURFACE, p)
                row.configure(bg=c)
                for w in widgets:
                    w.configure(bg=c)
            animate(row, 700, step)

    def _open(self, factory):
        if self._dialog is not None and self._dialog.winfo_exists():
            self._dialog.lift()
            return
        self._dialog = factory()

    def open_task_dialog(self):
        self._open(lambda: TaskDialog(self, self.add_task, self.mono))

    def ask_delete(self, task):
        self._open(lambda: ConfirmDialog(
            self, self.mono, f"Delete “{shorten(task['text'])}”?", "Delete",
            lambda: self.delete(task)))

    def ask_clear(self):
        n = sum(1 for t in self.tasks if t["done"])
        if n == 0:
            return
        self._open(lambda: ConfirmDialog(
            self, self.mono, f"Clear {n} completed task{'s' if n != 1 else ''}?", "Clear",
            self.clear_done))

    def add_task(self, text):
        task = {"text": text, "done": False, "done_at": 0.0}
        self.tasks.append(task)
        self._flash_task = task
        self._changed()

    def toggle(self, task):
        task["done"] = not task["done"]
        task["done_at"] = time.time() if task["done"] else 0.0
        self._pop_task = task
        self._changed()

    def delete(self, task):
        self.tasks = [t for t in self.tasks if t is not task]
        self._changed()

    def clear_done(self):
        self.tasks = [t for t in self.tasks if not t["done"]]
        self._changed()

    def _changed(self):
        self._save()
        self.render()

    def _load(self):
        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
            self.tasks = [{"text": str(t["text"]), "done": bool(t["done"]),
                           "done_at": float(t.get("done_at", 0))}
                          for t in data.get("tasks", [])]
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def _save(self):
        try:
            SAVE_FILE.write_text(json.dumps({"tasks": self.tasks}, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _on_close(self):
        self._save()
        self.destroy()


if __name__ == "__main__":
    TodoApp().mainloop()