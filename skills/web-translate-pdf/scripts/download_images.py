"""
图片下载辅助脚本

从 Markdown 文件中提取图片 URL 并下载到本地

用法：
    python download_images.py <input.md> [--output-dir 图片目录] [--timeout 超时秒数]

依赖：
    pip install requests
"""

import re
import os
import sys
import argparse
import hashlib
import requests


def extract_image_urls(md_content):
    """从 Markdown 内容中提取所有图片 URL"""
    # 匹配 ![alt](url) 格式
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    matches = re.findall(pattern, md_content)
    return [(alt, url) for alt, url in matches if url.startswith("http")]


def download_image(url, save_dir, timeout=30):
    """下载图片到本地，返回本地路径"""
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        if resp.status_code == 200:
            # 从 URL 推断扩展名
            ext = url.rsplit(".", 1)[-1].split("?")[0].split("#")[0][:4].lower()
            if ext not in ("png", "jpg", "jpeg", "gif", "svg", "webp", "ico"):
                ext = "png"
            h = hashlib.md5(url.encode()).hexdigest()[:12]
            path = os.path.join(save_dir, f"{h}.{ext}")
            if not os.path.exists(path):
                with open(path, "wb") as f:
                    f.write(resp.content)
            return path
    except Exception:
        pass
    return url


def replace_images(md_content, replacements):
    """替换 Markdown 中的图片 URL"""
    for old_url, new_path in replacements.items():
        md_content = md_content.replace(old_url, new_path)
    return md_content


def main():
    parser = argparse.ArgumentParser(description="下载 Markdown 中的图片")
    parser.add_argument("input", help="输入 Markdown 文件路径")
    parser.add_argument("--output-dir", default="images", help="图片保存目录")
    parser.add_argument("--timeout", type=int, default=30, help="下载超时（秒）")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误：文件不存在 {args.input}")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        content = f.read()

    images = extract_image_urls(content)
    print(f"发现 {len(images)} 张图片")

    os.makedirs(args.output_dir, exist_ok=True)

    replacements = {}
    for alt, url in images:
        local = download_image(url, args.output_dir, args.timeout)
        if local != url:
            replacements[url] = local
            print(f"  ✓ {url} → {local}")
        else:
            print(f"  ✗ {url} (下载失败)")

    if replacements:
        new_content = replace_images(content, replacements)
        with open(args.input, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"已替换 {len(replacements)} 张图片路径")


if __name__ == "__main__":
    main()
