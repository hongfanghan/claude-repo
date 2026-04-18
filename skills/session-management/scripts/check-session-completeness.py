#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话记录完整性+格式检查脚本

用于检查会话记录是否符合session-management技能的要求：
1. 检查会话记录是否包含完整的AI回复（不是摘要）
2. 检查对话轮次是否与jsonl文件匹配
3. 检查是否标注了"含压缩前完整会话"
4. 检查格式问题（TODO占位符、代码围栏闭合、用户输入引用格式、裸露代码行）

用法:
    python check-session-completeness.py <session_md_file> <jsonl_file>
    python check-session-completeness.py --check-all  # 检查所有会话记录
    python check-session-completeness.py --check-all --format  # 同时检查格式问题
"""

import os
import sys
import re
import json
import glob as glob_module
from datetime import datetime

# 导入公共工具函数
from utils import detect_project_name, get_sessions_dir, get_jsonl_dir

def count_rounds_in_md(md_path):
    """统计Markdown会话记录中的对话轮次"""
    with open(md_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # 统计 "### 第N轮对话" 的数量
    rounds = len(re.findall(r'### 第\d+轮对话', content))

    # 检查是否有摘要标记
    has_summary = '摘要' in content or '概要' in content

    # 检查是否有完整会话标注
    has_full_mark = '含压缩前完整会话' in content or '完整会话' in content

    # 检查AI回复是否包含完整内容（非摘要）
    # 完整内容通常包含代码块、表格、列表等
    has_code_blocks = '```' in content
    has_tables = '|:' in content or '|---' in content

    # 统计文件行数
    line_count = len(content.split('\n'))

    return {
        'rounds': rounds,
        'has_summary': has_summary,
        'has_full_mark': has_full_mark,
        'has_code_blocks': has_code_blocks,
        'has_tables': has_tables,
        'line_count': line_count,
        'file_size': os.path.getsize(md_path)
    }

def count_rounds_in_jsonl(jsonl_path):
    """统计jsonl文件中的用户消息轮次"""
    user_count = 0
    assistant_count = 0

    parse_errors = 0
    with open(jsonl_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get('type') == 'user':
                    user_count += 1
                elif data.get('type') == 'assistant':
                    assistant_count += 1
            except (json.JSONDecodeError, KeyError):
                parse_errors += 1

    return {
        'user_count': user_count,
        'assistant_count': assistant_count,
        'parse_errors': parse_errors
    }

def check_format_issues(md_path):
    """检查会话记录的格式问题

    检测从jsonl生成会话记录时常见的格式缺陷：
    1. TODO占位符（残留的 <!-- TODO --> 或 (TODO)）
    2. 代码围栏未正确闭合（奇数个 ```）
    3. 用户输入缺少 > 引用格式
    4. 裸露代码行（工具调用行之间的非Markdown行）
    """
    with open(md_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    lines = content.split('\n')
    issues = []

    # 1. TODO占位符检查
    todo_count = 0
    for line in lines:
        stripped = line.strip()
        if '<!-- TODO' in stripped or '(TODO' in stripped or '(本轮无文本输出)' in stripped:
            todo_count += 1
    if todo_count > 0:
        issues.append(f"发现 {todo_count} 处TODO占位符")

    # 2. 代码围栏闭合检查
    fence_count = content.count('```')
    if fence_count % 2 != 0:
        issues.append(f"代码围栏未闭合（奇数个 ```，共 {fence_count} 个）")

    # 3. 用户输入 > 引用格式检查
    in_user_input = False
    user_input_start = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '**用户输入**:' or stripped == '**用户输入**:':
            in_user_input = True
            user_input_start = idx
            continue
        if in_user_input:
            if stripped.startswith('**') and stripped.endswith(':'):
                # 遇到下一个子节（如 **AI回复**:），停止检查
                in_user_input = False
                continue
            if stripped and not stripped.startswith('>'):
                issues.append(f"第{idx+1}行: 用户输入缺少 > 引用格式: {stripped[:60]}")
                in_user_input = False

    # 4. 裸露代码行检查（工具调用行之间的可疑行）
    # 在 "**工具调用示例**:" 子节中，非列表项且非空的行可能是裸露代码
    in_tools = False
    bare_lines = 0
    for line in lines:
        stripped = line.strip()
        if stripped == '**工具调用示例**:' or stripped == '**工具调用示例**:':
            in_tools = True
            continue
        if in_tools:
            if stripped.startswith('###') or stripped.startswith('---'):
                in_tools = False
                continue
            # 工具调用子节内，非空、非列表项、非代码围栏、非粗体的行可能是裸露代码
            if stripped and not stripped.startswith('-') \
               and not stripped.startswith('```') \
               and not stripped.startswith('**') \
               and not stripped.startswith('|') \
               and not stripped.startswith('注'):
                bare_lines += 1
    if bare_lines > 0:
        issues.append(f"发现 {bare_lines} 处可能的裸露代码行（工具调用子节内）")

    return issues


