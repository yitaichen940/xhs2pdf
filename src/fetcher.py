"""Backward compatibility: re-export from platforms module."""
from src.platforms.base import CookieExpiredError
from src.platforms.xiaohongshu import XiaohongshuPlatform

_platform = XiaohongshuPlatform()


def resolve_note_url(url: str) -> str:
    return _platform._resolve(url)


def parse_note_id(url: str) -> str:
    return _platform._parse_id(url)


def fetch_note_html(full_url: str, cookie: str = "") -> str:
    return _platform._fetch_html(full_url, cookie)


def extract_note_data(html: str) -> dict:
    return _platform._extract_state(html)


def extract_note_info(note_data: dict, note_id: str):
    result = _platform._parse_note(note_data, note_id)
    urls = [item.data for item in result.items if item.type == 'image']
    return result.title, urls
