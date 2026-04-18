#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[已废弃] jsonl会话历史读取脚本

警告：亿赛通加密环境下无法正确读取jsonl文件，请改用Read工具。

用途：读取Claude Code的jsonl会话历史文件，提取完整对话内容
位置：~/.claude/projects/<project-id>/*.jsonl

使用方法：
    python read-jsonl.py <jsonl_file_path> [--output <output_file>] [--format markdown|text|json]

参数：
    jsonl_file_path: jsonl文件路径
    --output, -o: 可选，输出到指定文件
    --format, -f: 输出格式，支持 markdown/text/json，默认markdown
    --timestamp: 显示时间戳（默认不显示，与会话记录规范一致）
    --summary: 只显示统计信息
    --no-tools: 不包含工具调用细节，只输出文本对话内容
    --compact: 紧凑模式，合并连续的AI回复，只保留有实际内容的消息

示例：
    python read-jsonl.py ~/.claude/projects/{project-path}/{session-id}.jsonl
    python read-jsonl.py ~/.claude/projects/{project-path}/{session-id}.jsonl -o session.md
    python read-jsonl.py ~/.claude/projects/{project-path}/{session-id}.jsonl --no-tools --compact
"""

import json
import re
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path


def parse_jsonl(file_path, include_tools=True):
    """解析jsonl文件，提取对话内容

    Args:
        file_path: jsonl文件路径
        include_tools: 是否包含工具调用细节
    """
    messages = []
    stats = {
        'total_lines': 0,
        'user_messages': 0,
        'assistant_messages': 0,
        'tool_uses': 0,
        'errors': 0
    }

    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            stats['total_lines'] += 1
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                msg_type = data.get('type', '')

                # 处理不同类型的消息
                if msg_type == 'user':
                    stats['user_messages'] += 1
                    message = data.get('message', {})
                    role = 'user'
                    content = extract_content(message.get('content', ''), include_tools=include_tools)
                    timestamp = data.get('timestamp', '')

                    # 只保存有实际内容的消息
                    if content.strip():
                        messages.append({
                            'role': role,
                            'content': content,
                            'timestamp': timestamp,
                            'line_num': line_num,
                            'type': 'user'
                        })

                elif msg_type == 'assistant':
                    stats['assistant_messages'] += 1
                    message = data.get('message', {})
                    role = 'assistant'
                    content = extract_content(message.get('content', ''), include_tools=include_tools)
                    timestamp = data.get('timestamp', '')

                    # 检查是否有工具调用
                    if message.get('content') and isinstance(message['content'], list):
                        for item in message['content']:
                            if item.get('type') == 'tool_use':
                                stats['tool_uses'] += 1

                    # 只保存有实际内容的消息
                    if content.strip():
                        messages.append({
                            'role': role,
                            'content': content,
                            'timestamp': timestamp,
                            'line_num': line_num,
                            'type': 'assistant'
                        })

            except json.JSONDecodeError as e:
                stats['errors'] += 1
                print(f"警告: 第{line_num}行JSON解析失败: {e}", file=sys.stderr)
                continue

    return messages, stats


def downgrade_headings(content, levels=2):
    """将markdown标题降级指定级数，避免与外层轮次标题层级冲突

    Args:
        content: 原始内容
        levels: 降级的级数
    """
    lines = content.split('\n')
    result = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('#'):
            count = 0
            for c in stripped:
                if c == '#':
                    count += 1
                else:
                    break
            new_count = min(count + levels, 6)
            indent = len(line) - len(stripped)
            result.append(' ' * indent + '#' * new_count + stripped[count:])
        else:
            result.append(line)
    return '\n'.join(result)


def sanitize_topic(text):
    """清理轮次主题文本，去除HTML标签和特殊字符

    Args:
        text: 原始主题文本
    """
    # 去除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 去除markdown标题标记
    text = text.lstrip('#').strip()
    return text


def extract_content(content, include_tools=True, max_tool_result_length=500):
    """提取内容，处理不同的格式

    Args:
        content: 原始内容
        include_tools: 是否包含工具调用细节
        max_tool_result_length: 工具结果的最大显示长度（0表示不显示结果）
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        tool_calls = []  # 收集工具调用

        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    text = item.get('text', '').strip()
                    if text:
                        text_parts.append(text)
                elif item.get('type') == 'tool_use':
                    tool_name = item.get('name', 'unknown')
                    tool_input = item.get('input', {})
                    # 格式化工具调用
                    if include_tools:
                        tool_calls.append(format_tool_call(tool_name, tool_input))
                elif item.get('type') == 'tool_result':
                    # 工具结果不包含在消息中，由后续的user消息处理
                    pass
            else:
                text_parts.append(str(item))

        # 添加工具调用摘要
        if tool_calls:
            text_parts.append('\n\n**工具调用:**\n' + '\n'.join(tool_calls))

        return '\n'.join(text_parts)
    else:
        return str(content)


def format_tool_call(tool_name, tool_input):
    """格式化工具调用为可读格式"""
    if tool_name == 'Read':
        return f"- Read: `{tool_input.get('file_path', 'unknown')}`"
    elif tool_name == 'Edit':
        old = tool_input.get('old_string', '')[:50]
        new = tool_input.get('new_string', '')[:50]
        return f"- Edit: 修改内容 (旧: '{old}...' → 新: '{new}...')"
    elif tool_name == 'Write':
        return f"- Write: `{tool_input.get('file_path', 'unknown')}`"
    elif tool_name == 'Bash':
        cmd = tool_input.get('command', '')[:100]
        return f"- Bash: `{cmd}`"
    elif tool_name == 'Grep':
        pattern = tool_input.get('pattern', '')
        path = tool_input.get('path', '')
        return f"- Grep: 搜索 '{pattern}' 在 {path}"
    elif tool_name == 'Glob':
        pattern = tool_input.get('pattern', '')
        path = tool_input.get('path', '')
        return f"- Glob: 查找 '{pattern}' 在 {path}"
    elif tool_name == 'Agent':
        return f"- Agent: {tool_input.get('description', 'unknown')}"
    elif tool_name == 'Skill':
        return f"- Skill: {tool_input.get('skill', 'unknown')}"
    else:
        # 其他工具，显示简化的参数
        params_str = ''
        if tool_input:
            params_str = str(tool_input)[:100]
        return f"- {tool_name}: {params_str}"


def format_markdown(messages, include_timestamp=True, show_summary=False, compact=False):
    """格式化为Markdown输出

    Args:
        messages: 消息列表
        include_timestamp: 是否包含时间戳
        show_summary: 是否只显示摘要
        compact: 紧凑模式，按对话轮次组织（用户输入+AI回复为一轮）
    """
    output = []

    if not show_summary:
        output.append("# 会话记录\n")
        output.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"**消息总数**: {len(messages)}条")
        output.append("\n---\n")

    if compact:
        # 紧凑模式：按对话轮次组织（用户输入+AI回复为一轮）
        # 1. 先合并连续同角色消息
        merged_messages = []
        current_msg = None
        for msg in messages:
            if current_msg is None:
                current_msg = msg.copy()
            elif msg['role'] == current_msg['role']:
                current_msg['content'] += '\n\n' + msg['content']
                current_msg['timestamp'] = msg['timestamp']
            else:
                if current_msg['content'].strip():
                    merged_messages.append(current_msg)
                current_msg = msg.copy()
        if current_msg and current_msg['content'].strip():
            merged_messages.append(current_msg)

        # 2. 按轮次组织：用户消息为轮次起点，后续AI回复归入同一轮
        rounds = []
        current_round = None
        for msg in merged_messages:
            if msg['role'] == 'user':
                # 新轮次
                if current_round:
                    rounds.append(current_round)
                current_round = {'user': msg, 'assistant': None}
            elif msg['role'] == 'assistant':
                # AI回复归入当前轮次
                if current_round:
                    if current_round['assistant'] is None:
                        current_round['assistant'] = msg
                    else:
                        current_round['assistant']['content'] += '\n\n' + msg['content']
        if current_round:
            rounds.append(current_round)

        # 3. 输出按轮次格式
        for i, rnd in enumerate(rounds, 1):
            user_text = rnd['user']['content'].strip()
            # 清理轮次主题：去除HTML标签、markdown标题标记
            first_line = sanitize_topic(user_text.split('\n')[0])
            topic = first_line[:60]
            if len(first_line) > 60:
                topic += '...'

            output.append(f"## {i}. {topic}\n")
            output.append(f"### {i}.1. 用户输入\n")
            # 用户输入内容中的标题降2级，避免与轮次标题冲突
            output.append(f"> {downgrade_headings(user_text)}\n")

            if rnd['assistant']:
                output.append(f"### {i}.2. AI回复\n")
                # AI回复内容中的标题降2级，避免与轮次标题冲突
                output.append(f"{downgrade_headings(rnd['assistant']['content'])}\n")

            output.append("---\n")

        return '\n'.join(output)

    # 非紧凑模式：逐条输出
    for i, msg in enumerate(messages, 1):
        role_label = "用户" if msg['role'] == 'user' else "AI助手"
        timestamp_str = ""
        if include_timestamp and msg['timestamp']:
            try:
                dt = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                timestamp_str = f" _{dt.strftime('%H:%M:%S')}_"
            except (ValueError, OSError, KeyError):
                pass

        output.append(f"### {i}. {role_label}{timestamp_str}\n")

        if msg['role'] == 'user':
            output.append(f"> {msg['content']}\n")
        else:
            output.append(f"{msg['content']}\n")

        output.append("---\n")

    return '\n'.join(output)


def format_text(messages, include_timestamp=True):
    """格式化为纯文本输出"""
    output = []
    output.append(f"会话记录 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append(f"消息总数: {len(messages)}条")
    output.append("=" * 60)

    for i, msg in enumerate(messages, 1):
        role_label = "用户" if msg['role'] == 'user' else "AI助手"
        timestamp_str = ""
        if include_timestamp and msg['timestamp']:
            try:
                dt = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                timestamp_str = f" [{dt.strftime('%H:%M:%S')}]"
            except (ValueError, OSError, KeyError):
                pass

        output.append(f"\n[{i}] {role_label}{timestamp_str}")
        output.append("-" * 40)
        output.append(msg['content'])
        output.append("-" * 40)

    return '\n'.join(output)


def format_json(messages, stats):
    """格式化为JSON输出"""
    output = {
        'metadata': {
            'export_time': datetime.now().isoformat(),
            'total_messages': len(messages),
            'statistics': stats
        },
        'messages': messages
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='读取Claude Code jsonl会话历史',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('jsonl_file', help='jsonl文件路径')
    parser.add_argument('--output', '-o', help='输出文件路径（可选）')
    parser.add_argument('--format', '-f', choices=['markdown', 'text', 'json'],
                       default='markdown', help='输出格式，默认markdown')
    parser.add_argument('--timestamp', action='store_true', help='显示时间戳（默认不显示）')
    parser.add_argument('--summary', action='store_true', help='只显示统计信息')
    parser.add_argument('--no-tools', action='store_true',
                       help='不包含工具调用细节，只输出文本对话内容')
    parser.add_argument('--compact', '-c', action='store_true',
                       help='紧凑模式，合并连续的同角色消息')

    args = parser.parse_args()

    # 展开路径
    jsonl_path = Path(args.jsonl_file).expanduser()

    if not jsonl_path.exists():
        print(f"错误: 文件不存在 - {jsonl_path}", file=sys.stderr)
        sys.exit(1)

    # 解析jsonl
    print(f"正在解析文件: {jsonl_path}", file=sys.stderr)
    include_tools = not args.no_tools
    messages, stats = parse_jsonl(jsonl_path, include_tools=include_tools)

    # 显示统计信息
    print(f"\n统计信息:", file=sys.stderr)
    print(f"  总行数: {stats['total_lines']}", file=sys.stderr)
    print(f"  用户消息: {stats['user_messages']} 条", file=sys.stderr)
    print(f"  AI消息: {stats['assistant_messages']} 条", file=sys.stderr)
    print(f"  工具调用: {stats['tool_uses']} 次", file=sys.stderr)
    print(f"  有效消息: {len(messages)} 条", file=sys.stderr)
    if stats['errors'] > 0:
        print(f"  解析错误: {stats['errors']} 处", file=sys.stderr)
    print(file=sys.stderr)

    if args.summary:
        return

    if not messages:
        print("警告: 未找到任何有效消息", file=sys.stderr)
        sys.exit(0)

    # 格式化输出
    if args.format == 'markdown':
        formatted = format_markdown(messages, include_timestamp=args.timestamp, compact=args.compact)
    elif args.format == 'text':
        formatted = format_text(messages, include_timestamp=args.timestamp)
    elif args.format == 'json':
        formatted = format_json(messages, stats)
    else:
        formatted = format_markdown(messages, include_timestamp=args.timestamp, compact=args.compact)

    # 输出
    if args.output:
        output_path = Path(args.output).expanduser()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(formatted)
        print(f"已保存到: {output_path}", file=sys.stderr)
        print(f"   共提取 {len(messages)} 条有效消息", file=sys.stderr)
        if args.no_tools:
            print(f"   模式: 仅文本内容（不含工具调用详情）", file=sys.stderr)
        if args.compact:
            print(f"   模式: 紧凑格式（合并连续消息）", file=sys.stderr)
    else:
        print(formatted)


if __name__ == '__main__':
    main()
