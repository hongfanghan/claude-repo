"""
链接提取脚本：从原始 HTML 中提取页面内所有内部链接

背景：
    webReader MCP 工具将 HTML 转为纯文本时会丢弃所有 <a> 标签，
    导致交叉索引无法实现。本脚本用 requests + BeautifulSoup 直接
    解析原始 HTML，提取 <a> 标签的文本和 href。

用法：
    # 提取单个页面链接
    python extract_links.py --url "https://code.claude.com/docs/zh-CN/hooks" --site-domain "code.claude.com"

    # 从 manifest.json 批量提取所有页面链接
    python extract_links.py --manifest manifest.json --site-domain "code.claude.com"

    # 输出 JSON 文件
    python extract_links.py --url "https://..." --output links.json

依赖：
    pip install requests beautifulsoup4 lxml
"""

import sys
import os
import re
import json
import argparse
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def fetch_html(url, timeout=30):
    """获取页面原始 HTML"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  获取失败: {url} ({e})")
        return None


def extract_links_from_html(html_content, page_url, site_domain, base_path_prefix=""):
    """
    从 HTML 中提取所有内部链接

    参数：
        html_content: 页面 HTML 字符串
        page_url: 当前页面完整 URL（用于解析相对路径）
        site_domain: 站点域名（用于判断是否内部链接）
        base_path_prefix: URL 路径前缀（如 "/docs/en/"），只保留此前缀开头的链接

    返回：
        internal_links: 站内链接列表，每项包含 text, href, resolved_path, context
    """
    soup = BeautifulSoup(html_content, "lxml")

    # 移除 script、style、nav、footer、header 等无关元素
    for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # 智能定位正文区域：优先使用 article/main 标签，否则用常见正文 class
    content_area = None
    # 优先级 1：语义化标签
    for selector in ["article", "main", "[role='main']", "[role='article']"]:
        content_area = soup.select_one(selector)
        if content_area:
            break
    # 优先级 2：常见文档框架的正文 class
    # 注意：.mdx-content 必须排在 .prose 之前，因为 Mintlify 页面中
    # .prose 可能匹配到空壳 div，实际内容在 .mdx-content 中
    if not content_area:
        for selector in [
            ".mdx-content", ".markdown", ".md-content", ".post-content",
            ".documentation", ".doc-content", ".page-content",
            "#content", "#main-content", ".main-content",
            ".mintlify-main",
            ".content", ".prose",
            "[class*='content']", "[class*='article']"
        ]:
            content_area = soup.select_one(selector)
            if content_area:
                break
    # 优先级 3：找不到就用整个 body（但排除 aside）
    if not content_area:
        content_area = soup.body or soup
        for tag in content_area.find_all("aside"):
            tag.decompose()

    if not content_area:
        return []

    internal_links = []
    seen_hrefs = set()

    for a_tag in content_area.find_all("a", href=True):
        href = a_tag["href"].strip()
        text = a_tag.get_text(strip=True)

        # 跳过空链接、锚点、JavaScript
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        # 跳过邮件、电话
        if href.startswith("mailto:") or href.startswith("tel:"):
            continue

        # 解析为绝对 URL
        abs_url = urljoin(page_url, href)
        parsed = urlparse(abs_url)

        # 判断是否为同站链接
        if parsed.netloc and parsed.netloc != site_domain:
            continue

        # 提取路径部分
        path = parsed.path

        # 如果指定了前缀，只保留匹配的链接
        if base_path_prefix and not path.startswith(base_path_prefix):
            continue

        # 去重（同一 href 只记录一次）
        if path in seen_hrefs:
            continue
        seen_hrefs.add(path)

        # 获取上下文（链接周围的文字，最多前后各 50 字符）
        context = ""
        parent = a_tag.parent
        if parent:
            parent_text = parent.get_text(strip=True)
            idx = parent_text.find(text)
            if idx >= 0:
                start = max(0, idx - 50)
                end = min(len(parent_text), idx + len(text) + 50)
                context = parent_text[start:end]

        # 判断链接类型：页面链接 vs 锚点链接
        link_type = "page"
        if parsed.fragment:
            link_type = "anchor"

        internal_links.append({
            "text": text,
            "href": href,
            "resolved_path": path,
            "fragment": parsed.fragment or "",
            "link_type": link_type,
            "context": context
        })

    return internal_links


def extract_links_from_url(url, site_domain, base_path_prefix="", timeout=30):
    """从 URL 提取链接（完整流程）"""
    html = fetch_html(url, timeout=timeout)
    if not html:
        return []

    return extract_links_from_html(html, url, site_domain, base_path_prefix)


def batch_extract(manifest_path, site_domain, base_path_prefix="", timeout=30):
    """
    从 manifest.json 批量提取所有页面链接

    manifest.json 格式：
    {
        "base_url": "https://code.claude.com/docs/en/",
        "pages": [
            {"url_path": "en/hooks", ...},
            ...
        ]
    }
    """
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    base_url = manifest.get("base_url", "")
    pages = manifest.get("pages", [])

    all_links = {}

    for i, page in enumerate(pages):
        url_path = page.get("url_path", "")
        full_url = base_url + url_path

        print(f"[{i+1}/{len(pages)}] 提取链接: {url_path}")
        links = extract_links_from_url(full_url, site_domain, base_path_prefix, timeout)

        all_links[url_path] = {
            "url": full_url,
            "internal_links": links,
            "link_count": len(links)
        }

        print(f"  → 找到 {len(links)} 个内部链接")

    # 保存到 manifest 同目录
    output_dir = os.path.dirname(os.path.abspath(manifest_path))
    output_path = os.path.join(output_dir, "links_database.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_links, f, ensure_ascii=False, indent=2)

    print(f"\n链接数据库已保存: {output_path}")
    print(f"总页面数: {len(all_links)}")
    print(f"总链接数: {sum(v['link_count'] for v in all_links.values())}")

    return all_links


def main():
    parser = argparse.ArgumentParser(description="从原始 HTML 提取页面内所有内部链接")
    parser.add_argument("--url", help="单个页面 URL")
    parser.add_argument("--manifest", help="manifest.json 文件路径（批量模式）")
    parser.add_argument("--site-domain", required=True, help="站点域名（如 code.claude.com）")
    parser.add_argument("--base-path", default="", help="URL 路径前缀（如 /docs/en/）")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")
    parser.add_argument("--timeout", type=int, default=30, help="请求超时秒数")
    args = parser.parse_args()

    # 修复 Windows Git Bash 路径转换问题：
    # Git Bash 会将 /docs/en/ 自动转换为 C:/DevSoft/Git/docs/en/
    # 检测方式：值包含冒号（驱动器号）但不是 http URL
    if args.base_path and ':' in args.base_path and not args.base_path.startswith('http'):
        import re
        # 匹配 Windows 绝对路径 C:/xxx/docs/en/ → 提取 /docs/en/
        m = re.search(r'(/docs/.*)', args.base_path.replace('\\', '/'))
        if m:
            args.base_path = m.group(1)
            print(f"  [FIX] 路径自动修正: -> {args.base_path}")
        else:
            # 通用回退：去掉驱动器前缀
            m2 = re.match(r'[A-Za-z]:/(.*)', args.base_path.replace('\\', '/'))
            if m2:
                args.base_path = '/' + m2.group(1)
                print(f"  [FIX] 路径自动修正(回退): -> {args.base_path}")

    if args.url:
        # 单页面模式
        links = extract_links_from_url(
            args.url, args.site_domain, args.base_path, args.timeout
        )
        result = {
            "url": args.url,
            "internal_links": links,
            "link_count": len(links)
        }
        print(f"\n找到 {len(links)} 个内部链接：")
        for link in links:
            print(f"  [{link['link_type']}] {link['text']} → {link['resolved_path']}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n已保存: {args.output}")

    elif args.manifest:
        # 批量模式
        batch_extract(args.manifest, args.site_domain, args.base_path, args.timeout)

    else:
        print("请指定 --url 或 --manifest 参数")
        sys.exit(1)


if __name__ == "__main__":
    main()
