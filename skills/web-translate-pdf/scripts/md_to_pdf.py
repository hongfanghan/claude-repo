"""
Markdown 转 PDF 辅助脚本（图片下载 + base64 嵌入，完全离线）

核心特性：
- 自动下载 Markdown 中的远程图片到本地
- 将图片转为 base64 嵌入 HTML，生成完全离线的 PDF
- 保留原始高清分辨率

用法：
    python md_to_pdf.py <input.md> <output.pdf> [--title 标题] [--images-dir 图片保存目录]

依赖：
    pip install mistune playwright requests
    playwright install chromium
"""

import sys
import os
import re
import argparse
import hashlib
import base64
import mimetypes
import requests
import mistune
from playwright.sync_api import sync_playwright

PDF_CSS = """
body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC",
                 "Helvetica Neue", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.7;
    color: #1a1a1a;
    max-width: 100%;
    padding: 0;
    margin: 0;
}
h1.page-title {
    font-size: 22pt;
    color: #d97706;
    border-bottom: 3px solid #d97706;
    padding-bottom: 8px;
    margin-bottom: 20px;
}
h2 {
    font-size: 16pt;
    color: #1e40af;
    margin-top: 24px;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 6px;
}
h3 {
    font-size: 13pt;
    color: #374151;
    margin-top: 18px;
}
h4 {
    font-size: 12pt;
    color: #4b5563;
    margin-top: 14px;
}
h5, h6 {
    font-size: 11pt;
    color: #6b7280;
    margin-top: 12px;
}
code {
    background-color: #f3f4f6;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: "Cascadia Code", "Fira Code", "Source Code Pro", monospace;
    font-size: 9.5pt;
    color: #dc2626;
}
pre {
    background-color: #1e293b;
    color: #e2e8f0;
    padding: 16px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.5;
}
pre code {
    background: none;
    padding: 0;
    color: inherit;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 10pt;
    table-layout: fixed;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
th, td {
    border: 1px solid #d1d5db;
    padding: 8px 12px;
    text-align: left;
    overflow-wrap: break-word;
    word-wrap: break-word;
}
th {
    background-color: #f9fafb;
    font-weight: 600;
    color: #1e40af;
}
img {
    max-width: 100%;
    height: auto;
    margin: 12px 0;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
}
blockquote {
    border-left: 4px solid #d97706;
    margin: 12px 0;
    padding: 8px 16px;
    background-color: #fffbeb;
}
a {
    color: #2563eb;
    text-decoration: none;
}
ul, ol {
    padding-left: 24px;
}
li {
    margin: 4px 0;
}
/* Callout / Admonition 样式 */
.callout, .admonition {
    border-left: 4px solid #3b82f6;
    background-color: #eff6ff;
    padding: 12px 16px;
    margin: 12px 0;
    border-radius: 4px;
}
.callout-warning, .admonition-warning {
    border-left-color: #f59e0b;
    background-color: #fffbeb;
}
.callout-tip, .admonition-tip {
    border-left-color: #10b981;
    background-color: #ecfdf5;
}
/* 标签/徽章 */
.badge, .tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 9pt;
    background-color: #dbeafe;
    color: #1e40af;
}
.badge-warning {
    background-color: #fef3c7;
    color: #92400e;
}
.badge-success {
    background-color: #d1fae5;
    color: #065f46;
}
/* Tab/代码块标题 */
.code-block-title {
    background-color: #374151;
    color: #d1d5db;
    padding: 6px 16px;
    border-radius: 6px 6px 0 0;
    font-family: monospace;
    font-size: 9pt;
}
pre + .code-block-title,
.code-block-title + pre {
    border-radius: 0 0 6px 6px;
}
"""


def _svg_to_png_base64(svg_content, max_width=800):
    """
    将 SVG 内容转为 PNG base64 data URL。
    使用 Playwright 渲染 SVG 并截图，确保 PDF 中图片可见。
    """
    try:
        b64_svg = base64.b64encode(svg_content).decode("ascii")
        svg_data_url = f"data:image/svg+xml;base64,{b64_svg}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": max_width + 40, "height": 800})
            # 用 HTML 包裹 SVG，确保正确缩放
            html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:20px;">
