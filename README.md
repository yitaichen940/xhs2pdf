# 图文笔记 → PDF

支持小红书/知乎/微信公众号，粘贴链接自动识别平台，图文按原顺序导出为 PDF。

## 使用方法

**Windows**：双击 `启动.vbs`

**Linux**：`./启动.sh`（首次运行自动安装依赖和字体）

1. 粘贴链接（小红书/知乎/微信公众号，自动识别）
2. 点击「开始转换」
3. 等待完成 → 打开 PDF

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
