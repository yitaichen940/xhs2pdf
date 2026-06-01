# 图文笔记 → PDF

支持小红书/知乎/微信公众号，粘贴链接自动识别平台，图文按原顺序导出为 PDF。

## 使用方法

**Windows**：双击 `启动.bat`（`.vbs` 备用）

**Linux**：`chmod +x 启动.sh && ./启动.sh`（首次运行自动安装依赖和字体）

1. 粘贴链接（小红书/知乎/微信公众号，自动识别）
2. 点击「开始转换」
3. 等待完成 → 打开 PDF

## Cookie 配置

**小红书 / 知乎** 需要登录凭证才能访问内容（微信公众号无需）：

1. 浏览器打开对应网站并登录
2. 按 `F12` → `Application` → `Cookies`
3. 全选右侧 Cookie → 复制
4. 回到工具，勾选「Cookie」→ 粘贴 → 保存

Cookie 约几周后过期，届时重新获取即可。

## 环境要求

**Windows**：需提前安装 Python 3.7+（[下载](https://www.python.org/downloads/)，安装时勾选 `Add to PATH`）。如未安装，启动时会自动打开下载页。

**Linux**：无需提前准备，`启动.sh` 自动安装所有依赖。

## 项目结构

```
xhs2pdf/
├── 启动.bat          # Windows 启动器 (推荐)
├── 启动.vbs          # Windows 启动器 (备用)
├── 启动.sh           # Linux 启动器
├── cookie_xhs.txt    # 小红书 Cookie
├── cookie_zhihu.txt  # 知乎 Cookie
├── output/           # PDF 输出目录
└── src/              # 源码
```

## License

MIT