<img id="svg-img" src="{svg_data_url}" style="max-width:{max_width}px;height:auto;">
</body></html>"""
            page.set_content(html, wait_until="networkidle")
            img_el = page.query_selector("#svg-img")
            if img_el:
                box = img_el.bounding_box()
                if box and box["width"] > 10:
                    png_bytes = img_el.screenshot(type="png")
                    b64_png = base64.b64encode(png_bytes).decode("ascii")
                    browser.close()
                    return f"data:image/png;base64,{b64_png}"
            browser.close()
    except Exception as e:
        print(f"  SVG→PNG 转换失败: {e}")
    return None


def _get_referer_for_url(url):
    """根据图片URL域名自动推断Referer头（防盗链绕过）"""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    referer_map = {
        "i.qbitai.com": "https://www.qbitai.com/",
        "cdn.pingwest.com": "https://www.pingwest.com/",
        "simg.baai.ac.cn": "https://hub.baai.ac.cn/",
        "np-newspic.dfcfw.com": "https://www.eastmoney.com/",
        "doc-fd.zol-img.com.cn": "https://www.zol.com.cn/",
        "mmbiz.qpic.cn": "https://mp.weixin.qq.com/",
        "static.leiphone.com": "https://www.leiphone.com/",
    }
    for domain, referer in referer_map.items():
        if domain in host:
            return referer
    # GitHub 相关域名：使用 github.com 作为 referer
    if "github" in host or "githubusercontent" in host:
        return "https://github.com/"
    return None


def download_image_to_base64(url, timeout=60, max_retries=2):
    """下载远程图片并转为 base64 data URL。SVG 自动转 PNG 确保渲染。支持Referer防盗链和重试。"""
    import time
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    # 自动添加 Referer
    referer = _get_referer_for_url(url)
    if referer:
        headers["Referer"] = referer

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")
                # 检查是否实际返回了图片（而非HTML/纯文本）
                if resp.content and len(resp.content) > 100:
                    if "text/html" in content_type:
                        # 可能是防盗链返回的错误页面，跳过
                        print(f"  图片下载返回HTML（可能防盗链）: {url[:80]}...")
                        return None
                    # 从 URL 推断 MIME 类型
                    ext = url.rsplit(".", 1)[-1].split("?")[0].split("#")[0].lower()
                    if not content_type or "image" not in content_type:
                        mime_map = {
                            "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                            "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp",
                            "ico": "image/x-icon", "avif": "image/avif"
                        }
                        content_type = mime_map.get(ext, "image/png")

                    # SVG 特殊处理：转为 PNG 再嵌入，避免 Playwright PDF 渲染为微小图标
                    if "svg" in content_type or ext == "svg":
                        png_url = _svg_to_png_base64(resp.content)
                        if png_url:
                            print(f"  SVG→PNG 转换成功 ({len(resp.content)} bytes SVG)")
                            return png_url
                        print(f"  SVG→PNG 转换失败，降级直接嵌入 SVG")

                    b64 = base64.b64encode(resp.content).decode("ascii")
                    return f"data:{content_type};base64,{b64}"
                elif resp.content and len(resp.content) <= 100:
                    print(f"  图片内容过小（{len(resp.content)} bytes），可能已失效: {url[:80]}...")
                    return None
            elif resp.status_code == 403:
                print(f"  图片下载403（防盗链）: {url[:80]}...")
                return None
            elif resp.status_code == 404:
                print(f"  图片下载404（不存在）: {url[:80]}...")
                return None
        except Exception as e:
            if attempt < max_retries:
                print(f"  图片下载失败（第{attempt+1}次），{2}秒后重试: {url[:80]}... ({e})")
                time.sleep(2)
                continue
            print(f"  图片下载失败（已重试{max_retries}次）: {url[:80]}... ({e})")
    return None


def download_image_to_file(url, save_dir, timeout=60):
    """下载远程图片到本地文件，返回本地路径"""
    import time
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    referer = _get_referer_for_url(url)
    if referer:
        headers["Referer"] = referer
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            if resp.status_code == 200 and resp.content and len(resp.content) > 100:
                ext = url.rsplit(".", 1)[-1].split("?")[0].split("#")[0].lower()
                valid_exts = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "avif"}
                if ext not in valid_exts:
                    ext = "png"
                h = hashlib.md5(url.encode()).hexdigest()[:12]
                path = os.path.join(save_dir, f"{h}.{ext}")
                if not os.path.exists(path):
                    with open(path, "wb") as f:
                        f.write(resp.content)
                return path
        except Exception:
            if attempt < 2:
                time.sleep(2)
    return None


def embed_images_in_md(content_md, images_dir, use_base64=True):
    """
    处理 Markdown 中的所有远程图片：
    1. 下载图片到 images_dir
    2. 将 Markdown 中的远程 URL 替换为 base64 data URL（用于 HTML 嵌入）
       或本地文件路径
    """
    # 匹配 ![alt](url) 格式
    pattern = r'(!\[[^\]]*\]\()([^)]+)(\))'

    def replacer(match):
        prefix = match.group(1)  # ![alt](
        url = match.group(2)     # 图片 URL
        suffix = match.group(3)  # )

        # 只处理远程图片
        if not url.startswith("http"):
            return match.group(0)

        if use_base64:
            data_url = download_image_to_base64(url)
            if data_url:
                return f"{prefix}{data_url}{suffix}"
        else:
            local_path = download_image_to_file(url, images_dir)
            if local_path:
                abs_path = os.path.abspath(local_path)
                return f"{prefix}file:///{abs_path.replace(os.sep, '/')}{suffix}"

        # 下载失败，替换为占位符避免 networkidle 超时
        print(f"  图片下载失败，使用占位符: {url[:80]}...")
        alt_text = re.search(r'alt=["\']([^"\']*)["\']', match.group(0))
        alt = alt_text.group(1) if alt_text else "图片"
        return f"{prefix}data:image/svg+xml;base64,{base64.b64encode(f'<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"400\" height=\"60\"><rect width=\"100%\" height=\"100%\" fill=\"#f3f4f6\"/><text x=\"50%\" y=\"50%\" text-anchor=\"middle\" dominant-baseline=\"middle\" font-size=\"14\" fill=\"#9ca3af\">[图片加载失败: {alt}]</text></svg>'.encode()).decode()}{suffix}"

    return re.sub(pattern, replacer, content_md)


def _generate_anchor_id(text):
    """从标题文本生成锚点 ID（模拟 GitHub 风格）"""
    # 去除行内代码
    text = re.sub(r'`[^`]+`', '', text)
    # 转小写
    text = text.lower().strip()
    # 移除非字母数字中日文字符
    text = re.sub(r'[^\w\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff-]', '-', text)
    # 合并连续短横线
    text = re.sub(r'-{2,}', '-', text)
    # 去除首尾短横线
    text = text.strip('-')
    return text or 'section'


def _escape_pipes_in_code(md_text):
    """
    临时将行内代码 `...` 中的 | 替换为占位符，
    防止 mistune 表格解析器被行内代码中的 | 干扰。

    采用逐行逐字符解析方式，精确识别行内代码边界，
    只替换行内代码内部的管道符，不影响表格分隔符。
    """
    PIPE_PH = "\x00PIPE\x00"
    result = []
    i = 0
    n = len(md_text)

    while i < n:
        # 检测围栏代码块起始（3+反引号）
        if md_text[i] == '`':
            # 计算连续反引号数量
            j = i
            while j < n and md_text[j] == '`':
                j += 1
            tick_count = j - i

            if tick_count >= 3:
                # 围栏代码块：找到匹配的结束反引号
                end_marker = '`' * tick_count
                # 跳到下一行开始
                while j < n and md_text[j] != '\n':
                    j += 1
                if j < n:
                    j += 1  # 跳过换行
                # 搜索结束标记
                block_start = i
                while j < n:
                    if md_text[j:j+tick_count] == end_marker:
                        # 找到结束，输出整个代码块（不修改管道符）
                        j += tick_count
                        result.append(md_text[block_start:j])
                        i = j
                        break
                    # 在代码块内替换管道符
                    if md_text[j] == '|':
                        result.append(PIPE_PH)
                    else:
                        result.append(md_text[j])
                    j += 1
                else:
                    # 没找到结束标记，原样输出
                    result.append(md_text[block_start:])
                    i = n
                continue
            else:
                # 行内代码（1-2个反引号）
                # 寻找匹配的结束反引号
                end_search = j
                found_end = -1
                while end_search < n:
                    if md_text[end_search:end_search+tick_count] == '`' * tick_count:
                        # 确保后面不是更多反引号
                        if end_search + tick_count >= n or md_text[end_search + tick_count] != '`':
                            found_end = end_search
                            break
                        else:
                            end_search += 1
                    elif tick_count == 1 and md_text[end_search] == '`':
                        found_end = end_search
                        break
                    elif md_text[end_search] == '\n':
                        break  # 行内代码不能跨行
                    else:
                        end_search += 1

                if found_end >= 0:
                    # 输出开头的反引号
                    result.append(md_text[i:j])
                    # 输出代码内容（替换管道符）
                    code_content = md_text[j:found_end]
                    result.append(code_content.replace('|', PIPE_PH))
                    # 输出结束的反引号
                    result.append(md_text[found_end:found_end+tick_count])
                    i = found_end + tick_count
                    continue
                else:
                    # 没有匹配的结束反引号，原样输出
                    result.append(md_text[i])
                    i += 1
                    continue
        else:
            result.append(md_text[i])
            i += 1

    return ''.join(result)


def _restore_pipes_in_html(html_text):
    """将占位符还原为 | 字符"""
    return html_text.replace("\x00PIPE\x00", "|")


def md_to_html(title, content_md):
    """将 Markdown 转为带样式的 HTML，标题自动生成锚点 ID"""
    md = mistune.create_markdown(plugins=['table'])
    body = md(content_md)

    # 为 h2-h6 标题注入 id 属性
    def add_heading_ids(html):
        counter = {}
        def replacer(m):
            level = m.group(1)
            content = m.group(2)
            anchor = _generate_anchor_id(re.sub(r'<[^>]+>', '', content))
            # 处理重复 ID
            if anchor in counter:
                counter[anchor] += 1
                anchor = f"{anchor}-{counter[anchor]}"
            else:
                counter[anchor] = 0
            return f'<h{level} id="{anchor}">{content}</h{level}>'
        return re.sub(r'<h([2-6])>(.*?)</h\1>', replacer, html)

    body = add_heading_ids(body)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
{PDF_CSS}
</style>
</head>
<body>
<h1 class="page-title">{title}</h1>
{body}
</body>
</html>"""


