import re
import json
import requests
from bs4 import BeautifulSoup

from src.platforms.base import BasePlatform, ContentItem, NoteResult, CookieExpiredError

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
    'Sec-Ch-Ua': '"Google Chrome";v="131"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
}


class ZhihuPlatform(BasePlatform):
    name = "知乎"
    cookie_file = "cookie_zhihu.txt"

    def match(self, url: str) -> bool:
        return 'zhihu.com' in url

    def cookie_help(self) -> str:
        return ("浏览器登录 zhihu.com → F12 → Application → Cookies\n"
                "→ .zhihu.com → 全选复制 → 粘贴到Cookie设置")

    def fetch(self, url: str, cookie: str = "") -> NoteResult:
        headers = dict(HEADERS)
        if cookie:
            headers['Cookie'] = cookie
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 403:
            if not cookie:
                raise CookieExpiredError("知乎需要登录凭证(Cookie)，请在Cookie设置中配置知乎Cookie")
            raise CookieExpiredError("知乎Cookie已过期或无效，请重新获取")
        resp.raise_for_status()
        html = resp.text
        data = self._extract_state(html)
        return self._parse_content(data)

    def _extract_state(self, html: str) -> dict:
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup.find_all('script'):
            if script.string and '__INITIAL_STATE__' in script.string:
                text = script.string
                idx = text.find('__INITIAL_STATE__')
                eq_idx = text.find('=', idx)
                brace_start = text.find('{', eq_idx)
                if brace_start == -1:
                    continue
                json_str = _extract_braces(text, brace_start)
                if json_str:
                    json_str = re.sub(r'(?<!\w)undefined(?!\w)', 'null', json_str)
                    return json.loads(json_str)
        raise CookieExpiredError("无法提取知乎页面数据")

    def _parse_content(self, data: dict) -> NoteResult:
        # Try article first, then answer
        content_html = ''
        title = ''

        # Article (zhuanlan.zhihu.com/p/xxx)
        article = data.get('article', {})
        if article:
            title = article.get('title', '')
            content_html = article.get('content', '')

        # Answer (question/xxx/answer/xxx)
        if not content_html:
            answers = data.get('answer', {}) or data
            # Try different paths
            for path in ['answer', 'answers', 'question.answers']:
                ans_data = data
                for key in path.split('.'):
                    ans_data = ans_data.get(key, {}) if isinstance(ans_data, dict) else {}
                if isinstance(ans_data, dict) and ans_data.get('content'):
                    content_html = ans_data.get('content', '')
                    break
            if not title:
                title = data.get('question', {}).get('title', '')

        if not content_html:
            raise CookieExpiredError("未找到知乎文章内容，可能需要登录")

        title = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', title).strip()[:80] or 'untitled'
        items = self._parse_html(content_html)
        return NoteResult(title=title, items=items)

    def _parse_html(self, html: str) -> list:
        """Extract text paragraphs and images from content HTML in order."""
        items = []
        soup = BeautifulSoup(html, 'html.parser')

        for el in soup.descendants:
            if el.name in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'blockquote'):
                text = el.get_text(strip=True)
                if text and len(text) > 1:
                    items.append(ContentItem(type='text', data=text))
            elif el.name == 'img':
                src = el.get('data-original') or el.get('src') or el.get('data-actualsrc', '')
                if src and src.startswith('http'):
                    items.append(ContentItem(type='image', data=src))
            elif el.name == 'figure':
                img = el.find('img')
                if img:
                    src = img.get('data-original') or img.get('src') or img.get('data-actualsrc', '')
                    if src and src.startswith('http'):
                        items.append(ContentItem(type='image', data=src))

        if not items:
            # Fallback: extract all images at least
            for img in soup.find_all('img'):
                src = img.get('data-original') or img.get('src') or img.get('data-actualsrc', '')
                if src and src.startswith('http') and 'zhimg' in src:
                    items.append(ContentItem(type='image', data=src))

        return items


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
