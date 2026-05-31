import re
import requests
from bs4 import BeautifulSoup

from src.platforms.base import BasePlatform, ContentItem, NoteResult, CookieExpiredError

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


class WechatPlatform(BasePlatform):
    name = "微信公众号"
    cookie_file = ""  # No cookie needed
    login_url = "https://mp.weixin.qq.com"

    def match(self, url: str) -> bool:
        return 'mp.weixin.qq.com' in url

    def fetch(self, url: str, cookie: str = "") -> NoteResult:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return self._parse(resp.text)

    def _parse(self, html: str) -> NoteResult:
        soup = BeautifulSoup(html, 'html.parser')

        # Title
        title_el = soup.find('h1', class_='rich_media_title') or soup.find('title')
        title = title_el.get_text(strip=True) if title_el else 'untitled'
        title = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', title).strip()[:80] or 'untitled'

        # Content
        content = soup.find('div', id='js_content') or soup.find('div', class_='rich_media_content')
        if not content:
            raise CookieExpiredError("未找到文章内容，链接可能已失效")

        items = self._parse_content(content)
        if not items:
            raise CookieExpiredError("文章内容为空")
        return NoteResult(title=title, items=items)

    def _parse_content(self, content) -> list:
        """Walk content DOM, emit text paragraphs and images in order."""
        items = []
        # Remove script/style
        for tag in content.find_all(['script', 'style']):
            tag.decompose()

        for el in content.descendants:
            if el.name in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'blockquote', 'span', 'section'):
                # Skip if contains only images
                if el.name == 'section' and el.find('img'):
                    continue
                text = el.get_text(strip=True)
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                if text and len(text) > 1 and not text.startswith('微信扫一扫'):
                    # Avoid duplicates from nested tags
                    if el.find('p') or el.find('span'):
                        continue
                    items.append(ContentItem(type='text', data=text))
            elif el.name == 'img':
                src = el.get('data-src') or el.get('src', '')
                if src and src.startswith('http'):
                    # Clean: remove fragment, normalize
                    src = src.split('#')[0]
                    items.append(ContentItem(type='image', data=src))

        return items
