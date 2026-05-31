import os
from PIL import Image


def images_to_pdf(image_paths: list[str], output_path: str, remove_watermark: bool = True):
    """Combine images into a single PDF, one image per page."""
    if not image_paths:
        raise ValueError("没有图片可合并为PDF。")

    images = []
    for path in image_paths:
        try:
            img = Image.open(path)
            if remove_watermark:
                img = _crop_watermark(img)
            if img.mode in ('RGBA', 'P', 'LA', 'PA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
        except Exception as e:
            print(f"  [警告] 无法打开图片 {path}: {e}")
            continue

    if not images:
        raise ValueError("没有可用的图片可合并为PDF。")

    first = images[0]
    rest = images[1:]
    first.save(
        output_path, 'PDF', save_all=True,
        append_images=rest, resolution=100.0
    )
    print(f"  PDF已生成: {output_path} ({len(images)} 页)")


def _crop_watermark(img: Image.Image) -> Image.Image:
    """Crop bottom portion where Xiaohongshu watermark typically sits (~7% of height)."""
    w, h = img.size
    # Only crop if the image is tall enough (don't crop very short images)
    if h < 400:
        return img
    crop_px = int(h * 0.07)
    return img.crop((0, 0, w, h - crop_px))
