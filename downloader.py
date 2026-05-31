import os
import time
import requests
from typing import Callable, Optional

IMG_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Referer': 'https://www.xiaohongshu.com/',
}


def download_images(
    urls: list[str],
    dest_dir: str,
    max_retries: int = 3,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    """Download images sequentially. Calls progress_callback(current, total) after each."""
    os.makedirs(dest_dir, exist_ok=True)
    saved = []
    total = len(urls)

    for i, url in enumerate(urls, 1):
        ext = _guess_ext(url)
        filename = f"{i:03d}{ext}"
        filepath = os.path.join(dest_dir, filename)

        success = _download_with_retry(url, filepath, max_retries)
        if success:
            saved.append(filepath)
        else:
            print(f"  [警告] 第 {i} 张图片下载失败，已跳过: {url[:80]}...")
            _create_error_placeholder(filepath, i)
            saved.append(filepath)

        if progress_callback:
            progress_callback(i, total)

    return saved


def _guess_ext(url: str) -> str:
    url_clean = url.split('?')[0]
    for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
        if ext in url_clean.lower():
            return ext
    return '.jpg'


def _download_with_retry(url: str, filepath: str, max_retries: int) -> bool:
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=IMG_HEADERS, timeout=30)
            resp.raise_for_status()
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  [错误] 下载失败 (重试{max_retries}次): {e}")
                return False
    return False


def _create_error_placeholder(filepath: str, index: int):
    try:
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (800, 600), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.text((400, 280), f"Image {index} download failed", fill=(180, 180, 180))
        img.save(filepath)
    except Exception:
        pass
