#!/usr/bin/env python3
"""
小红书笔记图片 → PDF 转换工具

用法:
    python main.py "https://www.xiaohongshu.com/explore/xxxxx"
    python main.py "https://www.xiaohongshu.com/explore/xxxxx" --cookie "your_cookie_string"
    python main.py "https://www.xiaohongshu.com/explore/xxxxx" -o output.pdf

Cookie 获取方式:
    浏览器登录 xiaohongshu.com → F12 → Application → Cookies → 全选复制 Cookie 字符串
"""

import os
import sys
import argparse
import tempfile
import shutil

# Fix Windows console encoding for Chinese output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from src.fetcher import resolve_note_url, parse_note_id, fetch_note_html, extract_note_data, extract_note_info
from src.downloader import download_images
from src.pdf_maker import images_to_pdf


def load_cookie(cli_cookie: str = "") -> str:
    """Load cookie with priority: CLI arg > env var > cookie.txt file."""
    if cli_cookie:
        return cli_cookie

    env_cookie = os.environ.get('XHS_COOKIE', '')
    if env_cookie:
        return env_cookie

    # Try cookie.txt in the same directory as this script
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cookie_file = os.path.join(root_dir, 'cookie.txt')
    if os.path.exists(cookie_file):
        with open(cookie_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if content:
            return content

    return ""


def main():
    parser = argparse.ArgumentParser(
        description='小红书笔记 → PDF 工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py "https://www.xiaohongshu.com/explore/abc123"
  python main.py "https://xhslink.com/xyz789"
  python main.py "https://www.xiaohongshu.com/explore/abc123" -o note.pdf
  python main.py "https://www.xiaohongshu.com/explore/abc123" --cookie "a1=...; web_session=..."

Cookie 获取方式:
  1. 浏览器打开 https://www.xiaohongshu.com 并登录
  2. F12 打开开发者工具 → Application → Storage → Cookies
  3. 全选复制所有 Cookie 值，粘贴为 --cookie 参数
        """
    )
    parser.add_argument('url', help='小红书笔记链接')
    parser.add_argument('-o', '--output', help='输出PDF文件路径 (默认: 当前目录下 <标题>.pdf)')
    parser.add_argument('--cookie', help='小红书登录Cookie，用于避免反爬验证')
    parser.add_argument('--keep-temp', action='store_true', help='保留临时下载目录（调试用）')
    args = parser.parse_args()

    cookie = load_cookie(args.cookie)
    if not cookie:
        print("⚠️  未提供 Cookie，可能触发反爬验证。")
        print("   获取方式: 浏览器登录 xiaohongshu.com → F12 → Application → Cookies → 复制 Cookie 字符串")
        print("   然后用 --cookie 参数传入，或设置环境变量 XHS_COOKIE，或放到 cookie.txt 文件中")
        print()

    # Step 1: Resolve URL (follow short links, preserve xsec_token etc.)
    print(f"[1/5] 解析笔记链接...")
    try:
        full_url = resolve_note_url(args.url)
        note_id = parse_note_id(full_url)
        print(f"      笔记ID: {note_id}")
    except ValueError as e:
        print(f"  ✗ {e}")
        sys.exit(1)

    # Step 2: Fetch note page
    print(f"[2/5] 获取笔记页面...")
    try:
        html = fetch_note_html(full_url, cookie)
        note_data = extract_note_data(html)
        title, image_urls = extract_note_info(note_data, note_id)
        print(f"      标题: {title}")
        print(f"      图片数量: {len(image_urls)} 张")
    except RuntimeError as e:
        print(f"  ✗ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"  ✗ 请求失败: {e}")
        sys.exit(1)

    # Step 3: Download images
    print(f"[3/5] 下载图片中...")
    temp_dir = tempfile.mkdtemp(prefix='xhs2pdf_')
    try:
        image_paths = download_images(image_urls, temp_dir)
        print(f"      已下载: {len(image_paths)}/{len(image_urls)} 张")
    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        sys.exit(1)

    # Step 4: Generate PDF
    print(f"[4/5] 生成PDF...")
    output_path = args.output or f"{title}.pdf"
    # Ensure output is in current working dir by default
    if not os.path.isabs(output_path):
        output_path = os.path.join(os.getcwd(), output_path)
    try:
        images_to_pdf(image_paths, output_path)
    except Exception as e:
        print(f"  ✗ PDF生成失败: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        sys.exit(1)

    # Step 5: Cleanup
    print(f"[5/5] 清理临时文件...")
    if args.keep_temp:
        print(f"      临时目录已保留: {temp_dir}")
    else:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print()
    print(f"✅ 完成! PDF已保存到: {output_path}")


if __name__ == '__main__':
    main()