def check_completeness(md_path, jsonl_path):
    """检查会话记录完整性"""

    md_info = count_rounds_in_md(md_path)
    jsonl_info = count_rounds_in_jsonl(jsonl_path)

    # 计算完整性比率
    if jsonl_info['user_count'] > 0:
        round_ratio = md_info['rounds'] / jsonl_info['user_count']
    else:
        round_ratio = 1.0

    # 判断是否完整
    is_complete = True
    issues = []

    # 检查轮次完整性（要求90%以上）
    if round_ratio < 0.9:
        is_complete = False
        issues.append(f"对话轮次不完整: {md_info['rounds']}/{jsonl_info['user_count']} ({round_ratio*100:.1f}%)")

    # 检查是否有完整会话标注（如果jsonl轮次大于md轮次，说明有压缩前的内容）
    if jsonl_info['user_count'] > md_info['rounds'] and not md_info['has_full_mark']:
        is_complete = False
        issues.append("缺少'含压缩前完整会话'标注")

    # 检查文件大小（太小说明是摘要）
    if md_info['file_size'] < 5000 and jsonl_info['user_count'] > 3:
        is_complete = False
        issues.append(f"文件太小可能是摘要: {md_info['file_size']} bytes")

    return {
        'md_path': md_path,
        'jsonl_path': jsonl_path,
        'md_info': md_info,
        'jsonl_info': jsonl_info,
        'round_ratio': round_ratio,
        'is_complete': is_complete,
        'issues': issues
    }

def check_all_sessions(check_format=False):
    """检查所有会话记录的完整性和格式问题"""

    sessions_dir = get_sessions_dir()
    jsonl_dir = get_jsonl_dir()

    if not os.path.exists(sessions_dir):
        print(f"会话记录目录不存在: {sessions_dir}")
        return

    # 查找所有Markdown会话记录
    md_files = glob_module.glob(os.path.join(sessions_dir, "**/*.md"), recursive=True)

    # 查找所有jsonl文件
    jsonl_files = glob_module.glob(os.path.join(jsonl_dir, "*.jsonl"))

    print("=" * 70)
    print("会话记录完整性检查报告" + ("（含格式检查）" if check_format else ""))
    print("=" * 70)
    print()

    results = []

    for md_file in md_files:
        # 获取文件修改时间
        md_mtime = datetime.fromtimestamp(os.path.getmtime(md_file))

        # 查找最接近的jsonl文件
        best_jsonl = None
        best_diff = float('inf')

        for jsonl_file in jsonl_files:
            jsonl_mtime = datetime.fromtimestamp(os.path.getmtime(jsonl_file))
            diff = abs((md_mtime - jsonl_mtime).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_jsonl = jsonl_file

        if best_jsonl and best_diff < 3600:  # 1小时内
            result = check_completeness(md_file, best_jsonl)
            results.append(result)

    # 输出结果
    complete_count = sum(1 for r in results if r['is_complete'])
    incomplete_count = len(results) - complete_count

    print(f"检查会话记录: {len(results)} 个")
    print(f"完整: {complete_count} 个")
    print(f"不完整: {incomplete_count} 个")
    print()

    if incomplete_count > 0:
        print("-" * 70)
        print("不完整的会话记录:")
        print("-" * 70)

        for r in results:
            if not r['is_complete']:
                print(f"\n文件: {os.path.basename(r['md_path'])}")
                print(f"  MD轮次: {r['md_info']['rounds']}, JSONL用户消息: {r['jsonl_info']['user_count']}")
                print(f"  完整性比率: {r['round_ratio']*100:.1f}%")
                print(f"  问题:")
                for issue in r['issues']:
                    print(f"    - {issue}")

    print()
    print("=" * 70)
    print("建议: 对于不完整的会话记录，使用Read工具读取jsonl文件提取完整内容")
    if check_format:
        print("建议: 对于格式问题，运行 fix-session-format.py --fix-all 自动修复")
    print("=" * 70)

    # 格式检查
    if check_format:
        print()
        print("-" * 70)
        print("格式检查结果:")
        print("-" * 70)

        total_format_issues = 0
        for md_file in md_files:
            format_issues = check_format_issues(md_file)
            if format_issues:
                total_format_issues += len(format_issues)
                print(f"\n文件: {os.path.basename(md_file)}")
                for issue in format_issues:
                    print(f"  - {issue}")

        if total_format_issues == 0:
            print("  所有文件格式正常")
        else:
            print(f"\n共发现 {total_format_issues} 处格式问题")
            print("  运行 fix-session-format.py --fix-all 可自动修复部分问题")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    if sys.argv[1] == '--check-all':
        check_format = '--format' in sys.argv
        check_all_sessions(check_format=check_format)
        return

    if len(sys.argv) < 3:
        print("错误: 需要提供会话记录文件和jsonl文件路径")
        print(__doc__)
        return

    md_path = sys.argv[1]
    jsonl_path = sys.argv[2]

    if not os.path.exists(md_path):
        print(f"错误: 会话记录文件不存在 - {md_path}")
        return

    if not os.path.exists(jsonl_path):
        print(f"错误: jsonl文件不存在 - {jsonl_path}")
        return

    result = check_completeness(md_path, jsonl_path)

    print("=" * 70)
    print("会话记录完整性检查结果")
    print("=" * 70)
    print(f"\n会话记录: {md_path}")
    print(f"JSONL文件: {jsonl_path}")
    print(f"\n统计信息:")
    print(f"  MD轮次: {result['md_info']['rounds']}")
    print(f"  MD行数: {result['md_info']['line_count']}")
    print(f"  MD大小: {result['md_info']['file_size']} bytes")
    print(f"  JSONL用户消息: {result['jsonl_info']['user_count']}")
    print(f"  JSONL AI回复: {result['jsonl_info']['assistant_count']}")
    print(f"\n完整性比率: {result['round_ratio']*100:.1f}%")

    if result['is_complete']:
        print("\n结果: [完整] 会话记录符合要求")
    else:
        print("\n结果: [不完整] 存在以下问题:")
        for issue in result['issues']:
            print(f"  - {issue}")

    print("=" * 70)

if __name__ == '__main__':
    main()
