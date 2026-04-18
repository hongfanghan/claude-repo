#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话记录 V3.1 格式化工具

用途：将 extract_jsonl.py 的提取输出转换为 V3.1 模板格式
位置：.claude/skills/session-management/scripts/format_sessions.py

使用方法：
    # 单文件转换
    python format_sessions.py <extracted_md> --output <output_md> --date 2026-04-10 --seq 01 --topic "主题"

    # 批量转换（从目录）
    python format_sessions.py --batch-dir <extracted_dir> --sessions-dir <sessions_dir>

    # 批量转换（从配置JSON）
    python format_sessions.py --config <config.json>

参数：
    extracted_md      提取脚本输出的 markdown 文件路径
    --output, -o     输出文件路径（默认：自动生成）
    --date           会话日期 YYYY-MM-DD
    --seq            每日会话序号（01, 02, ...）
    --topic          会话主题
    --jsonl-id       jsonl 文件 ID（用于记录来源）
    --batch-dir      批量模式：提取文件所在目录
    --sessions-dir   批量模式：会话记录输出目录（默认：~/.claude/sessions/{project}，自动检测项目名）
    --config         批量模式：配置 JSON 文件路径
    --auto-seq       自动根据 jsonl 文件创建时间确定每日序号（需要 --jsonl-dir 和 --jsonl-id）
    --auto-date      自动从 jsonl 文件创建时间推导日期（需要 --jsonl-dir 和 --jsonl-id），跨天会话使用 jsonl 创建日期而非当前日期
    --jsonl-dir      jsonl 文件所在目录（用于 --auto-seq 或 --list-sessions）
    --list-sessions  列出指定日期的所有会话及创建时间排序

