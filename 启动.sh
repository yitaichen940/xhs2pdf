#!/bin/bash
set -e
cd "$(dirname "$0")"

# ── Check Python ──
if ! command -v python3 &>/dev/null; then
    echo ">>> 安装 Python3..."
    sudo apt update -qq && sudo apt install -y -qq python3 python3-pip
fi

# ── Install Python packages ──
if ! python3 -c "import requests, PIL, tqdm, bs4, fpdf" 2>/dev/null; then
    echo ">>> 安装 Python 依赖..."
    pip3 install --quiet requests Pillow tqdm beautifulsoup4 fpdf2
fi

# ── Check Chinese font ──
FONT_FOUND=0
for f in /usr/share/fonts/truetype/wqy/wqy-zenhei.ttc \
         /usr/share/fonts/truetype/wqy/wqy-microhei.ttc \
         /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
         /usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc; do
    if [ -f "$f" ]; then
        FONT_FOUND=1
        break
    fi
done
if [ $FONT_FOUND -eq 0 ]; then
    echo ">>> 安装中文字体..."
    sudo apt install -y -qq fonts-wqy-zenhei 2>/dev/null || \
    sudo apt install -y -qq fonts-wqy-microhei 2>/dev/null || \
    echo "（字体安装失败，PDF 中文可能显示异常）"
fi

# ── Launch ──
echo ">>> 启动..."
python3 -m src.main
