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
                    data = json.loads(json_str)
                    # Check if it has actual content
                    if data.get('article') or data.get('question'):
                        return data
        # Try alternative: js-initialData
        for script in soup.find_all('script', id='js-initialData'):
            try:
                return json.loads(script.string)
            except Exception:
                pass
        raise CookieExpiredError("无法提取知乎页面数据，可能需要重新获取Cookie")

    def _parse_content(self, data: dict) -> NoteResult:
        title = ''
        content_html = ''

        # Article (zhuanlan.zhihu.com/p/xxx)
        article = data.get('article', {})
        if article:
            title = article.get('title', '')
            content_html = article.get('content', '')

        # Question page
        if not title:
            question = data.get('question', {})
            title = question.get('title', '')
            # Try question detail HTML
            if question.get('detail'):
                content_html = question.get('detail', '')
            # Try first answer
            answers = data.get('answers') or data.get('question', {}).get('answers') or []
            if isinstance(answers, list) and answers:
                first = answers[0]
                if isinstance(first, dict) and first.get('content'):
                    if content_html:
                        content_html += first['content']
                    else:
                        content_html = first['content']
            elif isinstance(answers, dict):
                answer_list = answers.get('data') or answers.get('list') or []
                if isinstance(answer_list, list) and answer_list:
                    ans = answer_list[0]
                    if isinstance(ans, dict) and ans.get('content'):
                        if content_html:
                            content_html += ans['content']
                        else:
                            content_html = ans['content']

        if not title:
            # Fallback: try to find title in any field
            for key in data:
                v = data[key]
                if isinstance(v, dict) and v.get('title'):
                    title = v['title']
                    break
            if not title:
                title = 'untitled'
        if not content_html:
            # If no content HTML found, try to extract at least images from the whole data
            content_html = self._find_content_in_data(data)
        if not content_html:
            raise CookieExpiredError("未找到知乎文章内容")

        title = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', title).strip()[:80] or 'untitled'
        items = self._parse_html(content_html)
        return NoteResult(title=title, items=items)

    def _find_content_in_data(self, data: dict, depth: int = 0) -> str:
        """Recursively search for 'content' field in nested data."""
        if depth > 5:
            return ''
        if isinstance(data, dict):
            if 'content' in data and isinstance(data['content'], str) and len(data['content']) > 100:
                return data['content']
            for v in data.values():
                result = self._find_content_in_data(v, depth + 1)
                if result:
                    return result
        return ''

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