配置 JSON 格式：
[
  {"prefix": "730dc0cb", "date": "2026-04-09", "seq": "01", "topic": "CLAUDE.md文档更新", "jsonl_id": "730dc0cb-..."},
  ...
]
"""

import os
import re
import sys
import json
import argparse
import platform
import subprocess
from pathlib import Path
import shutil
from datetime import datetime

# 导入公共工具函数
from utils import detect_project_name, get_sessions_dir

# 默认会话记录目录（自动检测项目名称）
DEFAULT_SESSIONS_DIR = get_sessions_dir()

# 默认 projects 目录（用于查找 jsonl 文件）
DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _find_jsonl_path(session_id):
    """在 ~/.claude/projects/ 下所有目录中查找 jsonl 文件的完整路径。

    Args:
        session_id: 会话 session-id（UUID格式，不含 .jsonl 后缀）

    Returns:
        str: 找到的完整路径，或 None
    """
    projects_dir = DEFAULT_PROJECTS_DIR
    if not projects_dir.exists():
        return None
    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        jsonl_file = proj_dir / f"{session_id}.jsonl"
        if jsonl_file.exists():
            return str(jsonl_file)
    return None


def count_turns(content):
    """统计对话轮次（用户消息数）"""
    return len(re.findall(r'^### \d+\. 用户', content, re.MULTILINE))


def extract_first_user_message(content):
    """提取第一条用户消息"""
    match = re.search(r'^### \d+\. 用户\s*\n> (.+?)(?:\n---|\n\n)', content, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()[:200]
    return "未知"


def extract_tool_calls(content):
    """提取工具调用列表"""
    tools = set()
    for match in re.finditer(r'^- (\w+):', content, re.MULTILINE):
        tool_name = match.group(1)
        if tool_name not in ('用户', 'AI助手', '记录'):
            tools.add(tool_name)
    for match in re.finditer(r'\*\*工具调用:\*\*\n((?:- .+\n?)+)', content):
        for tool_match in re.finditer(r'- (\w+):', match.group(1)):
            tools.add(tool_match.group(1))
    return sorted(tools)


def extract_document_outputs(content):
    """提取文档产出"""
    docs = set()
    for pattern in [r'Write: `(.+?)`', r'Edit: `(.+?)`']:
        for match in re.finditer(pattern, content):
            docs.add(match.group(1))
    return sorted(docs)


def restructure_conversation(content):
    """将提取脚本的消息格式转换为 V3.1 轮次格式"""
    lines = content.split('\n')
    output = []
    turn_num = 0
    current_role = None
    current_content = []
    tool_calls_block = []

    # 跳过提取脚本的头部
    header_end = False
    for line in lines:
        if line.strip() == '---' and not header_end:
            header_end = True
            continue
        if not header_end:
            continue

        # 检测角色切换
        role_match = re.match(r'^### \d+\. (用户|AI助手|记录)\s*$', line)
        if role_match:
            role = role_match.group(1)

            # 跳过"记录"类型的系统消息
            if role == '记录':
                continue

            if role == '用户' and current_role == 'AI助手':
                # AI回合结束，输出工具调用示例和AI思考链
                if tool_calls_block:
                    output.append("")
                    output.append(f"### {turn_num}.4. 工具调用示例")
                    output.append("")
                    for tc in tool_calls_block:
                        output.append(f"**{tc}**")
                        output.append("")
                    tool_calls_block = []

                output.append("")
                output.append(f"### {turn_num}.3. AI思考链")
                output.append("")
                output.append("<!-- TODO: 根据本轮对话的实际执行过程填充，禁止使用通用占位符 -->")
                output.append("")

                turn_num += 1
                output.append(f"## {turn_num}. 对话轮次 {turn_num}")
                output.append("")
            elif role == '用户' and current_role is None:
                turn_num += 1
                output.append(f"## {turn_num}. 对话轮次 {turn_num}")
                output.append("")
            elif role == 'AI助手' and current_role == '用户':
                current_content = []

            if role == '用户':
                output.append(f"### {turn_num}.1. 用户输入")
                output.append("")
                current_role = '用户'
            elif role == 'AI助手':
                output.append(f"### {turn_num}.2. AI回复")
                output.append("")
                current_role = 'AI助手'
            current_content = []
        elif line.strip() == '---':
            continue
        else:
            # 收集工具调用
            tc_match = re.match(
                r'^- (Read|Edit|Write|Bash|Grep|Glob|Agent|Skill|TaskCreate|TaskUpdate|AskUserQuestion): (.+)$',
                line
            )
            if tc_match and current_role == 'AI助手':
                tool_calls_block.append(f"{tc_match.group(1)} - {tc_match.group(2)}")

            output.append(line)

    # 处理最后一个回合
    if tool_calls_block:
        output.append("")
        output.append(f"### {turn_num}.4. 工具调用示例")
        output.append("")
        for tc in tool_calls_block:
            output.append(f"**{tc}**")
            output.append("")

    if turn_num > 0:
        output.append("")
        output.append(f"### {turn_num}.3. AI思考链")
        output.append("")
        output.append("<!-- TODO: 根据本轮对话的实际执行过程填充，禁止使用通用占位符 -->")
        output.append("")

    return '\n'.join(output), turn_num


def infer_rules_refs(topic):
    """根据主题推断涉及的规则/技能（通用规则，适用于所有项目）"""
    refs = []
    t = topic.lower()
    if 'jsonl' in t or '会话' in t:
        refs.append("- session-management: 会话保存与文档管理技能")
    if 'git' in t or '环境' in t or '排查' in t:
        refs.append("- 系统环境排查相关工具")
    if 'claude.md' in t:
        refs.append("- CLAUDE.md: 项目配置文件")
    if '权限' in t or '配置' in t or 'settings' in t:
        refs.append("- update-config: 配置管理技能")
    if '架构' in t or 'design' in t:
        refs.append("- architecture-design: 架构设计技能")
    if '文档' in t and ('生成' in t or '创建' in t):
        refs.append("- doc-reading: 文档处理技能")
    return refs


def format_session(extract_file, date, seq, topic, jsonl_id, sessions_dir, output_path=None):
    """格式化单个会话文件"""
    extract_path = Path(extract_file)
    if not extract_path.exists():
        print(f"  跳过: {extract_path} 不存在", file=sys.stderr)
        return None

    with open(extract_path, 'r', encoding='utf-8', errors='replace') as f:
        raw_content = f.read()

    first_msg = extract_first_user_message(raw_content)
    tools = extract_tool_calls(raw_content)
    docs = extract_document_outputs(raw_content)
    restructured, turn_count = restructure_conversation(raw_content)

    parts = []

    # 头部
    parts.append(f"# 会话记录：{topic}")
    parts.append("")
    parts.append(f"**日期**: {date}")
    parts.append(f"**会话序号**: 第{int(seq)}次（当天）")
    parts.append(f"**会话轮次**: {turn_count}轮")
    if jsonl_id:
        parts.append(f"**jsonl来源**: {jsonl_id}.jsonl")
        # 记录jsonl完整路径，便于跨项目追溯
        jsonl_full_path = _find_jsonl_path(jsonl_id)
        if jsonl_full_path:
            parts.append(f"**jsonl路径**: {jsonl_full_path}")
    parts.append("")

    # 一、会话概述
    parts.append("## 一、会话概述")
    parts.append("")
    parts.append(f"本次会话主要围绕「{topic}」展开。首条用户输入：{first_msg}。")
    if tools:
        parts.append(f"使用的工具包括：{'、'.join(tools)}。")
    parts.append("")

    # 二、对话交互完整记录
    parts.append("## 二、对话交互完整记录")
    parts.append("")
    parts.append(restructured)
    parts.append("")

    # 三、变更文件清单
    parts.append("## 三、变更文件清单")
    parts.append("")
    if docs:
        parts.append("### 3.1. 新增/修改文件")
        parts.append("| 文件路径 | 说明 |")
        parts.append("|:---------|:-----|")
        for doc in docs:
            parts.append(f"| `{doc}` | 文档产出 |")
    else:
        parts.append("（本次会话未产生文件变更记录，详见对话内容中的工具调用）")
    parts.append("")

    # 四、涉及的规则/技能/提示词
    parts.append("## 四、涉及的规则/技能/提示词")
    parts.append("")
    refs = infer_rules_refs(topic)
    if refs:
        parts.extend(refs)
    else:
        parts.append("- （待补充）")
    parts.append("")

    content = '\n'.join(parts)

    # 输出文件名
    output_name = f"{seq}-{topic}.md"
    # 如果指定了 output_path，直接使用；否则按 sessions_dir/date/ 输出
    if output_path:
        output_path = Path(output_path)
    else:
        output_path = Path(sessions_dir) / date / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return {
        'output_path': str(output_path),
        'output_name': output_name,
        'turns': turn_count,
        'tools': tools,
        'docs': len(docs)
    }


def get_jsonl_birth_times(jsonl_dir, date_str=None):
    """获取 jsonl 文件的创建时间（birth time），按创建时间排序返回。

    [CRITICAL] 必须使用文件创建时间（birth time），严禁使用修改时间（mtime）。
    修改时间会在读取/写入时更新，导致跨天文件被错误计入当天排序。

    Args:
        jsonl_dir: jsonl 文件所在目录（~/.claude/projects/<project-id>/）
        date_str: 可选日期过滤 YYYY-MM-DD，只返回该日期的文件

    Returns:
        list of (jsonl_filename, birth_timestamp) 按创建时间升序排序
    """
    jsonl_path = Path(jsonl_dir)
    if not jsonl_path.exists():
        return []

    jsonl_files = sorted(jsonl_path.glob("*.jsonl"))
    if not jsonl_files:
        return []

    results = []
    system = platform.system()

    if system == "Windows":
        # Windows: 使用 PowerShell 获取 CreationTime（birth time）
        try:
            file_list = " ".join(str(f) for f in jsonl_files)
            cmd = (
                f'powershell -Command "Get-Item {file_list} | '
                f'Select-Object Name,CreationTime | '
                f'Sort-Object CreationTime | '
                f'ForEach-Object {{ $_.Name + \"`t\" + '
                f'$([long]($_.CreationTime - [datetime]::UnixEpoch).TotalSeconds) }}"'
            )
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in output.strip().split('\n'):
                if '\t' in line:
                    name, ts = line.split('\t', 1)
                    results.append((name.strip(), int(ts.strip())))
        except Exception:
            # Fallback: 使用 Python os.stat 的 st_ctime（Windows 上是创建时间）
            for f in jsonl_files:
                stat = f.stat()
                results.append((f.name, int(stat.st_ctime)))
    elif system == "Darwin":
        # macOS: 使用 stat -f "%B" 获取 birth time
        try:
            for f in jsonl_files:
                output = subprocess.check_output(
                    ['stat', '-f', '%B', str(f)],
                    text=True, stderr=subprocess.DEVNULL
                )
                results.append((f.name, int(output.strip())))
        except Exception:
            for f in jsonl_files:
                results.append((f.name, int(f.stat().st_birthtime)))
    else:
        # Linux: 使用 stat -c "%W" 获取 birth time
        try:
            for f in jsonl_files:
                output = subprocess.check_output(
                    ['stat', '-c', '%W', str(f)],
                    text=True, stderr=subprocess.DEVNULL
                )
                birth_ts = int(output.strip())
                if birth_ts == 0:
                    # 文件系统不支持 birth time，回退到 st_mtime（不推荐）
                    birth_ts = int(f.stat().st_mtime)
                results.append((f.name, birth_ts))
        except Exception:
            for f in jsonl_files:
                results.append((f.name, int(f.stat().st_mtime)))

    # 按创建时间排序
    results.sort(key=lambda x: x[1])

    # 按日期过滤
    if date_str:
        date_dt = datetime.strptime(date_str, "%Y-%m-%d")
        next_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
        day_start = date_dt.timestamp()
        day_end = next_dt.timestamp()
        results = [(n, t) for n, t in results if day_start <= t <= day_end]

    return results


def _get_single_birth_time(jsonl_file):
    """获取单个 jsonl 文件的创建时间（birth time）。

    Args:
        jsonl_file: Path 对象

    Returns:
        int 创建时间戳，失败返回 None
    """
    system = platform.system()
    if system == "Windows":
        try:
            stat = jsonl_file.stat()
            return int(stat.st_ctime)  # Windows 上 st_ctime 是创建时间
        except Exception:
            return None
    elif system == "Darwin":
        try:
            output = subprocess.check_output(
                ['stat', '-f', '%B', str(jsonl_file)],
                text=True, stderr=subprocess.DEVNULL
            )
            return int(output.strip())
        except Exception:
            return None
    else:
        # Linux: stat -c %W
        try:
            output = subprocess.check_output(
                ['stat', '-c', '%W', str(jsonl_file)],
                text=True, stderr=subprocess.DEVNULL
            )
            val = int(output.strip())
            return val if val > 0 else None
        except Exception:
            return None


def auto_determine_seq(jsonl_dir, date_str, target_jsonl_id):
    """根据 jsonl 文件创建时间自动确定每日会话序号。

    [CRITICAL] 使用文件创建时间（birth time）排序，严禁使用 ls -lt（修改时间）。

    Args:
        jsonl_dir: jsonl 文件所在目录
        date_str: 日期 YYYY-MM-DD
        target_jsonl_id: 目标会话的 jsonl 文件名（不含扩展名，如 dcb7cf79-971d-4838-b789-72f811a899c6）

    Returns:
        int: 会话序号（从 1 开始），未找到返回 0
    """
    birth_times = get_jsonl_birth_times(jsonl_dir, date_str)
    for idx, (filename, _ts) in enumerate(birth_times, 1):
        if filename.startswith(target_jsonl_id):
            return idx
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='会话记录 V3.1 格式化工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 单文件转换
  %(prog)s extracted.md --date 2026-04-10 --seq 01 --topic "CLAUDE.md更新" --jsonl-id 730dc0cb-...

  # 单文件转换（自动确定序号）
  %(prog)s extracted.md --date 2026-04-10 --topic "CLAUDE.md更新" --jsonl-id 730dc0cb-... --auto-seq --jsonl-dir ~/.claude/projects/<project-id>

  # 批量转换（配置JSON）
  %(prog)s --config sessions.json --sessions-dir ~/.claude/sessions/<项目名>

  # 列出当天所有会话的创建时间排序
  %(prog)s --list-sessions --jsonl-dir ~/.claude/projects/<project-id> --date 2026-04-11

注意：
  --auto-seq 使用文件创建时间（birth time）确定序号，严禁使用修改时间。
  不同平台获取 birth time 的方式：Linux(stat -c %%W)、macOS(stat -f %%B)、Windows(PowerShell CreationTime)
""")
    parser.add_argument('extracted_md', nargs='?', help='提取脚本输出的 markdown 文件')
    # 注意：当主题以 - 开头时，需用 -- 分隔，如: python format_sessions.py file.md --date ... -- --topic "-D-xxx"
    # 或通过 --extracted-md 选项传入避免歧义
    parser.add_argument('--extracted-md', dest='extracted_md_opt', help='提取脚本输出的 markdown 文件（选项形式，避免主题以-开头时的歧义）')
    parser.add_argument('--output', '-o', help='输出文件路径（默认自动生成）')
    parser.add_argument('--date', help='会话日期 YYYY-MM-DD')
    parser.add_argument('--seq', help='每日会话序号（01, 02, ...）')
    parser.add_argument('--topic', help='会话主题')
    parser.add_argument('--jsonl-id', help='jsonl 文件 ID')
    parser.add_argument('--batch-dir', help='批量模式：提取文件所在目录')
    parser.add_argument('--sessions-dir', default=str(DEFAULT_SESSIONS_DIR),
                        help='会话记录输出目录（默认自动检测项目名）')
    parser.add_argument('--config', help='批量模式：配置 JSON 文件')
    parser.add_argument('--auto-seq', action='store_true',
                        help='自动根据 jsonl 文件创建时间确定每日序号（需要 --jsonl-dir 和 --jsonl-id）')
    parser.add_argument('--auto-date', action='store_true',
                        help='自动从 jsonl 文件创建时间推导日期（需要 --jsonl-dir 和 --jsonl-id）')
    parser.add_argument('--jsonl-dir',
                        help='jsonl 文件所在目录（~/.claude/projects/<project-id>/），用于 --auto-seq')
    parser.add_argument('--list-sessions', action='store_true',
                        help='列出指定日期的所有会话及其创建时间排序（需要 --jsonl-dir）')

    args = parser.parse_args()

    # 兼容：--extracted-md 选项优先于 positional 参数
    if args.extracted_md_opt:
        args.extracted_md = args.extracted_md_opt

    # --list-sessions 模式：列出指定日期的所有会话及创建时间排序
    if args.list_sessions:
        if not args.jsonl_dir:
            print("错误: --list-sessions 需要 --jsonl-dir 参数", file=sys.stderr)
            sys.exit(1)
        date_filter = args.date or datetime.now().strftime("%Y-%m-%d")
        sessions = get_jsonl_birth_times(args.jsonl_dir, date_filter)
        print(f"日期: {date_filter} 的会话（按创建时间排序，共 {len(sessions)} 个）：", file=sys.stderr)
        print(f"{'序号':>4}  {'创建时间':>19}  文件名", file=sys.stderr)
        print("-" * 60, file=sys.stderr)
        for idx, (name, ts) in enumerate(sessions, 1):
            dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            print(f"{idx:>4}  {dt:>19}  {name}", file=sys.stderr)
        return

    if args.config:
        # 批量模式（配置JSON）
        with open(args.config, 'r', encoding='utf-8') as f:
            sessions = json.load(f)

        results = []
        for s in sessions:
            prefix = s.get('prefix', s.get('jsonl_id', '').split('-')[0])
            date = s['date']
            seq = s['seq']
            topic = s['topic']
            jsonl_id = s.get('jsonl_id', '')
            extract_file = s.get('extract_file', f"{args.batch_dir or ''}/{prefix}.md")

            print(f"处理: [{date}] {seq}-{topic}", file=sys.stderr)
            result = format_session(extract_file, date, seq, topic, jsonl_id, args.sessions_dir)
            if result:
                results.append(result)
                print(f"  [完成] {result['output_name']} ({result['turns']}轮, {len(result['tools'])}种工具)",
                      file=sys.stderr)
            else:
                print(f"  [跳过]", file=sys.stderr)

        print(f"\n处理完成: {len(results)}/{len(sessions)} 个会话", file=sys.stderr)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif args.extracted_md and args.date and args.topic:
        # --auto-date: 从 jsonl 创建时间推导日期（跨天会话用 jsonl 创建日期而非当前日期）
        date = args.date
        if args.auto_date:
            if not args.jsonl_dir or not args.jsonl_id:
                print("错误: --auto-date 需要 --jsonl-dir 和 --jsonl-id 参数", file=sys.stderr)
                sys.exit(1)
            jsonl_file = Path(args.jsonl_dir) / f"{args.jsonl_id}.jsonl"
            if not jsonl_file.exists():
                # 跨项目查找
                found = _find_jsonl_path(args.jsonl_id)
                if found:
                    jsonl_file = Path(found)
            if jsonl_file.exists():
                birth_ts = _get_single_birth_time(jsonl_file)
                if birth_ts:
                    date = datetime.fromtimestamp(birth_ts).strftime("%Y-%m-%d")
                    if date != args.date:
                        print(f"注意: --auto-date 推导日期 {date}（jsonl创建时间）与指定日期 {args.date} 不同，使用推导日期",
                              file=sys.stderr)
            else:
                print(f"警告: 未找到 jsonl 文件 {args.jsonl_id}，使用指定日期 {args.date}", file=sys.stderr)

        # 自动确定序号模式
        seq = args.seq
        if args.auto_seq:
            if not args.jsonl_dir or not args.jsonl_id:
                print("错误: --auto-seq 需要 --jsonl-dir 和 --jsonl-id 参数", file=sys.stderr)
                sys.exit(1)
            seq_num = auto_determine_seq(args.jsonl_dir, date, args.jsonl_id)
            if seq_num == 0:
                print(f"警告: 未找到 jsonl 文件 {args.jsonl_id}，无法自动确定序号", file=sys.stderr)
                sys.exit(1)
            seq = f"{seq_num:02d}"
            print(f"自动确定序号: {seq}（基于文件创建时间）", file=sys.stderr)

        if not seq:
            print("错误: 需要指定 --seq 或使用 --auto-seq", file=sys.stderr)
            sys.exit(1)

        # 单文件模式
        result = format_session(args.extracted_md, date, seq, args.topic,
                                args.jsonl_id or '', args.sessions_dir)
        if result:
            print(f"已生成: {result['output_path']}", file=sys.stderr)
            if args.output:
                # 同时输出到指定路径
                shutil.copy2(result['output_path'], args.output)
                print(f"已复制到: {args.output}", file=sys.stderr)
        else:
            print("处理失败", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
