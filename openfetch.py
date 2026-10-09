import os
import sys
import re
import threading
import time
import mimetypes
import queue
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog
from urllib.parse import urlparse, unquote
import requests

APP_NAME = "OpenFetch"
APP_VERSION = "0.4"

BG = "#0b1020"
CARD = "#141b2d"
FIELD = "#202a42"
TEXT = "#f6f8fc"
MUTED = "#9ca9c3"
ACCENT = "#6f8cff"
GREEN = "#35d08a"
RED = "#ff6b7a"
BORDER = "#24304a"

_PROBE_CACHE = {}
_PROBE_CACHE_LOCK = threading.Lock()
_PROBE_CACHE_TTL = 60


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def default_download_dir():
    path = os.path.join(os.path.expanduser("~"), "Downloads", "OpenFetch")
    os.makedirs(path, exist_ok=True)
    return path


def human_size(value):
    if value is None:
        return "Unknown"
    value = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024


def clean_filename(name):
    name = unquote(name or "").strip().strip('"')
    name = re.sub(r'[<>:"/\\|?*]+', "_", name)
    return name[:180] or "download.bin"


def parse_filename(headers, url):
    content_disposition = headers.get("content-disposition", "")
    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.I)
    if match:
        return clean_filename(match.group(1))
    match = re.search(r'filename="?([^";]+)"?', content_disposition, re.I)
    if match:
        return clean_filename(match.group(1))
    path = urlparse(url).path
    return clean_filename(os.path.basename(path.rstrip("/")) or "download.bin")


def probe_url(url):
    now = time.time()
    with _PROBE_CACHE_LOCK:
        cached = _PROBE_CACHE.get(url)
        if cached and now - cached[0] < _PROBE_CACHE_TTL:
            return dict(cached[1])
    headers = {"User-Agent": "Mozilla/5.0 OpenFetch/0.4", "Accept-Encoding": "identity", "Range": "bytes=0-0"}
    response = None
    try:
        response = requests.get(url, allow_redirects=True, timeout=(2.5, 4.0), stream=True, headers=headers)
        if response.status_code == 416:
            response.close()
            fallback = {"User-Agent": "Mozilla/5.0 OpenFetch/0.4", "Accept-Encoding": "identity"}
            response = requests.head(url, allow_redirects=True, timeout=(2.5, 4.0), headers=fallback)
        response.raise_for_status()
        final_url = response.url
        content_range = response.headers.get("content-range", "")
        m = re.search(r"/(\d+)$", content_range)
        if m: size = int(m.group(1))
        else:
            raw = response.headers.get("content-length"); size = int(raw) if raw and raw.isdigit() else None
        name = parse_filename(response.headers, final_url)
        content_type = response.headers.get("content-type", "").split(";")[0].strip() or mimetypes.guess_type(name)[0] or "Unknown"
        result = {"url": final_url, "name": name, "size": size, "type": content_type, "server": urlparse(final_url).netloc, "ranges": response.status_code == 206 or "bytes" in response.headers.get("accept-ranges", "").lower()}
        with _PROBE_CACHE_LOCK:
            _PROBE_CACHE[url] = (time.time(), dict(result))
            if len(_PROBE_CACHE) > 32:
                oldest = min(_PROBE_CACHE, key=lambda k: _PROBE_CACHE[k][0]); _PROBE_CACHE.pop(oldest, None)
        return result
    finally:
        if response is not None:
            try: response.close()
            except Exception: pass


