from __future__ import annotations
import os
import re
from PIL import Image
from fpdf import FPDF

# System Chinese font
_FONT_PATHS = [
    r'C:\Windows\Fonts\simhei.ttf',
    r'C:\Windows\Fonts\msyh.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
]
_FONT_PATH = next((p for p in _FONT_PATHS if os.path.exists(p)), _FONT_PATHS[0])


def content_to_pdf(items: list, image_path_map: dict, title: str,
                   output_path: str, remove_watermark: bool = True,
                   crop_top: int = 0, crop_bot: int = 7):
    """Create a mixed text+image PDF from ContentItems."""
    if not items:
        raise ValueError("没有内容可合并为PDF。")

    pdf = FPDF()
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font('zh', '', _FONT_PATH)
    pdf.add_font('zh', 'B', _FONT_PATH)

    pdf.add_page()
    # Title
    pdf.set_font('zh', 'B', 18)
    pdf.multi_cell(0, 12, title, align='L')
    pdf.ln(4)

    had_text = False
    for item in items:
        if item.type == 'text':
            had_text = True
            # Apply style
            style = getattr(item, 'style', '')
            if style == 'heading':
                pdf.set_font('zh', 'B', 16)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 10, item.data.strip())
                pdf.ln(4)
                continue
            elif style == 'subheading':
                pdf.set_font('zh', 'B', 13)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 8, item.data.strip())
                pdf.ln(2)
                continue
            elif style == 'bold':
                pdf.set_font('zh', 'B', 11)
            elif style == 'italic':
                pdf.set_font('zh', '', 11)
            else:
                pdf.set_font('zh', '', 11)

            text = item.data.strip()
            if not text:
                continue
            # Remove unsupported characters (emojis, special Unicode)
            text = text.encode('gbk', errors='ignore').decode('gbk')
            if not text.strip():
                continue
            # Clean: normalize newlines, remove excessive space per line
            text = re.sub(r'[ \t]+', ' ', text)    # collapse horizontal whitespace
            text = re.sub(r'\n{3,}', '\n\n', text)  # max 2 consecutive newlines
            # Split into paragraphs
            for para in text.split('\n'):
                para = para.strip()
                if not para:
                    pdf.ln(4)
                    continue
                pdf.set_x(pdf.l_margin)  # ensure we're at left margin
                try:
                    pdf.multi_cell(0, 7, para)
                except RuntimeError:
                    pdf.set_font('zh', '', 8)
                    pdf.set_x(pdf.l_margin)
                    try:
                        pdf.multi_cell(0, 5, para)
                    except RuntimeError:
                        pass
                    pdf.set_font('zh', '', 11)
            pdf.ln(2)

        elif item.type == 'image':
            # Page break between text and images (for XHS etc.)
            if had_text:
                pdf.add_page()
                had_text = False

            local_path = image_path_map.get(item.data, '')
            if not local_path or not os.path.exists(local_path):
                continue
            try:
                if remove_watermark:
                    img = _crop_watermark(Image.open(local_path), crop_top, crop_bot)
                    if img.mode in ('RGBA', 'P', 'LA', 'PA'):
                        bg = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = bg
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    tmp = local_path + '.tmp.jpg'
                    img.save(tmp, 'JPEG', quality=90)
                    local_path = tmp

                # Fit image within content area
                content_w = pdf.w - pdf.l_margin - pdf.r_margin
                pdf.image(local_path, x=pdf.l_margin, w=content_w)
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


def images_to_pdf(image_paths: list[str], output_path: str, remove_watermark: bool = True,
                  crop_top: int = 0, crop_bot: int = 7):
    """Legacy: combine images only, one per page (for backward compat)."""
    if not image_paths:
        raise ValueError("没有图片可合并为PDF。")

    images = []
    for path in image_paths:
        try:
            img = Image.open(path)
            if remove_watermark:
                img = _crop_watermark(img, crop_top, crop_bot)
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


def _crop_watermark(img: Image.Image, crop_top: int = 0, crop_bot: int = 7) -> Image.Image:
    w, h = img.size
    if h < 400:
        return img
    top_px = int(h * crop_top / 100)
    bot_px = int(h * crop_bot / 100)
    return img.crop((0, top_px, w, h - bot_px))
