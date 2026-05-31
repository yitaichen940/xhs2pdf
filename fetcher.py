import re

class CookieExpiredError(RuntimeError):
    """Raised when the cookie is expired or invalid."""
    pass

import json
import requests
from bs4 import BeautifulSoup

HEADERS_TEMPLATE = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://www.xiaohongshu.com/',
}


def resolve_note_url(url: str) -> str:
    """Resolve short links and return the full URL with all query parameters (xsec_token etc)."""
    if 'xhslink.com' in url:
        resp = requests.get(url, headers=HEADERS_TEMPLATE, allow_redirects=True, timeout=15)
        url = resp.url
    return url


def parse_note_id(url: str) -> str:
    """Extract note_id from various Xiaohongshu URL formats."""
    for pattern in [r'/explore/([a-zA-Z0-9]+)', r'/discovery/item/([a-zA-Z0-9]+)']:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    raise ValueError(f"无法从URL中解析出笔记ID: {url}")


def fetch_note_html(full_url: str, cookie: str = "") -> str:
    """Fetch the note detail page HTML using the full URL (with xsec_token etc)."""
    headers = dict(HEADERS_TEMPLATE)
    if cookie:
        headers['Cookie'] = cookie

    resp = requests.get(full_url, headers=headers, timeout=15)
    resp.raise_for_status()

    if '请通过验证' in resp.text or '滑动验证' in resp.text or '有安全风险' in resp.text:
        raise CookieExpiredError("触发小红书验证码")
    if 'login' in resp.text and 'password' in resp.text.lower() and len(resp.text) < 2000:
        raise CookieExpiredError("Cookie 已过期，页面重定向到登录")
    return resp.text


def extract_note_data(html: str) -> dict:
    """Extract window.__INITIAL_STATE__ JSON from the page HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script'):
        if script.string and '__INITIAL_STATE__' in script.string:
            text = script.string
            idx = text.find('__INITIAL_STATE__')
            if idx == -1:
                continue
            eq_idx = text.find('=', idx)
            if eq_idx == -1:
                continue
            brace_start = text.find('{', eq_idx)
            if brace_start == -1:
                continue
            json_str = _extract_json_by_braces(text, brace_start)
            if json_str:
                json_str = re.sub(r'(?<!\w)undefined(?!\w)', 'null', json_str)
                return json.loads(json_str)

    raise RuntimeError(
        "无法从页面中提取笔记数据，可能需要提供有效的 Cookie。\n"
        "获取方式: 浏览器登录 xiaohongshu.com → F12 → Application → Cookies → 复制完整 Cookie 字符串"
    )


def _extract_json_by_braces(text: str, start: int) -> str:
    """Extract a JSON object string by counting braces from start position."""
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def extract_note_info(note_data: dict, note_id: str) -> tuple[str, list[str]]:
    """Return (title, ordered_image_urls) from parsed __INITIAL_STATE__ data."""
    detail_map = note_data.get('note', {}).get('noteDetailMap', {})

    # Try with the given note_id first, then fall back to any key
    note = detail_map.get(note_id, {}).get('note', {})
    if not note:
        # The note_id might not match; try all keys
        for key in detail_map:
            candidate = detail_map[key].get('note', {})
            if candidate and candidate.get('noteId') == note_id:
                note = candidate
                break
        # If still not found, try any entry that has a title
        if not note:
            for key in detail_map:
                candidate = detail_map[key].get('note', {})
                if candidate and candidate.get('title'):
                    note = candidate
                    break

    if not note:
        # Empty noteDetailMap usually means cookie expired, not note not found
        if len(detail_map) == 0 or all(
            not isinstance(v, dict) or not v.get('note') or (isinstance(v.get('note'), dict) and not v['note'])
            for v in detail_map.values()
        ):
            raise CookieExpiredError(
                "Cookie 已过期或无效，页面未返回笔记数据。"
            )
        raise RuntimeError(
            f"笔记 {note_id} 不存在或已被删除/设为私密。"
        )

    title = note.get('title', '') or note.get('desc', 'untitled')
    title = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', title).strip()[:80]
    if not title:
        title = 'untitled'

    image_list = note.get('imageList', [])
    if not image_list:
        raise RuntimeError("该笔记不包含图片（可能是纯文字或视频笔记）。")

    urls = []
    for img in image_list:
        url = img.get('url') or img.get('urlDefault') or img.get('urlPre', '')
        if url:
            urls.append(url)

    if not urls:
        raise RuntimeError("无法解析图片URL。")

    return title, urls
