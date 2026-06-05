#!/usr/bin/env python3
"""图文笔记 → PDF | 小红书·知乎·微信公众号"""

import os
import sys
import re
import tempfile
import shutil
import threading
import webbrowser

# High-DPI awareness (must be before tkinter import)
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # System aware
    except Exception:
        pass
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from src.platforms import detect_platform, PLATFORMS
    from src.platforms.base import UnsupportedError, CookieExpiredError
    from src.downloader import download_images
    from src.pdf_maker import content_to_pdf, images_to_pdf
except ImportError:
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                    'requests', 'Pillow', 'tqdm', 'beautifulsoup4', 'fpdf2'])
    from src.platforms import detect_platform, PLATFORMS
    from src.platforms.base import UnsupportedError, CookieExpiredError
    from src.downloader import download_images
    from src.pdf_maker import content_to_pdf, images_to_pdf

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(ROOT_DIR, 'output')


def _open_file(path: str):
    """Cross-platform file opener."""
    if sys.platform == 'win32':
        os.startfile(path)
    else:
        import subprocess
        subprocess.run(['xdg-open', path])


def extract_url(text: str) -> str:
    patterns = [
        r'https?://xhslink\.com/\S+',
        r'https?://(?:www\.)?xiaohongshu\.com/\S+',
        r'https?://(?:www\.)?zhihu\.com/\S+',
        r'https?://zhuanlan\.zhihu\.com/\S+',
        r'https?://mp\.weixin\.qq\.com/\S+',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0).rstrip('.,;:!?）)')
    return ""


def load_cookie(cookie_file: str) -> str:
    if not cookie_file:
        return ""
    path = os.path.join(ROOT_DIR, cookie_file)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""


def save_cookie(value: str, cookie_file: str):
    if not cookie_file:
        return
    path = os.path.join(ROOT_DIR, cookie_file)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(value.strip())


