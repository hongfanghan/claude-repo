"""
PDF 合并辅助脚本（支持层级书签目录 + 目录页跳转）

功能：
1. 将多个 PDF 文件按网站目录结构合并
2. 生成可点击跳转的目录页
3. 添加层级书签导航（支持子目录折叠）

用法：
    # 从 manifest.json 生成带书签和目录页的合并 PDF
    python merge_pdfs.py --manifest manifest.json --output output.pdf

    # 简单合并（无书签）
    python merge_pdfs.py -o output.pdf input1.pdf input2.pdf ...

依赖：
    pip install pypdf
"""

import sys
import os
import json
import argparse
from pypdf import PdfReader, PdfWriter


def url_path_to_parts(url_path):
    """将 URL 路径拆分为层级列表，去掉语言前缀"""
    parts = url_path.strip("/").split("/")
    if len(parts) > 1:
        parts = parts[1:]  # 去掉语言前缀（如 "en"、"zh-CN"）
    return parts


def pretty_name(name):
    """将 URL slug 转为可读名称"""
    return name.replace("-", " ").replace("_", " ").title()


def merge_with_toc_and_bookmarks(page_list, output_path):
    """
    合并 PDF 并添加：
    1. 目录页（可点击跳转）
    2. 层级书签（PDF 阅读器侧边栏导航）

    page_list 每个元素：
    {
        "url_path": "en/agent-sdk/overview",
        "pdf_file": "pages/en/agent-sdk/overview.pdf",
        "title": "Agent SDK 概述"
    }
    """
    writer = PdfWriter()
    toc_entries = []  # 目录项：(层级, 标题, 页码)
    page_num = 0

    # 确定基准目录（manifest 所在目录）
    base_dir = os.path.dirname(os.path.abspath(output_path))

    # 第一遍：计算每页 PDF 的页数，建立页码映射
    pdf_page_counts = []
    for page in page_list:
        pdf_file = page.get("pdf_file", page.get("pdf_path", ""))
        pdf_path = os.path.join(base_dir, pdf_file) if pdf_file and not os.path.isabs(pdf_file) else pdf_file
        if not os.path.exists(pdf_path):
            pdf_page_counts.append(0)
            continue
        try:
            reader = PdfReader(pdf_path)
            pdf_page_counts.append(len(reader.pages))
        except Exception:
            pdf_page_counts.append(0)

    # 计算目录页需要多少页（估算）
    # 目录页为 HTML 生成的 PDF，后续会插入
    toc_placeholder_pages = max(1, (len(page_list) + 15) // 30)  # 约30条/页

    # 第二遍：写入所有页面并记录书签位置
    current_page = toc_placeholder_pages  # 预留目录页空间
    page_bookmarks = []  # (层级, 标题, 页码, 父级路径)

    for i, page in enumerate(page_list):
        pdf_file = page.get("pdf_file", page.get("pdf_path", ""))
        pdf_path = os.path.join(base_dir, pdf_file) if pdf_file and not os.path.isabs(pdf_file) else pdf_file
        if not os.path.exists(pdf_path):
            continue

        try:
            reader = PdfReader(pdf_path)
            parts = url_path_to_parts(page["url_path"])
            title = page.get("title") or pretty_name(parts[-1])
            depth = max(0, len(parts) - 1)

            # 记录目录项
            toc_entries.append((depth, title, current_page, parts))
            page_bookmarks.append((depth, title, current_page, parts))

            # 写入页面
            for pdf_page in reader.pages:
                writer.add_page(pdf_page)
            current_page += len(reader.pages)
        except Exception as e:
            print(f"警告：无法读取 {pdf_path}: {e}")

    # 第三遍：添加层级书签（支持嵌套）
    _add_nested_bookmarks(writer, page_bookmarks)

    # 第四遍：生成目录页并插入最前面
    toc_pdf_path = output_path + ".toc.tmp.pdf"
    _generate_toc_pdf(toc_entries, toc_pdf_path, output_path)

    if os.path.exists(toc_pdf_path):
        toc_reader = PdfReader(toc_pdf_path)
        actual_toc_pages = len(toc_reader.pages)

        # 如果预估页数不准确，需要重新计算偏移
        page_offset = actual_toc_pages - toc_placeholder_pages
        if page_offset != 0:
            # 重新生成带正确页码的目录
            adjusted_entries = [
                (d, t, p + page_offset, parts)
                for d, t, p, parts in toc_entries
            ]
            _generate_toc_pdf(adjusted_entries, toc_pdf_path, output_path)
            toc_reader = PdfReader(toc_pdf_path)
            actual_toc_pages = len(toc_reader.pages)

        # 将目录页插入到最前面
        # 使用新的 writer
        final_writer = PdfWriter()
        for toc_page in toc_reader.pages:
            final_writer.add_page(toc_page)

        # 重新添加书签到 final_writer
        final_bookmarks = [
            (d, t, p + actual_toc_pages, parts)
            for d, t, p, parts in page_bookmarks
        ]

        # 添加内容页
        for page_idx in range(len(writer.pages)):
            final_writer.add_page(writer.pages[page_idx])

        # 添加层级书签
        _add_nested_bookmarks(final_writer, final_bookmarks)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        final_writer.write(output_path)
        final_writer.close()

        # 清理临时文件
        try:
            os.remove(toc_pdf_path)
        except Exception:
            pass
    else:
        # 目录页生成失败，直接保存内容
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        writer.write(output_path)
        writer.close()

    print(f"已合并 {len(page_list)} 个 PDF（含目录页和书签）→ {output_path}")


def _add_nested_bookmarks(writer, bookmarks):
    """添加层级嵌套书签"""
    # 按目录结构构建父子关系
    parent_map = {}  # 路径 → 书签对象

    for depth, title, page_num, parts in bookmarks:
        # 查找父书签
        parent = None
        if depth > 0:
            parent_key = "/".join(parts[:depth])
            parent = parent_map.get(parent_key)

        try:
            if parent:
                bm = writer.add_outline_item(title, page_num, parent=parent)
            else:
                bm = writer.add_outline_item(title, page_num)

            # 记录当前书签（作为可能的父书签）
            current_key = "/".join(parts)
            parent_map[current_key] = bm
        except Exception:
            pass

    # 额外：为每个子目录创建分组书签
    # 如果目录下有多个页面，先创建目录级书签
    section_bookmarks = {}
    sorted_bookmarks = sorted(bookmarks, key=lambda x: "/".join(x[3]))

    for depth, title, page_num, parts in bookmarks:
        # 为中间目录添加分组书签
        for i in range(1, len(parts)):
            section_parts = parts[:i]
            section_key = "/".join(section_parts)
            if section_key not in section_bookmarks:
                section_title = pretty_name(section_parts[-1])
                try:
                    # 分组书签指向该目录下第一个页面
                    if depth == 0 or i == len(parts) - 1:
                        continue
                    sbm = writer.add_outline_item(section_title, page_num)
                    section_bookmarks[section_key] = sbm
                except Exception:
                    pass


def _generate_toc_pdf(toc_entries, toc_pdf_path, final_output_path):
    """生成目录页 PDF"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("警告：playwright 未安装，跳过目录页生成")
        return

    html = _build_toc_html(toc_entries, final_output_path)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            page.pdf(
                path=toc_pdf_path,
                format="A4",
                print_background=True,
                margin={"top": "15mm", "bottom": "15mm",
                        "left": "20mm", "right": "20mm"}
            )
            browser.close()
    except Exception as e:
        print(f"警告：目录页生成失败: {e}")


def _build_toc_html(toc_entries, final_output_path):
    """构建目录页 HTML"""
    # 按目录分组
    sections = {}
    flat_entries = []

    for depth, title, page_num, parts in toc_entries:
        if depth == 0:
            flat_entries.append((0, title, page_num))
        else:
            section_name = pretty_name(parts[0]) if parts else "Other"
            if section_name not in sections:
                sections[section_name] = []
            sections[section_name].append((depth - 1, title, page_num))

    toc_items_html = ""
    for depth, title, page_num in flat_entries:
        indent = "    " * depth
        toc_items_html += f'<div class="toc-item" style="padding-left: {depth * 24}px;">\n'
        toc_items_html += f'  <span class="toc-title">{title}</span>\n'
        toc_items_html += f'  <span class="toc-page">{page_num + 1}</span>\n'
        toc_items_html += '</div>\n'

    # 子目录分组
    for section_name, entries in sections.items():
        toc_items_html += f'<div class="toc-section">\n'
        toc_items_html += f'<div class="toc-section-header">{section_name}</div>\n'
        for depth, title, page_num in entries:
            toc_items_html += f'<div class="toc-item" style="padding-left: {24 + depth * 24}px;">\n'
            toc_items_html += f'  <span class="toc-title">{title}</span>\n'
            toc_items_html += f'  <span class="toc-page">{page_num + 1}</span>\n'
            toc_items_html += '</div>\n'
        toc_items_html += '</div>\n'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    padding: 0;
    margin: 0;
}}
.toc-cover {{
    text-align: center;
    padding: 120px 0 40px 0;
    border-bottom: 3px solid #d97706;
    margin-bottom: 40px;
}}
.toc-cover h1 {{
    font-size: 28pt;
    color: #1e40af;
    margin: 0 0 12px 0;
}}
.toc-cover .subtitle {{
    font-size: 14pt;
    color: #6b7280;
}}
.toc-header {{
    font-size: 18pt;
    color: #d97706;
    border-bottom: 2px solid #d97706;
    padding-bottom: 8px;
    margin: 30px 0 16px 0;
}}
.toc-section {{
    margin: 8px 0;
}}
.toc-section-header {{
    font-weight: 700;
    font-size: 12pt;
    color: #1e40af;
    padding: 6px 0;
    margin-top: 12px;
    border-bottom: 1px dashed #e5e7eb;
}}
.toc-item {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 3px 0;
    border-bottom: 1px dotted #e5e7eb;
}}
.toc-title {{
    color: #374151;
}}
.toc-page {{
    color: #6b7280;
    font-size: 10pt;
    min-width: 30px;
    text-align: right;
}}
</style>
</head>
<body>
<div class="toc-cover">
    <h1>网站中文版 PDF</h1>
    <div class="subtitle">完整离线版 - 含目录导航和层级书签</div>
</div>
<div class="toc-header">目录</div>
{toc_items_html}
</body>
</html>"""


def merge_pdfs_simple(pdf_paths, output_path):
    """简单合并多个 PDF（无书签）"""
    writer = PdfWriter()
    for path in pdf_paths:
        if os.path.exists(path):
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
        else:
            print(f"警告：跳过不存在的文件 {path}")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    writer.write(output_path)
    writer.close()


def main():
    parser = argparse.ArgumentParser(description="PDF 合并（支持书签目录 + 目录页跳转）")
    parser.add_argument("--manifest", help="manifest.json 文件路径（用于生成书签和目录页）")
    parser.add_argument("--output", "-o", help="输出 PDF 文件路径")
    parser.add_argument("inputs", nargs="*", help="输入 PDF 文件（无 manifest 时使用）")
    args = parser.parse_args()

    if args.manifest and args.output:
        with open(args.manifest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        pages = manifest.get("pages", [])
        merge_with_toc_and_bookmarks(pages, args.output)
    elif args.inputs:
        output = args.output or args.inputs[0].replace(".pdf", "-merged.pdf")
        merge_pdfs_simple(args.inputs, output)
        print(f"已合并 {len(args.inputs)} 个 PDF → {output}")
    else:
        print("用法：")
        print("  python merge_pdfs.py --manifest manifest.json -o output.pdf")
        print("  python merge_pdfs.py -o output.pdf input1.pdf input2.pdf ...")
        sys.exit(1)


if __name__ == "__main__":
    main()
