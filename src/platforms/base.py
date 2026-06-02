from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class CookieExpiredError(RuntimeError):
    pass


class UnsupportedError(RuntimeError):
    pass


@dataclass
class ContentItem:
    type: str          # "text" | "image"
    data: str          # text content | image URL
    style: str = ""    # "" | "bold" | "heading" | "subheading" | "italic"
    width: int = 0
    height: int = 0


@dataclass
class NoteResult:
    title: str
    items: list = field(default_factory=list)  # list[ContentItem]


class BasePlatform(ABC):
    name: str = ""
    cookie_file: str = ""      # filename in root dir
    login_url: str = ""        # URL to open for login

    @abstractmethod
    def match(self, url: str) -> bool:
        """Return True if this platform handles the given URL."""
        ...

    @abstractmethod
    def fetch(self, url: str, cookie: str = "") -> NoteResult:
        """Fetch note content. Returns (title, list of ContentItem)."""
        ...

    def cookie_help(self) -> str:
        return "无需 Cookie" if not self.cookie_file else "浏览器登录后从 F12 → Application → Cookies 复制"