def html_to_pdf(html_content, output_path):
    """使用 Playwright 将 HTML 转为高清 PDF"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle", timeout=60000)
        page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={
                "top": "20mm",
                "bottom": "20mm",
                "left": "15mm",
                "right": "15mm"
            }
        )
        browser.close()


def process_md_to_pdf(input_md, output_pdf, title="", images_dir=None, use_base64=True):
    """完整处理流程：读取 MD → 下载图片嵌入 → 生成离线 PDF"""
    if not os.path.exists(input_md):
        print(f"错误：文件不存在 {input_md}")
        return False

    with open(input_md, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取标题
    if not title:
        first_line = content.strip().split("\n")[0]
        if first_line.startswith("#"):
            title = first_line.lstrip("#").strip()
        else:
            title = os.path.splitext(os.path.basename(input_md))[0]

    # 下载图片并嵌入 Markdown
    if images_dir is None:
        images_dir = os.path.join(os.path.dirname(output_pdf), "..", "..", "images")
    os.makedirs(images_dir, exist_ok=True)

    print(f"  下载图片中...")
    content = embed_images_in_md(content, images_dir, use_base64=use_base64)

    # 转换 HTML → PDF
    html = md_to_html(title, content)
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)
    html_to_pdf(html, output_pdf)
    return True


def main():
    parser = argparse.ArgumentParser(description="Markdown 转 PDF（图片下载嵌入，完全离线）")
    parser.add_argument("input", help="输入 Markdown 文件路径")
    parser.add_argument("output", help="输出 PDF 文件路径")
    parser.add_argument("--title", default="", help="页面标题")
    parser.add_argument("--images-dir", default=None, help="图片保存目录")
    parser.add_argument("--no-base64", action="store_true", help="使用本地文件而非 base64 嵌入")
    args = parser.parse_args()

    success = process_md_to_pdf(
        args.input, args.output,
        title=args.title,
        images_dir=args.images_dir,
        use_base64=not args.no_base64
    )
    if success:
        print(f"PDF 已生成：{args.output}")


if __name__ == "__main__":
    main()