class DownloadItem:
    def __init__(self, app, info, save_dir, queued=False):
        self.app = app
        self.info = info
        self.save_dir = save_dir
        self.status = "Queued" if queued else "Ready"
        self.downloaded = 0
        self.total = info.get("size")
        self.speed = 0
        self.pause_event = threading.Event()
        self.worker = None
        self.frame = None
        self.progress = None
        self.status_lbl = None
        self.detail_lbl = None
        self.action_btn = None
        self.folder_btn = None
        self.build()

    @property
    def path(self):
        return os.path.join(self.save_dir, self.info["name"])

    def build(self):
        frame = tk.Frame(
            self.app.list_inner,
            bg=CARD,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        frame.pack(fill="x", pady=(0, 6))
        self.frame = frame

        top = tk.Frame(frame, bg=CARD)
        top.pack(fill="x", padx=10, pady=(8, 2))

        name_lbl = tk.Label(
            top,
            text=self.info["name"],
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
            anchor="w",
        )
        name_lbl.pack(side="left", fill="x", expand=True)

        self.status_lbl = tk.Label(
            top,
            text=self.status,
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 8),
        )
        self.status_lbl.pack(side="right")

        self.progress = ttk.Progressbar(frame, maximum=100, style="IDM.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=10, pady=(2, 3))

        self.detail_lbl = tk.Label(
            frame,
            text=self.detail_text(),
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.detail_lbl.pack(fill="x", padx=10)

        actions = tk.Frame(frame, bg=CARD)
        actions.pack(fill="x", padx=10, pady=(5, 7))

        self.folder_btn = tk.Button(
            actions,
            text="Open Folder",
            command=lambda: os.startfile(self.save_dir),
            bg=FIELD,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 8),
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.folder_btn.pack(side="left")

        self.action_btn = tk.Button(
            actions,
            text="Start" if self.status == "Queued" else "Start",
            command=self.start,
            bg=ACCENT,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 8),
            padx=12,
            pady=3,
            cursor="hand2",
        )
        self.action_btn.pack(side="right")
        self.refresh_existing_progress()

    def refresh_existing_progress(self):
        final_size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
        single_part = self.path + ".part"
        part_size = os.path.getsize(single_part) if os.path.exists(single_part) else 0
        segment_total = 0
        for i in range(8):
            p = self.path + f".part{i}"
            if os.path.exists(p):
                segment_total += os.path.getsize(p)
        self.downloaded = max(final_size, part_size, segment_total)
        if self.total and self.downloaded:
            self.progress["value"] = min(100, self.downloaded * 100 / self.total)
        self.detail_lbl.config(text=self.detail_text())

    def detail_text(self):
        total_text = human_size(self.total)
        if self.status in ("Downloading", "Starting...", "Pausing...") and self.speed > 0:
            return f"{human_size(self.downloaded)} / {total_text}   •   {human_size(self.speed)}/s"
        if self.status == "Completed":
            return f"{human_size(self.downloaded)} • Saved to {self.save_dir}"
        return f"{human_size(self.downloaded)} / {total_text}"

    def _status_color(self, status):
        if status == "Completed":
            return GREEN
        if status == "Failed":
            return RED
        if status in ("Paused", "Queued"):
            return ACCENT
        return MUTED

    def set_ui(self, status=None, progress=None, detail=None):
        def apply():
            if status is not None:
                self.status = status
                self.status_lbl.config(text=status, fg=self._status_color(status))
            if progress is not None:
                self.progress["value"] = max(0, min(100, progress))
            self.detail_lbl.config(text=detail or self.detail_text())
            self._sync_buttons()

        self.app.post_ui(apply)

    def _sync_buttons(self):
        status = self.status
        self.action_btn.config(state="normal", bg=ACCENT, fg=TEXT, activebackground=BORDER)
        if status in ("Queued", "Ready"):
            self.action_btn.config(text="Start", command=self.start)
        elif status in ("Starting...", "Downloading"):
            self.action_btn.config(text="Pause", command=self.pause)
        elif status == "Pausing...":
            self.action_btn.config(text="Pausing...", state="disabled")
        elif status == "Paused":
            self.action_btn.config(text="Resume", command=self.start, bg=GREEN, fg=BG)
        elif status == "Failed":
            self.action_btn.config(text="Retry", command=self.start, bg=ACCENT, fg=TEXT)
        elif status == "Completed":
            self.action_btn.config(text="Open File", command=self.open_file, bg=GREEN, fg=BG)

    def open_file(self):
        if os.path.exists(self.path):
            os.startfile(self.path)
        else:
            os.startfile(self.save_dir)

    def pause(self):
        if self.status not in ("Starting...", "Downloading"):
            return
        self.pause_event.set()
        self.set_ui("Pausing...")

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        os.makedirs(self.save_dir, exist_ok=True)
        self.pause_event.clear()
        self.refresh_existing_progress()
        self.set_ui("Starting...")
        self.worker = threading.Thread(target=self._download_worker, daemon=True)
        self.worker.start()

    def _download_worker(self):
        try:
            total = self.info.get("size")
            if total and self.info.get("ranges") and total > 8 * 1024 * 1024:
                completed = self._segmented(self.info["url"], total, 8)
            else:
                completed = self._single(self.info["url"], total)

            if self.pause_event.is_set():
                self.set_ui("Paused")
                return

            if completed:
                self.downloaded = os.path.getsize(self.path) if os.path.exists(self.path) else self.downloaded
                self.set_ui("Completed", 100)
        except Exception as exc:
            if self.pause_event.is_set():
                self.set_ui("Paused")
            else:
                self.set_ui("Failed", detail=str(exc)[:96])

    def _single(self, url, total):
        headers = {"User-Agent": "Mozilla/5.0 OpenFetch/0.4", "Accept-Encoding": "identity"}
        tmp = self.path + ".part"
        existing = os.path.getsize(tmp) if os.path.exists(tmp) else 0

        if existing:
            headers["Range"] = f"bytes={existing}-"

        with requests.get(url, stream=True, timeout=30, headers=headers) as response:
            if existing and response.status_code != 206:
                raise RuntimeError("Server does not support resume for this download.")
            response.raise_for_status()

            if total is None:
                if response.status_code == 206:
                    content_range = response.headers.get("content-range", "")
                    match = re.search(r"/(\d+)$", content_range)
                    if match:
                        total = int(match.group(1))
                if total is None:
                    length = response.headers.get("content-length")
                    if length and length.isdigit():
                        total = existing + int(length)
                self.total = total

            self.downloaded = existing
            last_t = time.time()
            last_b = self.downloaded
            mode = "ab" if existing else "wb"

            with open(tmp, mode) as file_obj:
                for chunk in response.iter_content(1024 * 512):
                    if self.pause_event.is_set():
                        file_obj.flush()
                        return False
                    if not chunk:
                        continue
                    file_obj.write(chunk)
                    self.downloaded += len(chunk)
                    now = time.time()
                    if now - last_t >= 0.35:
                        self.speed = (self.downloaded - last_b) / (now - last_t)
                        last_t = now
                        last_b = self.downloaded
                        percent = self.downloaded * 100 / total if total else 0
                        self.set_ui("Downloading", percent)

        os.replace(tmp, self.path)
        return True

    def _segmented(self, url, total, segments):
        self.total = total
        part_paths = [self.path + f".part{i}" for i in range(segments)]
        lock = threading.Lock()
        errors = []
        span = total // segments
        bounds = []

        for i in range(segments):
            start = i * span
            end = total - 1 if i == segments - 1 else start + span - 1
            bounds.append((start, end))

        progress = []
        for i, (start, end) in enumerate(bounds):
            expected = end - start + 1
            existing = os.path.getsize(part_paths[i]) if os.path.exists(part_paths[i]) else 0
            if existing > expected:
                with open(part_paths[i], "rb+") as file_obj:
                    file_obj.truncate(expected)
                existing = expected
            progress.append(existing)

        self.downloaded = sum(progress)
        if self.total:
            self.set_ui("Downloading", self.downloaded * 100 / self.total)

        def worker(index, start, end):
            expected = end - start + 1
            existing = progress[index]
            if existing >= expected:
                return
            request_start = start + existing
            headers = {
                "User-Agent": "Mozilla/5.0 OpenFetch/0.4",
                "Accept-Encoding": "identity",
                "Range": f"bytes={request_start}-{end}",
            }
            try:
                with requests.get(url, stream=True, timeout=30, headers=headers) as response:
                    if response.status_code != 206:
                        raise RuntimeError("Server rejected range resume.")
                    with open(part_paths[index], "ab") as file_obj:
                        for chunk in response.iter_content(1024 * 512):
                            if self.pause_event.is_set():
                                file_obj.flush()
                                return
                            if not chunk:
                                continue
                            file_obj.write(chunk)
                            with lock:
                                progress[index] += len(chunk)
            except Exception as exc:
                if not self.pause_event.is_set():
                    errors.append(exc)

        threads = []
        for i, (start, end) in enumerate(bounds):
            thread = threading.Thread(target=worker, args=(i, start, end), daemon=True)
            threads.append(thread)
            thread.start()

        last_t = time.time()
        last_b = self.downloaded
        while any(thread.is_alive() for thread in threads):
            time.sleep(0.20)
            with lock:
                done = sum(progress)
            now = time.time()
            if now - last_t >= 0.35:
                self.speed = (done - last_b) / (now - last_t)
                last_t = now
                last_b = done
                self.downloaded = done
                self.set_ui("Downloading", done * 100 / total)

        for thread in threads:
            thread.join()

        self.downloaded = sum(progress)

        if self.pause_event.is_set():
            return False

        if errors:
            raise errors[0]

        for i, (start, end) in enumerate(bounds):
            expected = end - start + 1
            if not os.path.exists(part_paths[i]) or os.path.getsize(part_paths[i]) != expected:
                raise RuntimeError("One or more download segments are incomplete.")

        with open(self.path, "wb") as output:
            for path in part_paths:
                with open(path, "rb") as source:
                    while True:
                        data = source.read(1024 * 1024)
                        if not data:
                            break
                        output.write(data)

        for path in part_paths:
            try:
                os.remove(path)
            except Exception:
                pass
        return True


class NewDownloadDialog(tk.Toplevel):
    def __init__(self, app, url):
        super().__init__(app)
        self.app = app
        self.url = url
        self.info = None
        self.save_dir = tk.StringVar(value=default_download_dir())
        self._drag = None
        self._closed = False

        self.geometry("460x330")
        self.resizable(False, False)
        self.configure(bg=BORDER)
        self.transient(app)
        self.overrideredirect(True)
        try:
            self.iconbitmap(os.path.join(app_dir(), "IDM.ico"))
        except Exception:
            pass

        self._build()
        self.update_idletasks()
        self._center_over_parent()
        self.lift()
        self.focus_force()
        self.bind("<Escape>", lambda _e: self.close_dialog())
        threading.Thread(target=self._probe, daemon=True, name="IDM-Probe").start()

    def _center_over_parent(self):
        x = self.app.winfo_rootx() + max(0, (self.app.winfo_width() - self.winfo_width()) // 2)
        y = self.app.winfo_rooty() + max(0, (self.app.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def _build(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        title = tk.Frame(outer, bg=BG, height=42)
        title.pack(fill="x")
        title.pack_propagate(False)

        icon_path = os.path.join(app_dir(), "IDM_header.png")
        if os.path.exists(icon_path):
            try:
                original = tk.PhotoImage(file=icon_path)
                factor = max(1, original.width() // 24)
                self.dialog_icon = original.subsample(factor, factor)
                tk.Label(title, image=self.dialog_icon, bg=BG, bd=0).place(x=12, y=9)
            except Exception:
                pass

        tk.Label(
            title,
            text="New Download",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 11),
        ).place(x=46, y=10)

        close_btn = tk.Button(
            title,
            text="×",
            command=self.close_dialog,
            bg=FIELD,
            fg=TEXT,
            activebackground=RED,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 12),
            cursor="hand2",
        )
        close_btn.place(relx=1.0, x=-10, y=7, width=30, height=28, anchor="ne")

        title.bind("<ButtonPress-1>", self._start_move)
        title.bind("<B1-Motion>", self._do_move)

        content = tk.Frame(outer, bg=BG)
        content.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        card = tk.Frame(content, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True)

        self.file_lbl = tk.Label(
            card,
            text="Checking link...",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI Semibold", 10),
            anchor="w",
        )
        self.file_lbl.pack(fill="x", padx=14, pady=(14, 4))

        self.size_lbl = tk.Label(
            card,
            text="File size: —",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.size_lbl.pack(fill="x", padx=14)

        self.meta_lbl = tk.Label(
            card,
            text="Server: —\nType: —",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 8),
            justify="left",
            anchor="w",
        )
        self.meta_lbl.pack(fill="x", padx=14, pady=(5, 10))

        tk.Label(
            card,
            text="Save to",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack(anchor="w", padx=14)

        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=14, pady=(4, 10))

        tk.Entry(
            row,
            textvariable=self.save_dir,
            bg=FIELD,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 8),
        ).pack(side="left", fill="x", expand=True, ipady=5)

        tk.Button(
            row,
            text="Browse",
            command=self.browse,
            bg=FIELD,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 8),
            padx=9,
            pady=4,
            cursor="hand2",
        ).pack(side="left", padx=(7, 0))

        buttons = tk.Frame(card, bg=CARD)
        buttons.pack(fill="x", padx=14, pady=(4, 12))

        tk.Button(
            buttons,
            text="Cancel",
            command=self.close_dialog,
            bg=FIELD,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 8),
            width=10,
            pady=5,
            cursor="hand2",
        ).pack(side="left")

        self.later = tk.Button(
            buttons,
            text="Download Later",
            command=self.download_later,
            state="disabled",
            bg=ACCENT,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            disabledforeground=MUTED,
            relief="flat",
            bd=0,
            font=("Segoe UI", 8),
            width=14,
            pady=5,
            cursor="hand2",
        )
        self.later.pack(side="right", padx=(6, 0))

        self.start = tk.Button(
            buttons,
            text="Start Download",
            command=self.start_now,
            state="disabled",
            bg=GREEN,
            fg=BG,
            activebackground=ACCENT,
            activeforeground=TEXT,
            disabledforeground=MUTED,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 8),
            width=14,
            pady=5,
            cursor="hand2",
        )
        self.start.pack(side="right")

    def _start_move(self, event):
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _do_move(self, event):
        if self._drag:
            self.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    def browse(self):
        path = filedialog.askdirectory(initialdir=self.save_dir.get(), parent=self)
        if path:
            self.save_dir.set(path)

    def _probe(self):
        try:
            info = probe_url(self.url)

            def done():
                if self._closed:
                    return
                try:
                    if not self.winfo_exists():
                        return
                except tk.TclError:
                    return
                self.info = info
                self.file_lbl.config(text=info["name"])
                self.size_lbl.config(text=f"File size: {human_size(info['size'])}")
                self.meta_lbl.config(text=f"Server: {info['server']}\nType: {info['type']}")
                self.start.config(state="normal")
                self.later.config(state="normal")

            self.app.post_ui(done)
        except Exception as exc:
            message = str(exc)[:65]
            parsed = urlparse(self.url)
            fallback_name = clean_filename(os.path.basename(parsed.path.rstrip("/")) or "download.bin")
            fallback_type = mimetypes.guess_type(fallback_name)[0] or "Unknown"
            fallback = {"url": self.url, "name": fallback_name, "size": None, "type": fallback_type, "server": parsed.netloc, "ranges": False}

            def failed():
                if self._closed:
                    return
                try:
                    if not self.winfo_exists():
                        return
                except tk.TclError:
                    return
                self.info = fallback
                self.file_lbl.config(text=fallback_name)
                self.size_lbl.config(text="File size: Unknown")
                self.meta_lbl.config(text=f"Server: {fallback['server']}\nType: {fallback_type}\nMetadata unavailable — download can still start")
                self.start.config(state="normal")
                self.later.config(state="normal")

            self.app.post_ui(failed)

    def close_dialog(self):
        if self._closed:
            return
        self._closed = True
        if getattr(self.app, "active_dialog", None) is self:
            self.app.active_dialog = None
        try:
            self.destroy()
        except tk.TclError:
            pass

    def start_now(self):
        if not self.info or self._closed:
            return
        item = self.app.add_item(self.info, self.save_dir.get(), queued=False)
        self.close_dialog()
        item.start()

    def download_later(self):
        if not self.info or self._closed:
            return
        self.app.add_item(self.info, self.save_dir.get(), queued=True)
        self.close_dialog()


class IDMApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("500x515")
        self.resizable(False, False)
        self.overrideredirect(True)
        self.configure(bg=BG)
        try:
            self.iconbitmap(os.path.join(app_dir(), "IDM.ico"))
        except Exception:
            pass
        self.url = tk.StringVar()
        self._drag = None
        self.empty = None
        self.active_dialog = None
        self._closing = False
        self.ui_queue = queue.Queue()
        self.build_ui()
        self.after(30, self._drain_ui_queue)

    def post_ui(self, callback):
        if not self._closing:
            self.ui_queue.put(callback)

    def _drain_ui_queue(self):
        if self._closing:
            return
        processed = 0
        try:
            while processed < 40:
                callback = self.ui_queue.get_nowait()
                try:
                    callback()
                except tk.TclError:
                    pass
                except Exception:
                    pass
                processed += 1
        except queue.Empty:
            pass
        try:
            self.after(15 if not self.ui_queue.empty() else 40, self._drain_ui_queue)
        except tk.TclError:
            pass

    def close_app(self):
        self._closing = True
        try:
            if self.active_dialog and self.active_dialog.winfo_exists():
                self.active_dialog.destroy()
        except tk.TclError:
            pass
        self.destroy()

    def minimize_window(self):
        self.overrideredirect(False)
        self.iconify()

    def restore_borderless(self, _event=None):
        if self.state() == "normal":
            self.after(20, lambda: self.overrideredirect(True))

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "IDM.Horizontal.TProgressbar",
            troughcolor=FIELD,
            background=ACCENT,
            bordercolor=FIELD,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            borderwidth=0,
        )
        style.configure(
            "IDM.Vertical.TScrollbar",
            troughcolor=CARD,
            background=FIELD,
            bordercolor=CARD,
            lightcolor=FIELD,
            darkcolor=FIELD,
            arrowcolor=TEXT,
            relief="flat",
            width=11,
        )
        style.map(
            "IDM.Vertical.TScrollbar",
            background=[("active", ACCENT), ("pressed", GREEN)],
            arrowcolor=[("active", TEXT)],
        )

        self.build_titlebar()

        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        card = tk.Frame(shell, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True, pady=(8, 0))

        tk.Label(
            card,
            text="Paste download link",
            font=("Segoe UI Semibold", 9),
            fg=TEXT,
            bg=CARD,
        ).pack(anchor="w", padx=14, pady=(11, 4))

        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=14)

        self.entry = tk.Entry(
            row,
            textvariable=self.url,
            font=("Segoe UI", 9),
            bg=FIELD,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", lambda _event: self.add_link())

        tk.Button(
            row,
            text="Paste",
            command=self.paste,
            bg=ACCENT,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=6,
            cursor="hand2",
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            card,
            text="Add Download",
            command=self.add_link,
            bg=GREEN,
            fg=BG,
            activebackground=ACCENT,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 9),
            pady=6,
            cursor="hand2",
        ).pack(fill="x", padx=14, pady=(8, 9))

        title = tk.Frame(card, bg=CARD)
        title.pack(fill="x", padx=14, pady=(0, 5))

        tk.Label(
            title,
            text="Downloads",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")

        tk.Label(
            title,
            text="8 connections when supported",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 7),
        ).pack(side="right")

        footer = tk.Frame(card, bg=CARD)
        footer.pack(side="bottom", fill="x", padx=14, pady=(4, 9))

        tk.Button(
            footer,
            text="Open Download Folder",
            command=lambda: os.startfile(default_download_dir()),
            bg=FIELD,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 8),
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side="left")

        wrap = tk.Frame(card, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 4))

        self.canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(
            wrap,
            orient="vertical",
            command=self.canvas.yview,
            style="IDM.Vertical.TScrollbar",
        )
        self.list_inner = tk.Frame(self.canvas, bg=CARD)
        self.window_id = self.canvas.create_window((0, 0), window=self.list_inner, anchor="nw")

        self.list_inner.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_list_width)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Enter>", lambda _e: self.bind_all("<MouseWheel>", self._mousewheel))
        self.canvas.bind("<Leave>", lambda _e: self.unbind_all("<MouseWheel>"))

        self.empty = tk.Label(
            self.list_inner,
            text="No downloads yet",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
        )
        self.empty.pack(pady=38)

    def _sync_scroll_region(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_list_width(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def build_titlebar(self):
        bar = tk.Frame(self, bg=BG, height=62)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        logo = os.path.join(app_dir(), "IDM_header.png")
        if os.path.exists(logo):
            try:
                self.logo = tk.PhotoImage(file=logo)
                tk.Label(bar, image=self.logo, bg=BG, bd=0).place(x=12, y=6, width=50, height=50)
            except Exception:
                pass

        tk.Label(
            bar,
            text="OpenFetch",
            font=("Segoe UI Semibold", 14),
            fg=TEXT,
            bg=BG,
        ).place(x=72, y=12)

        tk.Label(
            bar,
            text="Fast Download Manager",
            font=("Segoe UI", 8),
            fg=MUTED,
            bg=BG,
        ).place(x=74, y=37)

        min_btn = tk.Button(
            bar,
            text="−",
            command=self.minimize_window,
            bg=FIELD,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 13),
            cursor="hand2",
        )
        min_btn.place(relx=1, x=-88, y=14, width=34, height=30, anchor="ne")

        close_btn = tk.Button(
            bar,
            text="×",
            command=self.close_app,
            bg=FIELD,
            fg=TEXT,
            activebackground=RED,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 13),
            cursor="hand2",
        )
        close_btn.place(relx=1, x=-46, y=14, width=34, height=30, anchor="ne")

        bar.bind("<ButtonPress-1>", self.start_move)
        bar.bind("<B1-Motion>", self.do_move)
        self.bind("<Map>", self.restore_borderless)

    def start_move(self, event):
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def do_move(self, event):
        if self._drag:
            self.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    def paste(self):
        try:
            self.url.set(self.clipboard_get().strip())
        except Exception:
            pass

    def add_link(self):
        url = self.url.get().strip()
        if not url.lower().startswith(("http://", "https://")):
            self.entry.focus_set()
            return
        try:
            if self.active_dialog and self.active_dialog.winfo_exists():
                self.active_dialog.lift()
                self.active_dialog.focus_force()
                return
        except tk.TclError:
            self.active_dialog = None
        self.active_dialog = NewDownloadDialog(self, url)

    def add_item(self, info, save_dir, queued=False):
        if self.empty and self.empty.winfo_exists():
            self.empty.destroy()
            self.empty = None
        item = DownloadItem(self, info, save_dir, queued)
        self.url.set("")
        self.after(10, self._sync_scroll_region)
        return item


_INSTANCE_MUTEX = None

def ensure_single_instance():
    global _INSTANCE_MUTEX
    if os.name != "nt":
        return True
    kernel32 = ctypes.windll.kernel32
    _INSTANCE_MUTEX = kernel32.CreateMutexW(
        None, False, "Local\\IDM_FastDownloadManager_v03"
    )
    if not _INSTANCE_MUTEX:
        return True
    return kernel32.GetLastError() != 183

if __name__ == "__main__":
    if ensure_single_instance():
        IDMApp().mainloop()
