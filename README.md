# 小红书笔记 → PDF 转换工具

输入小红书链接，自动下载笔记内所有图片，按顺序合并为 PDF。

## 使用方法

1. 双击 `启动.vbs`
2. 粘贴小红书笔记链接（支持短链接、完整链接、复制整段分享文本）
3. 点击「开始转换」
4. 等待完成 → 打开 PDF

## 首次使用

启动时会自动检测 Python 依赖，缺失会弹窗一键安装（约 16 MB）。

## Cookie 配置

首次使用需配置小红书 Cookie（登录凭证）：

1. 浏览器打开 https://www.xiaohongshu.com 并登录
2. 按 `F12` → `Application` → `Cookies` → `www.xiaohongshu.com`
3. 全选右侧 Cookie → 复制
4. 回到工具，勾选「Cookie」→ 粘贴 → 保存

Cookie 约几周后过期，届时重新获取即可。

## 环境要求

- Python 3.8+
- 依赖自动安装，无需手动操作

## 项目结构

```
xhs2pdf/
├── 启动.vbs          # 启动器
├── cookie.txt        # Cookie 配置
├── output/           # PDF 输出目录
└── src/              # 源码
```

## License

MIT
