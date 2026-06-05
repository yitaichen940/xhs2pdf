import re
import json
import requests
from bs4 import BeautifulSoup

from src.platforms.base import BasePlatform, ContentItem, NoteResult, CookieExpiredError

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


class XiaohongshuPlatform(BasePlatform):
    name = "小红书"
    cookie_file = "cookie_xhs.txt"
    login_url = "https://www.xiaohongshu.com"

    def match(self, url: str) -> bool:
        return bool(re.search(r'(xhslink\.com|xiaohongshu\.com)', url))

    def cookie_help(self) -> str:
        return ("浏览器登录 xiaohongshu.com → F12 → Application → Cookies\n"
                "→ www.xiaohongshu.com → 全选复制 → 粘贴到Cookie设置")

    def fetch(self, url: str, cookie: str = "") -> NoteResult:
        full_url = self._resolve(url)
        note_id = self._parse_id(full_url)
        html = self._fetch_html(full_url, cookie)
        data = self._extract_state(html)
        return self._parse_note(data, note_id)

    def _resolve(self, url: str) -> str:
        if 'xhslink.com' in url:
            resp = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=15)
            url = resp.url
        return url

    def _parse_id(self, url: str) -> str:
        m = re.search(r'/(?:explore|discovery/item)/([a-zA-Z0-9]+)', url)
        if m:
            return m.group(1)
        raise CookieExpiredError(f"无法从URL解析笔记ID: {url}")

    def _fetch_html(self, full_url: str, cookie: str) -> str:
        headers = dict(HEADERS)
        if cookie:
            headers['Cookie'] = cookie
        resp = requests.get(full_url, headers=headers, timeout=15)
        resp.raise_for_status()
        if any(kw in resp.text for kw in ['请通过验证', '滑动验证', '有安全风险']):
            raise CookieExpiredError("触发小红书验证码")
        return resp.text

    def _extract_state(self, html: str) -> dict:
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup.find_all('script'):
            if script.string and '__INITIAL_STATE__' in script.string:
                text = script.string
                idx = text.find('__INITIAL_STATE__')
                eq_idx = text.find('=', idx)
                brace_start = text.find('{', eq_idx)
                json_str = _extract_braces(text, brace_start)
                if json_str:
                    json_str = re.sub(r'(?<!\w)undefined(?!\w)', 'null', json_str)
                    return json.loads(json_str)
        raise CookieExpiredError("无法提取笔记数据，Cookie可能已过期")

    def _parse_note(self, data: dict, note_id: str) -> NoteResult:
        detail_map = data.get('note', {}).get('noteDetailMap', {})
        note = detail_map.get(note_id, {}).get('note', {})
        if not note:
            for key in detail_map:
                candidate = detail_map[key].get('note', {})
                if candidate.get('title'):
                    note = candidate
                    break
        if not note:
            # Empty noteDetailMap = cookie expired
            if not detail_map or all(
                not (isinstance(v, dict) and v.get('note') and isinstance(v['note'], dict) and v['note'])
                for v in detail_map.values()
            ):
                raise CookieExpiredError("Cookie已过期，页面未返回笔记数据")
            raise CookieExpiredError(f"笔记 {note_id} 不存在或已删除")

        title = note.get('title', '') or note.get('desc', 'untitled')
        title = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', title).strip()[:80] or 'untitled'

        items = []
        # Add images in order
        for img in note.get('imageList', []):
            url = img.get('url') or img.get('urlDefault') or img.get('urlPre', '')
            if url:
                items.append(ContentItem(
                    type='image', data=url,
                    width=img.get('width', 0), height=img.get('height', 0)
                ))

        if not items:
            raise CookieExpiredError("该笔记不包含图片")
        return NoteResult(title=title, items=items)


def _extract_braces(text: str, start: int) -> str:
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
