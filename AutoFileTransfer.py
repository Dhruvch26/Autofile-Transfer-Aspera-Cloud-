import os
import time
import subprocess
import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import datetime

# ================================================================
# CONFIGURATION
# ================================================================
KEEP_EXTENSIONS  = {".zip"}
ASCLI_CMD        = r"C:\Ruby34-x64\bin\ascli"
ASPERA_URL       = "https://your-aspera-server.com"
ASPERA_BASE      = "YOUR-BASE-PATH"
LOGO_PATH        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

# Colors
BG_DARK          = "#0A0A0A"
BG_PANEL         = "#141414"
BG_INPUT         = "#1E1E1E"
ACCENT           = "#2563EB"
ACCENT_HOVER     = "#1D4ED8"
TEXT_PRIMARY     = "#FFFFFF"
TEXT_SECONDARY   = "#A0A0A0"
TEXT_SUCCESS     = "#4CAF50"
TEXT_ERROR       = "#FF5252"
TEXT_INFO        = "#64B5F6"
BORDER           = "#2A2A2A"
# ================================================================


class AutoFileTransferApp:
    def __init__(self, root):
        self.root            = root
        self.observer        = None
        self.is_running      = False
        self.username        = ""
        self.password        = ""
        self.watch_folder    = ""
        self.aspera_folder   = ""
        self.log_file        = ""
        self.processing      = set()
        self.processing_lock = threading.Lock()

        self.root.title("AutoFile Transfer — Aspera")
        self.root.geometry("900x620")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth()  // 2) - 450
        y = (self.root.winfo_screenheight() // 2) - 310
        self.root.geometry(f"900x620+{x}+{y}")

        self.setup_styles()
        self.build_header()
        self.container = tk.Frame(self.root, bg=BG_DARK)
        self.container.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        self.show_login_screen()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TEntry",
            fieldbackground=BG_INPUT,
            background=BG_INPUT,
            foreground=TEXT_PRIMARY,
            insertcolor=TEXT_PRIMARY,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            relief="flat",
            padding=8
        )

    def build_header(self):
        header = tk.Frame(self.root, bg=BG_PANEL, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        try:
            img = Image.open(LOGO_PATH)
            img = img.resize((120, 40), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
            tk.Label(header, image=self.logo_img,
                     bg=BG_PANEL).pack(side="left", padx=20, pady=15)
        except Exception:
            tk.Label(header, text="AFT", bg=BG_PANEL,
                     fg=ACCENT, font=("Segoe UI", 18, "bold")).pack(
                side="left", padx=20, pady=15)

        title_frame = tk.Frame(header, bg=BG_PANEL)
        title_frame.pack(side="left", padx=10)
        tk.Label(title_frame, text="AutoFile Transfer",
                 bg=BG_PANEL, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(title_frame, text="Aspera Automated Upload System",
                 bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(anchor="w")

        self.status_dot = tk.Label(header, text="●", bg=BG_PANEL,
                                   fg=TEXT_SECONDARY, font=("Segoe UI", 12))
        self.status_dot.pack(side="right", padx=8)
        self.status_lbl = tk.Label(header, text="Idle",
                                   bg=BG_PANEL, fg=TEXT_SECONDARY,
                                   font=("Segoe UI", 9))
        self.status_lbl.pack(side="right")

        tk.Frame(self.root, bg=ACCENT, height=2).pack(fill="x")

    def set_status(self, text, color=TEXT_SECONDARY):
        self.status_dot.config(fg=color)
        self.status_lbl.config(text=text, fg=color)

    def clear_container(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_login_screen(self):
        self.clear_container()
        self.set_status("Idle", TEXT_SECONDARY)

        tk.Label(self.container, text="Welcome to AutoFile Transfer",
                 bg=BG_DARK, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 20, "bold")).pack(pady=(30, 4))
        tk.Label(self.container,
                 text="Sign in with your IBM Aspera credentials to begin automated file uploads.",
                 bg=BG_DARK, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 10)).pack(pady=(0, 30))

        card = tk.Frame(self.container, bg=BG_PANEL,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(ipadx=40, ipady=30)

        tk.Label(card, text="Sign In", bg=BG_PANEL, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 14, "bold")).pack(pady=(20, 20))

        tk.Label(card, text="Username", bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=40)
        self.user_var = tk.StringVar()
        user_entry = tk.Entry(card, textvariable=self.user_var,
                              bg=BG_INPUT, fg=TEXT_PRIMARY,
                              insertbackground=TEXT_PRIMARY,
                              relief="flat", font=("Segoe UI", 11), width=32)
        user_entry.pack(padx=40, pady=(4, 14), ipady=8)
        user_entry.focus()

        tk.Label(card, text="Password", bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=40)
        self.pass_var = tk.StringVar()
        pass_entry = tk.Entry(card, textvariable=self.pass_var,
                              show="●", bg=BG_INPUT, fg=TEXT_PRIMARY,
                              insertbackground=TEXT_PRIMARY,
                              relief="flat", font=("Segoe UI", 11), width=32)
        pass_entry.pack(padx=40, pady=(4, 24), ipady=8)
        pass_entry.bind("<Return>", lambda e: self.do_login())

        self.login_error = tk.Label(card, text="", bg=BG_PANEL,
                                    fg=TEXT_ERROR, font=("Segoe UI", 9))
        self.login_error.pack()

        self.login_btn = tk.Button(card, text="LOGIN",
                                   bg=ACCENT, fg=TEXT_PRIMARY,
                                   font=("Segoe UI", 11, "bold"),
                                   relief="flat", cursor="hand2",
                                   width=28, pady=10,
                                   command=self.do_login)
        self.login_btn.pack(padx=40, pady=(8, 24))
        self.login_btn.bind("<Enter>",
                            lambda e: self.login_btn.config(bg=ACCENT_HOVER))
        self.login_btn.bind("<Leave>",
                            lambda e: self.login_btn.config(bg=ACCENT))

        tk.Label(card,
                 text="Credentials are used only for this session and never stored.",
                 bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 8)).pack(pady=(0, 16))

    def do_login(self):
        u = self.user_var.get().strip()
        p = self.pass_var.get().strip()
        if not u or not p:
            self.login_error.config(text="Please enter username and password.")
            return
        self.login_btn.config(text="Signing in...", state="disabled")
        self.root.update()
        self.username = u
        self.password = p
        self.show_config_screen()

    def show_config_screen(self):
        self.clear_container()
        self.set_status("Configuring...", TEXT_INFO)

        tk.Label(self.container, text="Configure Transfer Settings",
                 bg=BG_DARK, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 18, "bold")).pack(pady=(25, 4))
        tk.Label(self.container,
                 text="Select your local watch folder and Aspera destination path.",
                 bg=BG_DARK, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 10)).pack(pady=(0, 20))

        card = tk.Frame(self.container, bg=BG_PANEL,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", ipadx=20, ipady=10)

        inner = tk.Frame(card, bg=BG_PANEL)
        inner.pack(padx=40, pady=20, fill="x")

        tk.Label(inner, text="Local Watch Folder",
                 bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text="ZIP files will be automatically detected and uploaded from this folder.",
                 bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 6))

        folder_row = tk.Frame(inner, bg=BG_PANEL)
        folder_row.pack(fill="x", pady=(0, 20))

        self.folder_var = tk.StringVar(value=os.path.join(
            os.path.expanduser("~"), "Downloads", "Watchfolder"))
        tk.Entry(folder_row, textvariable=self.folder_var,
                 bg=BG_INPUT, fg=TEXT_PRIMARY,
                 insertbackground=TEXT_PRIMARY,
                 relief="flat", font=("Segoe UI", 10),
                 width=50).pack(side="left", ipady=8, padx=(0, 10))

        browse_btn = tk.Button(folder_row, text="Browse",
                               bg=BG_INPUT, fg=TEXT_PRIMARY,
                               font=("Segoe UI", 9), relief="flat",
                               cursor="hand2", padx=16, pady=8,
                               command=self.browse_folder)
        browse_btn.pack(side="left")
        browse_btn.bind("<Enter>", lambda e: browse_btn.config(bg=BORDER))
        browse_btn.bind("<Leave>", lambda e: browse_btn.config(bg=BG_INPUT))

        tk.Label(inner, text="Aspera Destination Path",
                 bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(inner,
                 text="Enter your Aspera base path and sub-path below.",
                 bg=BG_PANEL, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 6))

        path_row = tk.Frame(inner, bg=BG_PANEL)
        path_row.pack(fill="x", pady=(0, 10))

        tk.Label(path_row, text=ASPERA_BASE,
                 bg=BG_INPUT, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 10), padx=10).pack(side="left", ipady=8)
        tk.Label(path_row, text="/", bg=BG_PANEL, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=4)

        self.subpath_var = tk.StringVar(value="folder/subfolder")
        tk.Entry(path_row, textvariable=self.subpath_var,
                 bg=BG_INPUT, fg=TEXT_PRIMARY,
                 insertbackground=TEXT_PRIMARY,
                 relief="flat", font=("Segoe UI", 10),
                 width=28).pack(side="left", ipady=8)

        self.preview_lbl = tk.Label(inner, text="",
                                    bg=BG_PANEL, fg=TEXT_INFO,
                                    font=("Segoe UI", 9))
        self.preview_lbl.pack(anchor="w", pady=(6, 0))
        self.subpath_var.trace("w", self.update_preview)
        self.update_preview()

        self.config_error = tk.Label(inner, text="", bg=BG_PANEL,
                                     fg=TEXT_ERROR, font=("Segoe UI", 9))
        self.config_error.pack(anchor="w", pady=(8, 0))

        btn_row = tk.Frame(self.container, bg=BG_DARK)
        btn_row.pack(pady=20)

        back_btn = tk.Button(btn_row, text="← Back",
                             bg=BG_INPUT, fg=TEXT_PRIMARY,
                             font=("Segoe UI", 10), relief="flat",
                             cursor="hand2", padx=20, pady=10,
                             command=self.show_login_screen)
        back_btn.pack(side="left", padx=(0, 12))
        back_btn.bind("<Enter>", lambda e: back_btn.config(bg=BORDER))
        back_btn.bind("<Leave>", lambda e: back_btn.config(bg=BG_INPUT))

        start_btn = tk.Button(btn_row, text="START MONITORING  →",
                              bg=ACCENT, fg=TEXT_PRIMARY,
                              font=("Segoe UI", 11, "bold"),
                              relief="flat", cursor="hand2",
                              padx=30, pady=10,
                              command=self.do_start)
        start_btn.pack(side="left")
        start_btn.bind("<Enter>", lambda e: start_btn.config(bg=ACCENT_HOVER))
        start_btn.bind("<Leave>", lambda e: start_btn.config(bg=ACCENT))

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Watch Folder")
        if folder:
            self.folder_var.set(folder)

    def update_preview(self, *args):
        sub  = self.subpath_var.get().strip().strip("/")
        full = f"/{ASPERA_BASE}/{sub}" if sub else f"/{ASPERA_BASE}"
        self.preview_lbl.config(text=f"Full path: {full}")

    def do_start(self):
        folder = self.folder_var.get().strip()
        sub    = self.subpath_var.get().strip().strip("/")
        if not folder:
            self.config_error.config(text="Please select a local watch folder.")
            return
        if not sub:
            self.config_error.config(text="Please enter the Aspera sub-path.")
            return
        self.watch_folder  = folder
        self.aspera_folder = f"/{ASPERA_BASE}/{sub}"
        self.log_file      = os.path.join(folder, "upload_log.txt")
        os.makedirs(folder, exist_ok=True)

        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.show_dashboard()

    def show_dashboard(self):
        self.clear_container()
        self.set_status("Running", TEXT_SUCCESS)

        info = tk.Frame(self.container, bg=BG_PANEL,
                        highlightbackground=BORDER, highlightthickness=1)
        info.pack(fill="x", pady=(15, 10))
        info_inner = tk.Frame(info, bg=BG_PANEL)
        info_inner.pack(padx=20, pady=10, fill="x")

        def info_item(parent, label, value):
            f = tk.Frame(parent, bg=BG_PANEL)
            f.pack(side="left", padx=20)
            tk.Label(f, text=label, bg=BG_PANEL, fg=TEXT_SECONDARY,
                     font=("Segoe UI", 8)).pack(anchor="w")
            tk.Label(f, text=value, bg=BG_PANEL, fg=TEXT_PRIMARY,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")

        info_item(info_inner, "USER",        self.username)
        info_item(info_inner, "WATCHING",    self.watch_folder)
        info_item(info_inner, "DESTINATION", self.aspera_folder)
        info_item(info_inner, "FILE TYPES",  ".zip only")

        tk.Label(self.container, text="Live Transfer Log",
                 bg=BG_DARK, fg=TEXT_SECONDARY,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 4))

        log_frame = tk.Frame(self.container, bg=BG_PANEL,
                             highlightbackground=BORDER, highlightthickness=1)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, bg=BG_PANEL, fg=TEXT_PRIMARY,
                                font=("Consolas", 10), relief="flat",
                                state="disabled", wrap="word",
                                padx=16, pady=12,
                                insertbackground=TEXT_PRIMARY,
                                selectbackground=ACCENT)
        self.log_text.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(log_frame, command=self.log_text.yview,
                              bg=BG_PANEL, troughcolor=BG_PANEL, relief="flat")
        scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scroll.set)

        self.log_text.tag_config("success", foreground=TEXT_SUCCESS)
        self.log_text.tag_config("error",   foreground=TEXT_ERROR)
        self.log_text.tag_config("info",    foreground=TEXT_INFO)
        self.log_text.tag_config("warn",    foreground="#FFA726")
        self.log_text.tag_config("time",    foreground=TEXT_SECONDARY)

        btn_row = tk.Frame(self.container, bg=BG_DARK)
        btn_row.pack(fill="x", pady=(10, 0))

        self.stop_btn = tk.Button(btn_row,
                                  text="⬛  STOP MONITORING",
                                  bg="#333333", fg=TEXT_PRIMARY,
                                  font=("Segoe UI", 10, "bold"),
                                  relief="flat", cursor="hand2",
                                  padx=20, pady=10,
                                  command=self.do_stop)
        self.stop_btn.pack(side="right")
        self.stop_btn.bind("<Enter>",
                           lambda e: self.stop_btn.config(bg="#444444"))
        self.stop_btn.bind("<Leave>",
                           lambda e: self.stop_btn.config(bg="#333333"))

        self.is_running = True
        self.append_log(f"Session started — user: {self.username}", "info")
        self.append_log(f"Watching folder: {self.watch_folder}", "info")
        self.append_log(f"Aspera destination: {self.aspera_folder}", "info")
        self.append_log("Watcher is running — waiting for .zip files...", "success")
        self.start_watcher_thread()

    def append_log(self, message, tag=""):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{now}]  ", "time")
        self.log_text.insert("end", f"{message}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def do_stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.is_running = False
        self.set_status("Stopped", TEXT_ERROR)
        self.append_log("Monitoring stopped by user.", "warn")
        logging.info(f"Watcher stopped | user: {self.username}")
        self.stop_btn.config(
            text="▶  START MONITORING",
            bg=TEXT_SUCCESS, fg=BG_DARK,
            command=self.do_restart)
        self.stop_btn.bind("<Enter>",
                           lambda e: self.stop_btn.config(bg="#45A049"))
        self.stop_btn.bind("<Leave>",
                           lambda e: self.stop_btn.config(bg=TEXT_SUCCESS))

    def do_restart(self):
        self.processing      = set()
        self.processing_lock = threading.Lock()
        self.is_running      = True
        self.set_status("Running", TEXT_SUCCESS)
        self.append_log("Monitoring restarted by user.", "success")
        logging.info(f"Watcher restarted | user: {self.username}")
        self.start_watcher_thread()
        self.stop_btn.config(
            text="⬛  STOP MONITORING",
            bg="#333333", fg=TEXT_PRIMARY,
            command=self.do_stop)
        self.stop_btn.bind("<Enter>",
                           lambda e: self.stop_btn.config(bg="#444444"))
        self.stop_btn.bind("<Leave>",
                           lambda e: self.stop_btn.config(bg="#333333"))

    def start_watcher_thread(self):
        self.processing      = set()
        self.processing_lock = threading.Lock()
        handler              = self.build_handler()
        self.observer        = Observer()
        self.observer.schedule(handler, self.watch_folder, recursive=False)
        self.observer.start()
        logging.info(
            f"Watcher started | user: {self.username} | folder: {self.watch_folder}")

    def build_handler(self):
        app = self

        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory:
                    return
                ext = os.path.splitext(event.src_path)[1].lower()
                if ext in KEEP_EXTENSIONS:
                    app.handle_file(event.src_path)

            def on_modified(self, event):
                if event.is_directory:
                    return
                ext = os.path.splitext(event.src_path)[1].lower()
                if ext in KEEP_EXTENSIONS:
                    app.handle_file(event.src_path)

        return Handler()

    def handle_file(self, file_path):
        with self.processing_lock:
            if file_path in self.processing:
                return
            self.processing.add(file_path)

        thread = threading.Thread(
            target=self.upload_and_release,
            args=(file_path,),
            daemon=True
        )
        thread.start()

    def wait_for_file_ready(self, file_path,
                             stable_secs=3, interval=1, timeout=300):
        stable_count = 0
        last_size    = -1
        elapsed      = 0

        while elapsed < timeout:
            try:
                current_size = os.path.getsize(file_path)
            except FileNotFoundError:
                return False

            if current_size == 0:
                self.root.after(0, self.append_log,
                    f"Compressing: {os.path.basename(file_path)} — 0 KB, waiting...",
                    "warn")
                stable_count = 0
            elif current_size == last_size:
                stable_count += 1
                self.root.after(0, self.append_log,
                    f"Compressing: {os.path.basename(file_path)} — "
                    f"stable {stable_count}/{stable_secs}s "
                    f"({round(current_size/1024/1024, 2)} MB)", "warn")
                if stable_count >= stable_secs:
                    self.root.after(0, self.append_log,
                        f"Ready: {os.path.basename(file_path)} "
                        f"({round(current_size/1024/1024, 2)} MB)", "info")
                    return True
            else:
                stable_count = 0
                self.root.after(0, self.append_log,
                    f"Compressing: {os.path.basename(file_path)} — "
                    f"growing ({round(current_size/1024/1024, 2)} MB)...", "warn")

            last_size  = current_size
            time.sleep(interval)
            elapsed   += interval

        return False

    def upload_and_release(self, file_path):
        try:
            filename = os.path.basename(file_path)
            self.root.after(0, self.append_log,
                f"Detected: {filename} — checking compression...", "info")

            is_ready = self.wait_for_file_ready(file_path)

            if not is_ready:
                self.root.after(0, self.append_log,
                    f"TIMEOUT: {filename} — skipped.", "error")
                logging.error(f"Timeout: {filename}")
                return

            self.upload_file(file_path)

        finally:
            with self.processing_lock:
                self.processing.discard(file_path)
            self.root.after(0, self.append_log,
                            "Waiting for next file...", "info")

    def upload_file(self, file_path):
        filename = os.path.basename(file_path)
        self.root.after(0, self.append_log,
                        f"Uploading: {filename} → {self.aspera_folder}", "")
        logging.info(f"Upload started | user: {self.username} | file: {filename}")

        cmd = [
            ASCLI_CMD,
            "shares", "files", "upload",
            file_path,
            f"--to-folder={self.aspera_folder}",
            f"--url={ASPERA_URL}",
            f"--username={self.username}",
            f"--password={self.password}"
        ]

        result = subprocess.run(cmd, capture_output=True,
                                text=True, shell=True)

        if result.returncode == 0:
            self.root.after(0, self.append_log,
                            f"SUCCESS: {filename} uploaded!", "success")
            logging.info(f"Upload SUCCESS | user: {self.username} | file: {filename}")
            try:
                os.remove(file_path)
                self.root.after(0, self.append_log,
                                f"DELETED: {filename} from local folder", "warn")
                logging.info(f"Deleted local file: {filename}")
            except Exception as e:
                self.root.after(0, self.append_log,
                                f"DELETE FAILED: {filename} | {e}", "error")
        else:
            self.root.after(0, self.append_log,
                            f"FAILED: {filename} — {result.stderr.strip()}", "error")
            self.root.after(0, self.append_log,
                            f"NOTE: {filename} kept in local folder", "warn")
            logging.error(f"Upload FAILED | user: {self.username} | file: {filename}")

    def on_close(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.root.destroy()


if __name__ == "__main__":
    try:
        from PIL import Image, ImageTk
    except ImportError:
        import subprocess as sp
        sp.run(["pip", "install", "Pillow"], check=True)
        from PIL import Image, ImageTk

    root = tk.Tk()
    app  = AutoFileTransferApp(root)
    root.mainloop()