def test_cookie_web(cookie: str, test_url: str) -> bool:
    """Test cookie against a platform-specific URL."""
    if not cookie or len(cookie) < 20:
        return False
    try:
        import requests
        resp = requests.get(test_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cookie': cookie,
        }, timeout=8, allow_redirects=True)
        return resp.status_code == 200 and len(resp.text) > 500
    except Exception:
        return False


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("图文笔记 → PDF")
        self.root.geometry("720x1000")
        self.root.resizable(True, True)
        self.root.minsize(640,720)
        # === Instagram Style ===
        style = ttk.Style()
        style.theme_use('clam')

        BG = '#fafafa'
        self.root.configure(bg=BG)
        CARD_BG = '#ffffff'
        ACCENT = '#0095f6'
        ACCENT_HOVER = '#1877f2'
        TEXT = '#262626'
        TEXT_SEC = '#8e8e8e'
        BORDER = '#c7c7c7'
        SUCCESS = '#78de54'
        WARNING = '#d9920b'
        DANGER = '#ed4956'

        style.configure('.', background=BG, foreground=TEXT, font=('Microsoft YaHei UI', 10))
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=TEXT)
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 17, 'bold'), foreground=TEXT)
        style.configure('Hint.TLabel', font=('Microsoft YaHei UI', 10), foreground=TEXT_SEC)

        # Buttons — visible borders
        style.configure('TButton', font=('Microsoft YaHei UI', 10), padding=(14, 7),
                         relief='solid', borderwidth=1, bordercolor='#c0c0c0', background=CARD_BG)
        style.map('TButton',
                  background=[('active', '#f5f5f5'), ('!disabled', CARD_BG)],
                  bordercolor=[('active', '#a0a0a0'), ('!disabled', '#c0c0c0')],
                  foreground=[('disabled', '#c0c0c0')])
        style.configure('Small.TButton', font=('Microsoft YaHei UI', 10), padding=(10, 5))

        # Checkbutton
        style.configure('TCheckbutton', background=BG, foreground=TEXT, indicatorsize=18, font=('Microsoft YaHei UI', 10))
        style.map('TCheckbutton', background=[('active', BG)])

        # Progressbar
        style.configure('TProgressbar', thickness=4, background=ACCENT, troughcolor='#efefef',
                         borderwidth=0, relief='flat')

        # === Main container ===
        main = ttk.Frame(root, padding=(24, 20))
        main.pack(fill=tk.BOTH, expand=True)

        # === Title ===
        title_row = ttk.Frame(main)
        title_row.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(title_row, text="图文笔记 → PDF", style='Title.TLabel').pack(side=tk.LEFT)

        # Status pills
        status_row = ttk.Frame(main)
        status_row.pack(fill=tk.X, pady=(0, 12))

        self.env_btn = tk.Label(status_row, text="● 环境检测",
                                 font=("Microsoft YaHei UI", 10), fg=WARNING, bg=BG, cursor="hand2")
        self.env_btn.pack(side=tk.LEFT, padx=(0, 20))
        self.env_btn.bind("<Button-1>", lambda e: self.check_env())
        self._add_label_hover(self.env_btn)

        self.cookie_status = tk.Label(status_row, text="● Cookie: 未设置",
                                       font=("Microsoft YaHei UI", 10), fg=WARNING, bg=BG)
        self.cookie_status.pack(side=tk.LEFT)

        ttk.Button(status_row, text="?", width=2, style='Small.TButton',
                   command=self.show_cookie_help).pack(side=tk.RIGHT)

        # === URL card ===
        url_card = tk.Frame(main, bg=CARD_BG, highlightthickness=2, highlightbackground=BORDER)
        url_card.pack(fill=tk.X, pady=(0, 12))

        url_inner = tk.Frame(url_card, bg=CARD_BG, padx=16, pady=16)
        url_inner.pack(fill=tk.X)

        tk.Label(url_inner, text="支持小红书 · 知乎 · 微信公众号   |   自动识别平台", font=("Microsoft YaHei UI", 8),
                 bg=CARD_BG, fg='#b0b0b0').pack(anchor=tk.W, pady=(0, 6))

        self.url_entry = tk.Text(url_inner, height=2, font=("Microsoft YaHei UI", 11), wrap=tk.WORD,
                                  relief=tk.FLAT, borderwidth=0, padx=10, pady=8,
                                  bg='#f0f2f5', fg=TEXT, insertbackground=TEXT,
                                  highlightthickness=1, highlightbackground='#c0c0c0',
                                  highlightcolor='#0095f6')
        self.url_entry.pack(fill=tk.BOTH, expand=True)

        # === Options row ===
        opt_frame = ttk.Frame(main)
        opt_frame.pack(fill=tk.X, pady=(0, 8))

        self.watermark_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="裁剪", variable=self.watermark_var,
                         command=self._toggle_crop).pack(side=tk.LEFT)

        self.crop_top_lbl = tk.Label(opt_frame, text="顶", font=("Microsoft YaHei UI", 8), bg=BG, fg=TEXT_SEC)
        self.crop_top_lbl.pack(side=tk.LEFT, padx=(2, 0))
        self.crop_top_var = tk.StringVar(value="0")
        self.crop_top_spin = ttk.Spinbox(opt_frame, textvariable=self.crop_top_var,
                     values=[str(i) for i in range(0, 31)], width=2, font=("Microsoft YaHei UI", 8))
        self.crop_top_spin.pack(side=tk.LEFT)
        self.crop_top_pct = tk.Label(opt_frame, text="%", font=("Microsoft YaHei UI", 8), bg=BG, fg=TEXT_SEC)
        self.crop_top_pct.pack(side=tk.LEFT)

        self.crop_bot_lbl = tk.Label(opt_frame, text="底", font=("Microsoft YaHei UI", 8), bg=BG, fg=TEXT_SEC)
        self.crop_bot_lbl.pack(side=tk.LEFT, padx=(2, 0))
        self.crop_bot_var = tk.StringVar(value="7")
        self.crop_bot_spin = ttk.Spinbox(opt_frame, textvariable=self.crop_bot_var,
                     values=[str(i) for i in range(0, 31)], width=2, font=("Microsoft YaHei UI", 8))
        self.crop_bot_spin.pack(side=tk.LEFT)
        self.crop_bot_pct = tk.Label(opt_frame, text="%", font=("Microsoft YaHei UI", 8), bg=BG, fg=TEXT_SEC)
        self.crop_bot_pct.pack(side=tk.LEFT)

        self.show_cookie_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="Cookie", variable=self.show_cookie_var,
                         command=self._toggle_cookie_panel).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(opt_frame, text="输出", style='Hint.TLabel').pack(side=tk.LEFT, padx=(12, 4))
        self.out_dir_var = tk.StringVar(value=DEFAULT_OUT_DIR)
        self.out_dir_label = tk.Label(opt_frame, text=self._short_path(ROOT_DIR),
                                       font=("Microsoft YaHei UI", 9), fg=TEXT_SEC, bg=BG,
                                       anchor=tk.W)
        self.out_dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(opt_frame, text="修改", style='Small.TButton',
                   command=self._choose_out_dir).pack(side=tk.LEFT, padx=(4, 0))

        # === Cookie panel ===
        self.cookie_frame = tk.Frame(main, bg=CARD_BG, highlightthickness=2, highlightbackground=BORDER)
        ck_inner = tk.Frame(self.cookie_frame, bg=CARD_BG, padx=16, pady=16)
        ck_inner.pack(fill=tk.X)

        # Section header
        tk.Label(ck_inner, text="Cookie 设置", font=("Microsoft YaHei UI", 10, "bold"),
                 bg=CARD_BG, fg=TEXT).pack(anchor=tk.W)
        self.cookie_help_label = tk.Label(ck_inner, text="请先在输入框中粘贴链接以识别平台",
                 font=("Microsoft YaHei UI", 8), bg=CARD_BG, fg=TEXT_SEC)
        self.cookie_help_label.pack(anchor=tk.W, pady=(2, 0))

        # Content area with subtle border
        ck_content = tk.Frame(ck_inner, bg='#f8f8f8', highlightthickness=1, highlightbackground='#e0e0e0')
        ck_content.pack(fill=tk.X, pady=(8, 8), ipady=4)

        self.cookie_text = tk.Text(ck_content, height=6, font=("Consolas", 8), wrap=tk.WORD,
                                    relief=tk.FLAT, borderwidth=0, padx=8, pady=6,
                                    bg='#f8f8f8', fg=TEXT, insertbackground=TEXT)
        self.cookie_text.pack(fill=tk.X)

        # Separator
        ttk.Separator(ck_inner, orient='horizontal').pack(fill=tk.X, pady=(0, 8))

        # Action buttons
        ck_btn_row = tk.Frame(ck_inner, bg=CARD_BG)
        ck_btn_row.pack(fill=tk.X)
        ttk.Button(ck_btn_row, text="保存Cookie", style='Small.TButton',
                   command=self._save_cookie).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(ck_btn_row, text="测试Cookie", style='Small.TButton',
                   command=self._test_cookie).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(ck_btn_row, text="打开登录页", style='Small.TButton',
                   command=self._open_login).pack(side=tk.LEFT)

        # === Action buttons ===
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(12, 10))

        # Blue primary button
        style.configure('Accent.TButton', font=('Microsoft YaHei UI', 11, 'bold'),
                         padding=(18, 8), relief='solid', borderwidth=1,
                         background=ACCENT, bordercolor=ACCENT, foreground='#ffffff')
        style.map('Accent.TButton',
                  background=[('active', '#0084e0'), ('!disabled', ACCENT)],
                  bordercolor=[('active', '#0084e0'), ('!disabled', ACCENT)],
                  foreground=[('disabled', '#c0c0c0'), ('!disabled', '#ffffff')])

        self.convert_btn = ttk.Button(btn_frame, text="开始转换",
                                       style='Accent.TButton', command=self.start_convert)
        self.convert_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.open_btn = ttk.Button(btn_frame, text="打开PDF", command=self.open_pdf, state=tk.DISABLED)
        self.open_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.open_dir_btn = ttk.Button(btn_frame, text="目录", command=self.open_dir, state=tk.DISABLED)
        self.open_dir_btn.pack(side=tk.LEFT)

        # === Progress ===
        prog_frame = ttk.Frame(main)
        self.progress = ttk.Progressbar(prog_frame, mode='determinate', maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_label = ttk.Label(prog_frame, text="", width=6, style='Hint.TLabel')
        self.progress_label.pack(side=tk.RIGHT, padx=(8, 0))

        # === Log area ===
        log_frame = tk.Frame(main, bg=CARD_BG, highlightthickness=2, highlightbackground=BORDER)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        log_header = tk.Frame(log_frame, bg=CARD_BG)
        log_header.pack(fill=tk.X, padx=16, pady=(12, 6))
        tk.Label(log_header, text="状态", font=("Microsoft YaHei UI", 11, "bold"),
                 bg=CARD_BG, fg=TEXT).pack(side=tk.LEFT)

        self.log_text = tk.Text(log_frame, height=5, font=("Consolas", 12), wrap=tk.WORD,
                                 relief=tk.FLAT, borderwidth=0,
                                 bg=CARD_BG, fg=TEXT, insertbackground=TEXT)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))
        self.log_text.config(state=tk.DISABLED)

        # === Result ===
        self.result_label = tk.Label(main, text="", font=("Microsoft YaHei UI", 11, "bold"),
                                      bg=BG, fg=TEXT)
        self.result_label.pack(pady=(10, 0))

        self.output_path = ""
        self.current_platform = None

        # Init
        self._refresh_cookie_status()
        self.root.after(300, self._auto_check_env)

    def _add_label_hover(self, widget):
        """Subtle dim on hover for clickable labels."""
        def on_enter(e):
            widget.config(fg='#555555')
        def on_leave(e):
            # restore original color based on current text
            t = widget.cget('text')
            if '✓' in t:
                widget.config(fg='#58b942')
            elif '✗' in t or '无效' in t or '过期' in t:
                widget.config(fg='#ed4956')
            else:
                widget.config(fg='#d9920b')
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _add_hover(self, widget, normal_bg, hover_bg, fg):
        def on_enter(e):
            widget.config(bg=hover_bg)
        def on_leave(e):
            widget.config(bg=normal_bg)
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _add_press(self, widget, hover_bg, press_bg):
        def on_press(e):
            widget.config(bg=press_bg)
        def on_release(e):
            widget.config(bg=hover_bg)
        widget.bind("<ButtonPress-1>", on_press)
        widget.bind("<ButtonRelease-1>", on_release)

    def _short_path(self, path: str) -> str:
        if len(path) <= 50:
            return path
        return "..." + path[-47:]

    def _set_cookie_color(self, color: str, text: str):
        colors = {'green': '#58b942', 'yellow': '#d9920b', 'red': '#ed4956'}
        self.cookie_status.config(text=text, fg=colors.get(color, '#d9920b'))

    def _set_env_btn_color(self, color: str, text: str):
        colors = {'green': '#58b942', 'yellow': '#d9920b', 'red': '#ed4956'}
        self.env_btn.config(text=text, fg=colors.get(color, '#d9920b'))

    def _platform_cookie_file(self) -> str:
        if self.current_platform:
            return self.current_platform.cookie_file
        return ""

    def _platform_cookie_help(self) -> str:
        if self.current_platform:
            return self.current_platform.cookie_help()
        return ""

    def _refresh_cookie_status(self):
        if not self.current_platform:
            self._set_cookie_color('yellow', '● Cookie: 等待识别平台')
            return
        cf = self._platform_cookie_file()
        if cf and load_cookie(cf):
            self._set_cookie_color('green', f'● Cookie: {self.current_platform.name}已加载')
        elif cf:
            self._set_cookie_color('yellow', f'● Cookie: {self.current_platform.name}未设置')
        else:
            self._set_cookie_color('green', '● Cookie: 无需设置')

    def _toggle_crop(self):
        state = tk.NORMAL if self.watermark_var.get() else tk.DISABLED
        for w in [self.crop_top_lbl, self.crop_top_spin, self.crop_top_pct,
                   self.crop_bot_lbl, self.crop_bot_spin, self.crop_bot_pct]:
            w.config(state=state)

    def _toggle_cookie_panel(self):
        if self.show_cookie_var.get():
            self.cookie_frame.pack(fill=tk.X, pady=(0, 8), before=self.convert_btn.master)
            cf = self._platform_cookie_file()
            current = load_cookie(cf) if cf else ""
            self.cookie_text.delete('1.0', tk.END)
            if current:
                self.cookie_text.insert('1.0', current)
            # Update cookie panel label
            if self.current_platform:
                self._update_cookie_help_label()
        else:
            self.cookie_frame.pack_forget()

    def _update_cookie_help_label(self):
        if self.current_platform:
            help_text = self.current_platform.cookie_help()
            if hasattr(self, 'cookie_help_label'):
                self.cookie_help_label.config(text=help_text)
            # If no cookie needed, disable text input
            if not self.current_platform.cookie_file:
                self.cookie_text.config(state=tk.DISABLED, bg='#f0f0f0')
            else:
                self.cookie_text.config(state=tk.NORMAL, bg='#f8f8f8')

    def _save_cookie(self):
        cookie = self.cookie_text.get('1.0', 'end-1c').strip()
        cf = self._platform_cookie_file()
        if not cf:
            self.log("[Cookie] 当前平台无需设置Cookie")
            return
        if not cookie:
            self.log("[Cookie] 输入为空，未保存")
            return
        save_cookie(cookie, cf)
        self._refresh_cookie_status()
        self.log(f"[Cookie] {self.current_platform.name}Cookie已保存")

    def _open_login(self):
        if self.current_platform and self.current_platform.login_url:
            webbrowser.open(self.current_platform.login_url)
        else:
            webbrowser.open('https://www.xiaohongshu.com')

    def _choose_out_dir(self):
        directory = filedialog.askdirectory(initialdir=self.out_dir_var.get(), title="选择PDF输出目录")
        if directory:
            self.out_dir_var.set(directory)
            self.out_dir_label.config(text=self._short_path(directory))

    def _test_cookie(self):
        cf = self._platform_cookie_file()
        if not cf:
            self.log("[Cookie测试] 当前平台无需Cookie")
            return
        cookie = self.cookie_text.get('1.0', 'end-1c').strip()
        if not cookie:
            cookie = load_cookie(cf)
        if not cookie:
            self.log("[Cookie测试] 没有可测试的Cookie，请先输入")
            return
        self.log("[Cookie测试] 验证中...")
        # Use platform-specific test URL
        test_url = f"https://www.{self.current_platform.name.replace(' ', '').lower()}.com"
        # But for XHS use the user API
        test_urls = {'小红书': 'https://edith.xiaohongshu.com/api/sns/web/v2/user/me',
                      '知乎': 'https://www.zhihu.com',
                      '微信公众号': None}
        actual_url = test_urls.get(self.current_platform.name, test_url)
        if actual_url is None:
            self.log("[Cookie测试] 当前平台无需Cookie")
            return
        ok = test_cookie_web(cookie, actual_url)
        if ok:
            self._set_cookie_color('green', f'● Cookie: {self.current_platform.name}有效')
            self.log("[Cookie测试] Cookie 有效")
        else:
            self._set_cookie_color('red', f'● Cookie: {self.current_platform.name}无效')
            self.log("[Cookie测试] Cookie 无效或已过期，请重新获取")

    def log(self, msg: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _auto_check_env(self):
        """Auto-check dependencies on startup. Prompt only if something is missing."""
        required = {
            'requests': ('requests', 0.4),
            'PIL': ('Pillow', 15),
            'tqdm': ('tqdm', 0.3),
            'bs4': ('beautifulsoup4', 0.7),
            'fpdf': ('fpdf2', 2),
        }
        missing = []
        total_mb = 0.0
        for mod, (pkg, size_mb) in required.items():
            try:
                __import__(mod)
            except ImportError:
                missing.append((pkg, size_mb))
                total_mb += size_mb

        if not missing:
            self._set_env_btn_color('green', '● 环境检测 ✓')
            return  # All OK, silent

        lines = '\n'.join(f'  - {pkg}  (~{size:.1f} MB)' for pkg, size in missing)
        msg = (f"检测到缺少以下 Python 依赖包:\n\n{lines}\n\n"
               f"总计需下载约 {total_mb:.1f} MB\n\n是否立即安装？")
        if messagebox.askyesno("首次使用 - 安装依赖", msg):
            self.log("[环境检测] 正在安装，请稍候...")
            import subprocess
            for pkg, _ in missing:
                self.log(f"  安装 {pkg}...")
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', pkg, '-q'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    self.log(f"  {pkg} 安装成功")
                else:
                    self.log(f"  {pkg} 安装失败: {result.stderr.strip()}")
            all_ok = True
            for pkg, _ in missing:
                try:
                    mod = {'requests': 'requests', 'Pillow': 'PIL', 'tqdm': 'tqdm', 'beautifulsoup4': 'bs4'}[pkg]
                    __import__(mod)
                except ImportError:
                    all_ok = False
            if all_ok:
                self._set_env_btn_color('green', '● 环境检测 ✓')
            else:
                self._set_env_btn_color('red', '● 环境检测 ✗')
            self.log("[环境检测] 完成，请重新启动程序以确保依赖生效")

    def check_env(self):
        """Check if all required packages are installed. Offer to install if missing."""
        required = {
            'requests': ('requests', 0.4),
            'PIL': ('Pillow', 15),
            'tqdm': ('tqdm', 0.3),
            'bs4': ('beautifulsoup4', 0.7),
            'fpdf': ('fpdf2', 2),
        }
        missing = []
        total_mb = 0.0
        for mod, (pkg, size_mb) in required.items():
            try:
                __import__(mod)
            except ImportError:
                missing.append((pkg, size_mb))
                total_mb += size_mb

        if not missing:
            self._set_env_btn_color('green', '● 环境检测 ✓')
            self.log("[环境检测] 所有依赖已满足，无需安装")
            return

        self._set_env_btn_color('red', '● 环境检测 ✗')
        self.log(f"[环境检测] 缺少以下包: {', '.join(m[0] for m in missing)} (共约 {total_mb:.1f} MB)")
        lines = '\n'.join(f'  - {pkg}  (~{size:.1f} MB)' for pkg, size in missing)
        msg = f"检测到缺少以下 Python 包:\n\n{lines}\n\n总计需下载约 {total_mb:.1f} MB\n\n是否立即安装？"
        if messagebox.askyesno("安装依赖", msg):
            self.log("[环境检测] 正在安装，请稍候...")
            import subprocess
            for pkg, _ in missing:
                self.log(f"  安装 {pkg}...")
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', pkg, '-q'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    self.log(f"  {pkg} 安装成功")
                else:
                    self.log(f"  {pkg} 安装失败: {result.stderr.strip()}")
            all_ok = True
            for pkg, _ in missing:
                try:
                    mod = {'requests': 'requests', 'Pillow': 'PIL', 'tqdm': 'tqdm', 'beautifulsoup4': 'bs4'}[pkg]
                    __import__(mod)
                except ImportError:
                    all_ok = False
            if all_ok:
                self._set_env_btn_color('green', '● 环境检测 ✓')
            self.log("[环境检测] 完成")

    def show_cookie_help(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("使用教程")
        dlg.geometry("560x620")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.configure(bg='#fafafa')

        canvas = tk.Canvas(dlg, highlightthickness=0, bg='#fafafa', width=540)
        scrollbar = ttk.Scrollbar(dlg, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW, width=540)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse wheel scrolling - bind to everything
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        for w in (dlg, canvas, scroll_frame):
            w.bind("<MouseWheel>", _on_mousewheel)
        dlg.bind("<Enter>", lambda e: dlg.bind_all("<MouseWheel>", _on_mousewheel), add="+")
        dlg.bind("<Leave>", lambda e: dlg.unbind_all("<MouseWheel>"), add="+")

        frame = ttk.Frame(scroll_frame, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        def title(text):
            ttk.Label(frame, text=text, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W, pady=(12, 4))

        def body(text):
            ttk.Label(frame, text=text, font=("Microsoft YaHei UI", 10), wraplength=470).pack(anchor=tk.W, padx=(8, 0))

        def step(num, text):
            ttk.Label(frame, text=f"  {num}. {text}", font=("Microsoft YaHei UI", 10), wraplength=460).pack(anchor=tk.W, padx=(8, 0))

        # === Section 0: Environment ===
        title("环境配置（首次使用必读）")
        body("首次启动时会自动检测 Python 依赖包是否齐全。如缺少，会弹窗提示并帮你一键安装（需联网，约 16 MB）。")
        body("如果没有任何弹窗提示，说明环境已就绪，直接使用即可。")
        body("你也可以随时点击右上角「环境检测」按钮手动检查。")

        # === Section 1: Overview ===
        title("一、工具简介")
        body("支持 小红书、知乎、微信公众号 三个平台。粘贴链接后自动识别平台，将文章中的文字和图片按原顺序导出为 PDF。支持短链接(xhslink.com)和完整链接，可识别整段分享文本中的 URL。")

        title("二、基本使用流程")
        step(1, "复制文章的分享链接（或整段分享文本）")
        step(2, "粘贴到白色输入框中（上方小字显示支持的平台）")
        step(3, "点击「开始转换」（自动识别平台）")
        step(4, "等待进度条走完，点击「打开PDF」查看结果")

        # === Section 3: Cookie ===
        title("三、Cookie 设置 ⚠️")
        body("小红书和知乎需要登录凭证(Cookie)才能访问完整内容。微信公众号文章是公开的，无需 Cookie。")
        body("Cookie 类似门禁卡，一般几周后过期，届时需要重新获取。工具会根据链接自动切换对应平台的 Cookie 设置。")
        body("")
        body("获取 Cookie 的详细步骤：")
        step(1, "点击下方「打开小红书登录」按钮，在浏览器中打开网页")
        step(2, "扫码或手机号登录你的小红书账号")
        step(3, "登录成功后，按键盘 F12 键（部分笔记本需 Fn+F12）")
        step(4, "在开发者工具顶部找到「Application」或 网络 标签并点击")
        step(5, "按一下Ctrl+F搜索 “cookies”，列表中找到「Cookies」→ 点击展开 → 找到“标头”")
        step(6, "选中“标头”中的Cookies，按Ctrl+C 复制")
        step(7, "回到本工具，勾选「显示Cookie设置」")
        step(8, "在 Cookie 文本框中 Ctrl+V 粘贴，点击「保存Cookie」")
        step(9, "点击「测试Cookie」确认无误（提示\"有效\"即可）")
        body("")
        body("常见问题：")
        body("  Q: 找不到 Application 标签？")
        body("  A: 试试找到网络标签也可以；也有可能 F12 打开的面板如果较窄，Application 可能隐藏在更多菜单中，点击即可找到。")
        body("  Q: 复制出来的内容很短（只有几十个字符）？")
        body("  A: 可能只复制了一个键值对。正确做法是点击表格区域后 Ctrl+A（全选），确保复制了所有行。")
        body("  Q: 测试 Cookie 提示\"无效\"？")
        body("  A: 可能是 Cookie 已过期。重新登录小红书后，刷新页面，再次复制 Cookie。")

        # === Section 4: Options ===
        title("四、其他功能说明")
        body("去除水印：勾选后自动裁剪图片底部 7%（水印区域）。如果图片本身没有水印或有重要内容在底部，可取消勾选。")
        body("输出目录：PDF 默认保存在 output/ 文件夹。点击「修改」可更改保存位置。")
        body("环境检测：首次使用或发给别人时，先点此按钮。自动检查缺少的依赖包，弹窗一键安装。")

        title("五、常见报错处理")
        body("「Cookie 已过期/无效」→ 重新获取 Cookie（见第三节）")
        body("「触发验证码」→ Cookie 失效，重新获取")
        body("「暂不支持的链接」→ 链接不是小红书/知乎/公众号，或格式有误")
        body("「文章内容为空」→ 该链接可能已失效，检查链接是否正确")

        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=(16, 0))
        ttk.Button(btn_row, text="小红书登录", command=lambda: webbrowser.open('https://www.xiaohongshu.com')).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="知乎登录", command=lambda: webbrowser.open('https://www.zhihu.com')).pack(side=tk.LEFT)

    def start_convert(self):
        self.convert_btn.config(state=tk.DISABLED)
        self.open_btn.config(state=tk.DISABLED)
        self.open_dir_btn.config(state=tk.DISABLED)
        self.result_label.config(text="", fg="black")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.progress_label.config(text="")
        self.output_path = ""

        raw_text = self.url_entry.get('1.0', 'end-1c').strip()
        if not raw_text:
            self.log("请输入链接")
            self.convert_btn.config(state=tk.NORMAL)
            return

        url = extract_url(raw_text)
        if not url:
            self.log("未识别到有效链接，请检查输入")
            self.convert_btn.config(state=tk.NORMAL)
            return

        # Detect platform
        try:
            self.current_platform = detect_platform(url)
            self.log(f"识别平台: {self.current_platform.name}")
            self._refresh_cookie_status()
            if self.show_cookie_var.get():
                self._update_cookie_help_label()
        except UnsupportedError as e:
            self.log(f"暂不支持的链接: {e}")
            self.convert_btn.config(state=tk.NORMAL)
            return

        self.log(f"链接:\n  {url}\n")
        self.progress.pack(fill=tk.X, pady=(0, 4))
        self.progress_label.pack()

        remove_wm = self.watermark_var.get()
        crop_top = int(self.crop_top_var.get())
        crop_bot = int(self.crop_bot_var.get())
        thread = threading.Thread(target=self._do_convert, args=(url, remove_wm, crop_top, crop_bot), daemon=True)
        thread.start()

    def _do_convert(self, url: str, remove_wm: bool, crop_top: int = 0, crop_bot: int = 7):
        temp_dir = None
        try:
            platform = self.current_platform
            cf = platform.cookie_file
            cookie = load_cookie(cf) if cf else ""

            self._log_thread("[1/4] 获取内容...")
            self._set_progress(10)
            result = platform.fetch(url, cookie)
            self._log_thread(f"      标题: {result.title}")
            self._log_thread(f"      内容项: {len(result.items)} 项")
            self._set_progress(30)

            # Collect image URLs and build path map
            img_urls = [item.data for item in result.items if item.type == 'image']
            img_path_map = {}

            if img_urls:
                self._log_thread("[2/4] 下载图片中...")
                temp_dir = tempfile.mkdtemp(prefix='xhs2pdf_')

                def progress_cb(current, total):
                    pct = 30 + int((current / total) * 40)
                    self._set_progress(pct)
                    self._log_thread(f"      下载中: {current}/{total}")

                local_paths = download_images(img_urls, temp_dir, progress_callback=progress_cb)
                for orig_url, local_path in zip(img_urls, local_paths):
                    img_path_map[orig_url] = local_path
                self._log_thread(f"      已下载: {len(local_paths)}/{len(img_urls)} 张")

            self._log_thread("[3/4] 生成PDF...")
            self._set_progress(80)
            out_dir = self.out_dir_var.get()
            output_path = os.path.join(out_dir, f"{result.title}.pdf")

            if result.items and any(item.type == 'text' for item in result.items):
                # Mixed text+image
                content_to_pdf(result.items, img_path_map, result.title, output_path,
                             remove_watermark=remove_wm, crop_top=crop_top, crop_bot=crop_bot)
            else:
                # Images only
                images_to_pdf([img_path_map[u] for u in img_urls if u in img_path_map],
                             output_path, remove_watermark=remove_wm,
                             crop_top=crop_top, crop_bot=crop_bot)

            self.output_path = output_path
            self._set_progress(100)
            self._log_thread(f"\n完成! PDF已保存到:\n  {output_path}")
            self._result_success(output_path)

        except CookieExpiredError as e:
            self._set_cookie_color('red', '● Cookie: 已过期')
            self._log_thread(f"\nCookie 已过期或无效！")
            self._log_thread(f"请勾选\"显示Cookie设置\"，重新粘贴有效的Cookie并保存。")
            self._result_fail("Cookie 已过期/无效，请更新Cookie")

        except UnsupportedError as e:
            self._log_thread(f"\n不支持: {e}")
            self._result_fail(str(e))

        except Exception as e:
            self._log_thread(f"\n失败: {e}")
            self._result_fail(str(e))

        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _set_progress(self, value: int):
        def update():
            self.progress['value'] = value
            self.progress_label.config(text=f"{value}%")
        self.root.after(0, update)

    def _log_thread(self, msg: str):
        self.root.after(0, self.log, msg)

    def _result_success(self, path: str):
        def update():
            self.progress['value'] = 100
            self.progress_label.config(text="完成")
            self.result_label.config(text="转换成功！", fg="#58b942")
            self.open_btn.config(state=tk.NORMAL)
            self.open_dir_btn.config(state=tk.NORMAL)
            self.convert_btn.config(state=tk.NORMAL)
        self.root.after(0, update)

    def _result_fail(self, err_msg: str):
        def update():
            self.progress_label.config(text="失败")
            short_msg = err_msg[:100] + ("..." if len(err_msg) > 100 else "")
            self.result_label.config(text=short_msg, fg="#ed4956")
            self.convert_btn.config(state=tk.NORMAL)
        self.root.after(0, update)

    def open_pdf(self):
        if self.output_path and os.path.exists(self.output_path):
            _open_file(self.output_path)

    def open_dir(self):
        if self.output_path:
            _open_file(os.path.dirname(self.output_path))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
