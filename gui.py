#!/usr/bin/env python3
"""小红书笔记图片 → PDF 转换工具 (GUI版)"""

import os
import sys
import re
import tempfile
import shutil
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fetcher import (
    resolve_note_url, parse_note_id, fetch_note_html,
    extract_note_data, extract_note_info, CookieExpiredError,
)
from downloader import download_images
from pdf_maker import images_to_pdf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(SCRIPT_DIR, 'cookie.txt')


def extract_url(text: str) -> str:
    patterns = [
        r'https?://xhslink\.com/\S+',
        r'https?://www\.xiaohongshu\.com/\S+',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0).rstrip('.,;:!?）)')
    return ""


def load_cookie() -> str:
    env_cookie = os.environ.get('XHS_COOKIE', '')
    if env_cookie:
        return env_cookie
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""


def save_cookie(value: str):
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        f.write(value.strip())


def test_cookie(cookie: str) -> bool:
    """Quick test if cookie is valid by hitting the homepage."""
    if not cookie or len(cookie) < 20:
        return False
    try:
        import requests
        resp = requests.get('https://www.xiaohongshu.com', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cookie': cookie,
        }, timeout=8, allow_redirects=False)
        # 302 redirect to /explore = logged in; 200 with login page = not logged in
        if resp.status_code == 302:
            return True
        return resp.status_code == 200 and 'login-form' not in resp.text[:2000].lower()
    except Exception:
        return False


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("小红书笔记 → PDF")
        self.root.geometry("560x560")
        self.root.resizable(True, True)
        self.root.minsize(480, 480)
        self.root.configure(bg='#f0f2f5')

        # === Style configuration ===
        style = ttk.Style()
        style.theme_use('clam')

        # Color palette
        BG = '#f0f2f5'
        CARD_BG = '#ffffff'
        ACCENT = '#2563eb'
        ACCENT_HOVER = '#1d4ed8'
        TEXT = '#1e293b'
        TEXT_SEC = '#64748b'
        BORDER = '#e2e8f0'
        SUCCESS = '#16a34a'
        WARNING = '#d97706'
        DANGER = '#dc2626'
        LOG_BG = '#1e293b'
        LOG_FG = '#cbd5e1'

        # Global defaults
        style.configure('.', background=BG, foreground=TEXT, font=('Microsoft YaHei UI', 9))
        style.configure('TFrame', background=BG)
        style.configure('Card.TFrame', background=CARD_BG, relief='solid', borderwidth=1, bordercolor=BORDER)
        style.configure('TLabel', background=BG, foreground=TEXT)
        style.configure('Card.TLabel', background=CARD_BG, foreground=TEXT)
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 15, 'bold'), foreground=TEXT)
        style.configure('Hint.TLabel', font=('Microsoft YaHei UI', 9), foreground=TEXT_SEC)
        style.configure('Small.TLabel', font=('Microsoft YaHei UI', 8), foreground=TEXT_SEC)

        # Buttons
        style.configure('TButton', font=('Microsoft YaHei UI', 9), padding=(12, 5), borderwidth=1,
                         relief='solid', bordercolor='#cbd5e1', background=CARD_BG)
        style.map('TButton', background=[('active', '#f1f5f9'), ('!disabled', CARD_BG)],
                  bordercolor=[('active', '#94a3b8')])
        style.configure('Primary.TButton', font=('Microsoft YaHei UI', 10, 'bold'), padding=(20, 7))
        style.configure('Small.TButton', font=('Microsoft YaHei UI', 8), padding=(8, 3))

        # LabelFrame
        style.configure('TLabelframe', background=BG, bordercolor=BORDER, relief='solid', borderwidth=1)
        style.configure('TLabelframe.Label', background=BG, foreground=TEXT_SEC, font=('Microsoft YaHei UI', 9))

        # Checkbutton
        style.configure('TCheckbutton', background=BG, foreground=TEXT_SEC)
        style.map('TCheckbutton', background=[('active', BG)])

        # Progressbar
        style.configure('TProgressbar', thickness=6, background=ACCENT, troughcolor='#e2e8f0',
                         borderwidth=0, relief='flat')

        # === Main container ===
        main = ttk.Frame(root, padding=(20, 16))
        main.pack(fill=tk.BOTH, expand=True)

        # === Title row ===
        title_row = ttk.Frame(main)
        title_row.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(title_row, text="小红书笔记 → PDF", style='Title.TLabel').pack(side=tk.LEFT)

        self.cookie_status = tk.Label(title_row, text="● Cookie: 未设置",
                                       font=("Microsoft YaHei UI", 9), fg=WARNING, bg=BG)
        self.cookie_status.pack(side=tk.RIGHT, padx=(0, 8))

        self.env_btn = tk.Button(title_row, text="● 环境检测",
                                  font=("Microsoft YaHei UI", 9), fg=WARNING, bg=BG,
                                  relief=tk.FLAT, bd=0, padx=4, cursor="hand2",
                                  command=self.check_env, activebackground='#e2e8f0')
        self.env_btn.pack(side=tk.RIGHT, padx=(0, 6))

        ttk.Button(title_row, text="?", width=3, style='Small.TButton',
                   command=self.show_cookie_help).pack(side=tk.RIGHT)

        # === URL input card ===
        url_card = tk.Frame(main, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        url_card.pack(fill=tk.X, pady=(0, 10))

        url_inner = tk.Frame(url_card, bg=CARD_BG, padx=12, pady=10)
        url_inner.pack(fill=tk.X)

        tk.Label(url_inner, text="粘贴小红书链接或分享文本", font=("Microsoft YaHei UI", 10, "bold"),
                 bg=CARD_BG, fg=TEXT).pack(anchor=tk.W)
        tk.Label(url_inner, text="自动识别短链接和完整链接", font=("Microsoft YaHei UI", 8),
                 bg=CARD_BG, fg=TEXT_SEC).pack(anchor=tk.W, pady=(0, 6))

        self.url_entry = tk.Text(url_inner, height=3, font=("Microsoft YaHei UI", 10), wrap=tk.WORD,
                                  relief=tk.FLAT, borderwidth=1, padx=8, pady=6,
                                  bg='#f8fafc', fg=TEXT, insertbackground=TEXT,
                                  highlightthickness=1, highlightbackground='#cbd5e1',
                                  highlightcolor=ACCENT)
        self.url_entry.pack(fill=tk.X)

        # === Options row ===
        opt_frame = ttk.Frame(main)
        opt_frame.pack(fill=tk.X, pady=(0, 6))

        self.watermark_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="去除水印", variable=self.watermark_var).pack(side=tk.LEFT)

        self.show_cookie_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="Cookie设置", variable=self.show_cookie_var,
                         command=self._toggle_cookie_panel).pack(side=tk.LEFT, padx=(16, 0))

        # Output dir
        ttk.Label(opt_frame, text="输出:", style='Hint.TLabel').pack(side=tk.LEFT, padx=(16, 2))
        self.out_dir_var = tk.StringVar(value=SCRIPT_DIR)
        self.out_dir_label = tk.Label(opt_frame, text=self._short_path(SCRIPT_DIR),
                                       font=("Microsoft YaHei UI", 8), fg=TEXT_SEC, bg=BG,
                                       anchor=tk.W, cursor="hand2")
        self.out_dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.out_dir_label.bind("<Button-1>", lambda e: self._choose_out_dir())
        ttk.Button(opt_frame, text="···", width=3, style='Small.TButton',
                   command=self._choose_out_dir).pack(side=tk.RIGHT)

        # === Cookie panel ===
        self.cookie_frame = tk.Frame(main, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)

        ck_inner = tk.Frame(self.cookie_frame, bg=CARD_BG, padx=12, pady=10)
        ck_inner.pack(fill=tk.X)

        tk.Label(ck_inner, text="Cookie 设置", font=("Microsoft YaHei UI", 10, "bold"),
                 bg=CARD_BG, fg=TEXT).pack(anchor=tk.W)
        tk.Label(ck_inner, text="从浏览器 F12 → Application → Cookies 复制后粘贴到下方",
                 font=("Microsoft YaHei UI", 8), bg=CARD_BG, fg=TEXT_SEC).pack(anchor=tk.W, pady=(2, 6))

        self.cookie_text = tk.Text(ck_inner, height=3, font=("Consolas", 8), wrap=tk.WORD,
                                    relief=tk.FLAT, borderwidth=1, padx=8, pady=4,
                                    bg='#f8fafc', fg=TEXT,
                                    highlightthickness=1, highlightbackground='#cbd5e1')
        self.cookie_text.pack(fill=tk.X, pady=(0, 6))

        ck_btn_row = tk.Frame(ck_inner, bg=CARD_BG)
        ck_btn_row.pack(fill=tk.X)
        ttk.Button(ck_btn_row, text="保存", command=self._save_cookie, style='Small.TButton').pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(ck_btn_row, text="测试", command=self._test_cookie, style='Small.TButton').pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(ck_btn_row, text="打开登录页", command=lambda: webbrowser.open('https://www.xiaohongshu.com'),
                   style='Small.TButton').pack(side=tk.LEFT)

        # === Action buttons ===
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(10, 6))

        self.convert_btn = tk.Button(btn_frame, text="开始转换",
                                      font=("Microsoft YaHei UI", 12, "bold"),
                                      fg='#ffffff', bg=ACCENT, activebackground=ACCENT_HOVER,
                                      activeforeground='#ffffff',
                                      relief=tk.FLAT, bd=0, padx=28, pady=8, cursor="hand2",
                                      command=self.start_convert)
        self.convert_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.open_btn = ttk.Button(btn_frame, text="打开PDF", command=self.open_pdf, state=tk.DISABLED)
        self.open_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.open_dir_btn = ttk.Button(btn_frame, text="打开目录", command=self.open_dir, state=tk.DISABLED)
        self.open_dir_btn.pack(side=tk.LEFT)

        # === Progress bar ===
        prog_frame = ttk.Frame(main)
        self.progress = ttk.Progressbar(prog_frame, mode='determinate', maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.progress_label = ttk.Label(prog_frame, text="", width=8, style='Small.TLabel')
        self.progress_label.pack(side=tk.RIGHT)

        # === Status log (dark theme) ===
        log_frame = tk.Frame(main, bg=LOG_BG, highlightthickness=1, highlightbackground=BORDER)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        log_header = tk.Frame(log_frame, bg=LOG_BG)
        log_header.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(log_header, text="状态", font=("Microsoft YaHei UI", 9, "bold"),
                 bg=LOG_BG, fg=LOG_FG).pack(side=tk.LEFT)

        self.log_text = tk.Text(log_frame, height=5, font=("Consolas", 10), wrap=tk.WORD,
                                 relief=tk.FLAT, borderwidth=0, padx=12, pady=4,
                                 bg=LOG_BG, fg=LOG_FG, insertbackground=LOG_FG,
                                 selectbackground='#334155')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        # === Result ===
        self.result_label = tk.Label(main, text="", font=("Microsoft YaHei UI", 10, "bold"),
                                      bg=BG, fg=SUCCESS)
        self.result_label.pack(pady=(8, 0))

        self.output_path = ""

        # Init
        self._refresh_cookie_status()
        self.root.after(300, self._auto_check_env)

    def _short_path(self, path: str) -> str:
        if len(path) <= 50:
            return path
        return "..." + path[-47:]

    def _set_cookie_color(self, color: str, text: str):
        """color: 'green', 'yellow', 'red'"""
        colors = {'green': '#16a34a', 'yellow': '#d97706', 'red': '#dc2626'}
        self.cookie_status.config(text=text, fg=colors.get(color, '#d97706'))

    def _set_env_btn_color(self, color: str, text: str):
        colors = {'green': '#16a34a', 'yellow': '#d97706', 'red': '#dc2626'}
        self.env_btn.config(text=text, fg=colors.get(color, '#d97706'))

    def _refresh_cookie_status(self):
        cookie = load_cookie()
        if cookie:
            self._set_cookie_color('green', '● Cookie: 已加载')
        else:
            self._set_cookie_color('yellow', '● Cookie: 未设置')

    def _toggle_cookie_panel(self):
        if self.show_cookie_var.get():
            self.cookie_frame.pack(fill=tk.X, pady=(0, 8), before=self.convert_btn.master)
            current = load_cookie()
            self.cookie_text.delete('1.0', tk.END)
            if current:
                self.cookie_text.insert('1.0', current)
        else:
            self.cookie_frame.pack_forget()

    def _save_cookie(self):
        cookie = self.cookie_text.get('1.0', 'end-1c').strip()
        if not cookie:
            self.log("[Cookie] 输入为空，未保存")
            return
        save_cookie(cookie)
        self._refresh_cookie_status()
        self.log("[Cookie] 已保存")

    def _choose_out_dir(self):
        directory = filedialog.askdirectory(initialdir=self.out_dir_var.get(), title="选择PDF输出目录")
        if directory:
            self.out_dir_var.set(directory)
            self.out_dir_label.config(text=self._short_path(directory))

    def _test_cookie(self):
        cookie = self.cookie_text.get('1.0', 'end-1c').strip()
        if not cookie:
            cookie = load_cookie()
        if not cookie:
            self.log("[Cookie测试] 没有可测试的Cookie，请先输入")
            return
        self.log("[Cookie测试] 验证中...")
        ok = test_cookie(cookie)
        if ok:
            self._set_cookie_color('green', '● Cookie: 有效')
            self.log("[Cookie测试] Cookie 有效")
        else:
            self._set_cookie_color('red', '● Cookie: 无效')
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
        dlg.geometry("520x600")
        dlg.resizable(False, False)
        dlg.transient(self.root)

        canvas = tk.Canvas(dlg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dlg, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        scroll_frame.bind("<MouseWheel>", _on_mousewheel)
        # Also bind for all child widgets via tag
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        frame = ttk.Frame(scroll_frame, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        def title(text):
            ttk.Label(frame, text=text, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W, pady=(12, 4))

        def body(text):
            ttk.Label(frame, text=text, font=("Microsoft YaHei UI", 9), wraplength=470).pack(anchor=tk.W, padx=(8, 0))

        def step(num, text):
            ttk.Label(frame, text=f"  {num}. {text}", font=("Microsoft YaHei UI", 9), wraplength=460).pack(anchor=tk.W, padx=(8, 0))

        # === Section 0: Environment ===
        title("零、环境配置（首次使用必读）")
        body("首次启动时会自动检测 Python 依赖包是否齐全。如缺少，会弹窗提示并帮你一键安装（需联网，约 16 MB）。")
        body("如果没有任何弹窗提示，说明环境已就绪，直接使用即可。")
        body("你也可以随时点击右上角「环境检测」按钮手动检查。")

        # === Section 1: Overview ===
        title("一、工具简介")
        body("将小红书笔记中的图片按顺序下载并合并为一个 PDF 文件。支持短链接(xhslink.com)和完整链接，自动识别粘贴文本中的 URL。")

        title("二、基本使用流程")
        step(1, "复制小红书笔记的分享链接（或整段分享文本）")
        step(2, "粘贴到主界面的文本框中")
        step(3, "点击「开始转换」")
        step(4, "等待进度条走完，点击「打开PDF」查看结果")

        # === Section 3: Cookie ===
        title("三、Cookie 设置（难点）")
        body("Cookie 是你的小红书登录凭证，类似门禁卡。没有它，小红书服务器会拒绝返回笔记数据。Cookie 一般几周后过期，届时需要重新获取。")
        body("")
        body("获取 Cookie 的详细步骤：")
        step(1, "点击下方「打开小红书登录」按钮，在浏览器中打开网页")
        step(2, "扫码或手机号登录你的小红书账号")
        step(3, "登录成功后，按键盘 F12 键（部分笔记本需 Fn+F12）")
        step(4, "在开发者工具顶部找到「Application」（应用程序）标签并点击")
        step(5, "左侧列表中找到「Cookies」→ 点击展开 → 点击「www.xiaohongshu.com」")
        step(6, "右侧出现一长串键值对表格 —— 点击任意一行，Ctrl+A 全选，Ctrl+C 复制")
        step(7, "回到本工具，勾选「显示Cookie设置」")
        step(8, "在 Cookie 文本框中 Ctrl+V 粘贴，点击「保存Cookie」")
        step(9, "点击「测试Cookie」确认无误（提示\"有效\"即可）")
        body("")
        body("常见问题：")
        body("  Q: 找不到 Application 标签？")
        body("  A: F12 打开的面板如果较窄，Application 可能隐藏在 » 更多菜单中，点击即可找到。")
        body("  Q: 复制出来的内容很短（只有几十个字符）？")
        body("  A: 可能只复制了一个键值对。正确做法是点击表格区域后 Ctrl+A（全选），确保复制了所有行。")
        body("  Q: 测试 Cookie 提示\"无效\"？")
        body("  A: 可能是 Cookie 已过期。重新登录小红书后，刷新页面，再次复制 Cookie。")

        # === Section 4: Options ===
        title("四、其他功能说明")
        body("去除水印：勾选后自动裁剪图片底部 7%（小红书水印区域）。如果图片本身没有水印或有重要内容在底部，可取消勾选。")
        body("输出目录：PDF 默认保存在工具所在文件夹。点击「选择目录」可更改保存位置。")
        body("环境检测：首次使用或发给别人时，先点此按钮。自动检查 Python 依赖包，如有缺失会弹窗提示安装。")

        title("五、常见报错处理")
        body("「Cookie 已过期/无效」→ 重新获取 Cookie（见第三节）")
        body("「触发验证码」→ Cookie 失效，重新获取")
        body("「笔记不存在或已被删除」→ 该链接已失效，检查链接是否正确")
        body("「该笔记不包含图片」→ 这篇笔记是纯文字或视频，不支持转换")

        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=(16, 0))
        ttk.Button(btn_row, text="打开小红书登录", command=lambda: webbrowser.open('https://www.xiaohongshu.com')).pack(side=tk.LEFT)

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
            self.log("请输入小红书笔记链接")
            self.convert_btn.config(state=tk.NORMAL)
            return

        url = extract_url(raw_text)
        if not url:
            self.log("未识别到有效的小红书链接，请检查输入")
            self.convert_btn.config(state=tk.NORMAL)
            return

        self.log(f"识别到链接:\n  {url}\n")
        self.progress.pack(fill=tk.X, pady=(0, 4))
        self.progress_label.pack()

        remove_wm = self.watermark_var.get()
        thread = threading.Thread(target=self._do_convert, args=(url, remove_wm), daemon=True)
        thread.start()

    def _do_convert(self, url: str, remove_wm: bool):
        temp_dir = None
        try:
            cookie = load_cookie()

            self._log_thread("[1/5] 解析笔记链接...")
            self._set_progress(5)
            full_url = resolve_note_url(url)
            note_id = parse_note_id(full_url)
            self._log_thread(f"      笔记ID: {note_id}")

            self._log_thread("[2/5] 获取笔记数据...")
            self._set_progress(15)
            html = fetch_note_html(full_url, cookie)
            note_data = extract_note_data(html)
            title, image_urls = extract_note_info(note_data, note_id)
            self._log_thread(f"      标题: {title}")
            self._log_thread(f"      图片数量: {len(image_urls)} 张")
            self._set_progress(30)

            self._log_thread("[3/5] 下载图片中...")
            temp_dir = tempfile.mkdtemp(prefix='xhs2pdf_')

            def progress_cb(current, total):
                pct = 30 + int((current / total) * 50)
                self._set_progress(pct)
                self._log_thread(f"      下载中: {current}/{total}")

            image_paths = download_images(image_urls, temp_dir, progress_callback=progress_cb)
            self._set_progress(80)
            self._log_thread(f"      已下载: {len(image_paths)}/{len(image_urls)} 张")

            self._log_thread("[4/5] 生成PDF..." + (" (去水印)" if remove_wm else ""))
            out_dir = self.out_dir_var.get()
            output_path = os.path.join(out_dir, f"{title}.pdf")
            images_to_pdf(image_paths, output_path, remove_watermark=remove_wm)
            self.output_path = output_path
            self._set_progress(95)

            self._set_progress(100)
            self._log_thread(f"\n完成! PDF已保存到:\n  {output_path}")
            self._result_success(output_path)

        except CookieExpiredError as e:
            self._set_cookie_color('red', '● Cookie: 已过期')
            self._log_thread(f"\nCookie 已过期或无效！")
            self._log_thread(f"请勾选\"显示Cookie设置\"，重新粘贴有效的Cookie并保存。")
            self._result_fail("Cookie 已过期/无效，请更新Cookie")

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
            self.result_label.config(text="转换成功！", fg="#2e7d32")
            self.open_btn.config(state=tk.NORMAL)
            self.open_dir_btn.config(state=tk.NORMAL)
            self.convert_btn.config(state=tk.NORMAL)
        self.root.after(0, update)

    def _result_fail(self, err_msg: str):
        def update():
            self.progress_label.config(text="失败")
            short_msg = err_msg[:100] + ("..." if len(err_msg) > 100 else "")
            self.result_label.config(text=short_msg, fg="#c62828")
            self.convert_btn.config(state=tk.NORMAL)
        self.root.after(0, update)

    def open_pdf(self):
        if self.output_path and os.path.exists(self.output_path):
            os.startfile(self.output_path)

    def open_dir(self):
        if self.output_path:
            os.startfile(os.path.dirname(self.output_path))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
