#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话记录格式修复脚本

修复从 jsonl 生成会话记录时产生的常见格式问题：
1. 截断过长的工具调用行（>200字符）
2. 修复多行 Bash 命令导致的裸露代码（如 python -c "..." 的内嵌代码）

用法:
    python fix-session-format.py <session_md_file>
    python fix-session-format.py --fix-all  # 修复所有会话记录
"""
import os
import sys
import re
import glob as glob_module

from utils import detect_project_name, get_sessions_dir

CODE_FENCE = chr(96) * 3


def fix_long_tool_calls(lines, max_len=200, desc_len=120):
    """截断过长的工具调用行"""
    result = []
    fixed = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- **') and len(stripped) > max_len:
            match = re.match(r'^(- \*\*(\w+)\*\*:)\s*(.{1,%d})' % desc_len, stripped)
            if match:
                prefix = match.group(1)
                desc_start = match.group(2).rstrip()
                result.append(f'{prefix} {desc_start}...\n')
                fixed += 1
            else:
                result.append(line)
        else:
            result.append(line)
    return result, fixed


def fix_multiline_tool_calls(lines):
    """修复多行工具调用导致的裸露代码

    当 jsonl 中的 Bash 命令包含多行内容（如 python -c "...多行代码..."），
    生成脚本会保留换行符导致代码裸露在 Markdown 中。
    此函数检测多行工具调用并截断为单行 + 行数标注。
    """
    result = []
    i = 0
    fixed = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测 Bash 工具调用中的多行命令（python -c "...、heredoc 等）
        if stripped.startswith('- **Bash**:') and ('python -c "' in stripped or 'python -c \"' in stripped):
            collected = [stripped]
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                # 遇到下一个工具调用、章节标题、分隔符、引用或空行时停止
                if next_line.startswith('- **') or next_line.startswith('**') \
                   or next_line.startswith('#') or next_line.startswith('---') \
                   or next_line.startswith('>') or not next_line:
                    break
                collected.append(next_line)
                j += 1

            if len(collected) > 1:
                first_line = collected[0]
                if len(first_line) > 150:
                    result.append(f'{first_line[:120]}...\n')
                else:
                    result.append(f'{first_line}\n')
                result.append(f'  ({len(collected)} 行命令)\n')
                fixed += 1
                i = j
                continue

        # 检测非 Bash 工具调用的多行延续（如 Read 的文件内容）
        if stripped.startswith('- **') and not stripped.startswith('- **Bash**'):
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('- **') \
                   and not next_line.startswith('**') \
                   and not next_line.startswith('#') \
                   and not next_line.startswith('---') \
                   and not next_line.startswith('>'):
                    result.append(f'{stripped}\n')
                    i += 1
                    fixed += 1
                    continue

        result.append(line)
        i += 1

    return result, fixed


def fix_session_format(md_path):
    """修复单个会话记录文件的格式问题"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_size = len(content)
    lines = content.split('\n')

    # Step 1: 修复多行工具调用（先执行，因为它处理裸露代码行）
    lines, multiline_fixed = fix_multiline_tool_calls(lines)

    # Step 2: 截断过长工具调用行
    lines, long_fixed = fix_long_tool_calls(lines)

    result = '\n'.join(lines)
    new_size = len(result)

    if original_size != new_size or multiline_fixed > 0 or long_fixed > 0:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(result)

    return multiline_fixed + long_fixed


def fix_all_sessions():
    """修复所有会话记录文件"""
    sessions_dir = get_sessions_dir()
    if not os.path.exists(sessions_dir):
        print(f"会话记录目录不存在: {sessions_dir}")
        return

    md_files = glob_module.glob(os.path.join(sessions_dir, "**/*.md"), recursive=True)
    total_fixed = 0

    for md_file in sorted(md_files):
        fixed = fix_session_format(md_file)
        if fixed > 0:
            name = os.path.basename(md_file)
            print(f"  修复 {fixed} 处格式问题: {name}")
            total_fixed += fixed

    print(f"\n共修复 {total_fixed} 处格式问题（{len(md_files)} 个文件）")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    if sys.argv[1] == '--fix-all':
        print("修复所有会话记录文件...")
        fix_all_sessions()
        return

    md_path = sys.argv[1]
    if not os.path.exists(md_path):
        print(f"错误: 文件不存在 - {md_path}")
        return

    fixed = fix_session_format(md_path)
    if fixed > 0:
        print(f"修复 {fixed} 处格式问题: {md_path}")
    else:
        print(f"无需修复: {md_path}")


if __name__ == '__main__':
    main()
