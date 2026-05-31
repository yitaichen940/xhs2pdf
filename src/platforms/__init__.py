from src.platforms.base import BasePlatform, ContentItem, UnsupportedError, CookieExpiredError
from src.platforms.xiaohongshu import XiaohongshuPlatform
from src.platforms.zhihu import ZhihuPlatform
from src.platforms.wechat import WechatPlatform

PLATFORMS = [XiaohongshuPlatform(), ZhihuPlatform(), WechatPlatform()]


def detect_platform(url: str) -> BasePlatform:
    for p in PLATFORMS:
        if p.match(url):
            return p
    raise UnsupportedError(f"不支持的链接格式: {url}")
