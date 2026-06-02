import re
import requests
from bs4 import BeautifulSoup

from src.platforms.base import BasePlatform, ContentItem, NoteResult, CookieExpiredError

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Sec-Ch-Ua': '\"Google Chrome\";v=\"131\"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '\"Windows\"',
    'Cache-Control': 'no-cache',
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
            if len(html) < 50000:
                raise CookieExpiredError("微信页面加载不完整，请稍后重试")
            raise CookieExpiredError("未找到文章内容，链接可能已失效")

        items = self._parse_content(content)
        if not items:
            raise CookieExpiredError("文章内容为空")
        return NoteResult(title=title, items=items)

    def _parse_content(self, content) -> list:
        """Walk content DOM, emit text paragraphs and images in original order."""
        items = []
        for tag in content.find_all(['script', 'style']):
            tag.decompose()

        def _walk(el, depth=0):
            if depth > 3 or not hasattr(el, 'name') or el.name is None:
                return
            if el.name in ('script', 'style'):
                return

            if el.name == 'img':
                src = el.get('data-src') or el.get('src', '')
                if src and src.startswith('http'):
                    src = src.split('#')[0]
                    items.append(ContentItem(type='image', data=src))
                return

            if el.name in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'blockquote'):
                # Check for images directly inside
                imgs = el.find_all('img', recursive=False)
                for img in imgs:
                    src = img.get('data-src') or img.get('src', '')
                    if src and src.startswith('http'):
                        items.append(ContentItem(type='image', data=src.split('#')[0]))
                # Full text
                text = el.get_text(strip=True)
                text = re.sub(r'\s+', ' ', text).strip()
                if text and len(text) > 1 and not text.startswith('微信扫一扫'):
                    # Detect style
                    style = ''
                    if el.name in ('h1', 'h2'):
                        style = 'heading'
                    elif el.name in ('h3', 'h4'):
                        style = 'subheading'
                    items.append(ContentItem(type='text', data=text, style=style))
                return

            # For section/div/span: recurse into children but don't emit text directly
            for child in el.children:
                if hasattr(child, 'name'):
                    _walk(child, depth + 1)

        for child in content.children:
            _walk(child, 0)

        return items
