import os
import re
from PIL import Image
from fpdf import FPDF

# System Chinese font
_FONT_PATH = r'C:\Windows\Fonts\simhei.ttf'
if not os.path.exists(_FONT_PATH):
    _FONT_PATH = r'C:\Windows\Fonts\msyh.ttc'


def content_to_pdf(items: list, image_path_map: dict, title: str,
                   output_path: str, remove_watermark: bool = True):
    """Create a mixed text+image PDF from ContentItems."""
    if not items:
        raise ValueError("没有内容可合并为PDF。")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font('zh', '', _FONT_PATH)
    pdf.add_font('zh', 'B', _FONT_PATH)

    pdf.add_page()
    # Title
    pdf.set_font('zh', 'B', 18)
    pdf.multi_cell(0, 12, title, align='L')
    pdf.ln(4)

    for item in items:
        if item.type == 'text':
            pdf.set_font('zh', '', 11)
            # Clean text
            text = item.data
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                pdf.multi_cell(0, 7, text)
                pdf.ln(2)

        elif item.type == 'image':
            local_path = image_path_map.get(item.data, '')
            if not local_path or not os.path.exists(local_path):
                continue
            try:
                if remove_watermark:
                    img = _crop_watermark(Image.open(local_path))
                    tmp = local_path + '.tmp.jpg'
                    img.save(tmp, 'JPEG', quality=90)
                    local_path = tmp

                # Fit image to page width
                pdf.image(local_path, x=10, w=pdf.w - 20)
                pdf.ln(4)

                if remove_watermark:
                    os.remove(local_path)
            except Exception as e:
                print(f"  [警告] 图片嵌入失败: {e}")

    # Remove existing file to avoid permission issues
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass
    pdf.output(output_path)
    print(f"  PDF已生成: {output_path}")


def images_to_pdf(image_paths: list[str], output_path: str, remove_watermark: bool = True):
    """Legacy: combine images only, one per page (for backward compat)."""
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
    first.save(output_path, 'PDF', save_all=True, append_images=rest, resolution=100.0)
    print(f"  PDF已生成: {output_path} ({len(images)} 页)")


def _crop_watermark(img: Image.Image) -> Image.Image:
    w, h = img.size
    if h < 400:
        return img
    crop_px = int(h * 0.07)
    return img.crop((0, 0, w, h - crop_px))
