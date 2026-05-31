import re
import json
import requests
from bs4 import BeautifulSoup

from src.platforms.base import BasePlatform, ContentItem, NoteResult, CookieExpiredError

API_HEADERS_BASE = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'x-api-version': '3.0.40',
    'x-requested-with': 'fetch',
}

HTML_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
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
        if not cookie:
            raise CookieExpiredError("知乎需要登录凭证(Cookie)")

        qid = self._extract_qid(url)
        aid = self._extract_aid(url)
        api_headers = dict(API_HEADERS_BASE, **{'Cookie': cookie, 'Referer': url})
        html_headers = dict(HTML_HEADERS, **{'Cookie': cookie})

        # Get question info
        title = 'untitled'
        question_detail = ''
        if qid:
            try:
                q_resp = requests.get(
                    f'https://www.zhihu.com/api/v4/questions/{qid}',
                    headers=api_headers, timeout=10
                )
                if q_resp.status_code == 200:
                    q_data = q_resp.json()
                    title = q_data.get('title', 'untitled')
                    question_detail = q_data.get('detail', '') or ''
            except Exception:
                pass

        # Get answers
        content_html = ''
        if aid:
            # Single answer
            try:
                a_resp = requests.get(
                    f'https://www.zhihu.com/api/v4/answers/{aid}',
                    headers=api_headers, timeout=10
                )
                if a_resp.status_code == 200:
                    a_data = a_resp.json()
                    content_html = a_data.get('content', '')
                    if not title or title == 'untitled':
                        title = a_data.get('question', {}).get('title', 'untitled')
            except Exception:
                pass
        elif qid:
            # Question page - get top answers
            try:
                a_resp = requests.get(
                    f'https://www.zhihu.com/api/v4/questions/{qid}/answers',
                    params={'limit': 5, 'include': 'data[*].content'},
                    headers=api_headers, timeout=10
                )
                if a_resp.status_code == 200:
                    answers = a_resp.json().get('data', [])
                    contents = []
                    for ans in answers:
                        c = ans.get('content', '')
                        if c:
                            contents.append(c)
                    content_html = '\n'.join(contents)
            except Exception:
                pass

        # Fallback: try HTML extraction
        if not content_html:
            try:
                resp = requests.get(url, headers=html_headers, timeout=15)
                data = self._extract_state(resp.text)
                result = self._parse_state(data)
                if result.title != 'untitled':
                    title = result.title
                content_html = self._find_content_in_data(data)
            except Exception:
                pass

        if not content_html and question_detail:
            content_html = question_detail
        if not content_html:
            raise CookieExpiredError("未找到知乎内容，该问题可能没有回答")

        title = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', title).strip()[:80] or 'untitled'

        # Build items: question detail first, then answers
        items = []
        if question_detail:
            detail_text = BeautifulSoup(question_detail, 'html.parser').get_text(strip=True)
            if detail_text:
                items.append(ContentItem(type='text', data=f"问题描述: {detail_text}"))

        items.extend(self._parse_html(content_html))
        if not items:
            raise CookieExpiredError("未找到可导出的内容")
        return NoteResult(title=title, items=items)

    def _extract_qid(self, url: str) -> str:
        m = re.search(r'/question/(\d+)', url)
        return m.group(1) if m else ''

    def _extract_aid(self, url: str) -> str:
        m = re.search(r'/answer/(\d+)', url)
        return m.group(1) if m else ''

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
        for script in soup.find_all('script', id='js-initialData'):
            try:
                return json.loads(script.string)
            except Exception:
                pass
        return {}

    def _parse_state(self, data: dict) -> NoteResult:
        article = data.get('article', {})
        if article and article.get('content'):
            title = article.get('title', 'untitled')
            items = self._parse_html(article['content'])
            return NoteResult(title=title, items=items)
        return NoteResult(title='untitled', items=[])

    def _find_content_in_data(self, data: dict, depth: int = 0) -> str:
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
