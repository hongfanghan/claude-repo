#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""session-management 公共工具函数

提供自动检测项目名称、获取会话目录等功能。
"""

import os
import subprocess
import sys
from pathlib import Path


def detect_project_name():
    """通过git remote或工作目录名自动识别项目名

    优先级：
    1. 命令行参数 --project
    2. git remote origin URL 中的项目名
    3. 当前工作目录名

    Returns:
        str: 检测到的项目名称
    """
    # 检查命令行参数
    if '--project' in sys.argv:
        idx = sys.argv.index('--project')
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]

    # 尝试从git remote获取项目名
    try:
        remote_url = subprocess.check_output(
            ['git', 'remote', 'get-url', 'origin'],
            stderr=subprocess.DEVNULL, text=True, timeout=5
        ).strip()
        if remote_url:
            # 从URL中提取项目目录名
            # gitlab.example.com:81/group/project -> project
            # https://github.com/user/repo.git -> repo
            url = remote_url.rstrip('/')
            if url.endswith('.git'):
                url = url[:-4]
            proj_name = os.path.splitext(os.path.basename(url))[0]
            if proj_name:
                return proj_name
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 从当前工作目录名获取
    cwd = os.getcwd()
    return os.path.basename(cwd)


def get_sessions_dir(project_name=None):
    """获取会话保存目录: ~/.claude/sessions/{project_name}/

    Args:
        project_name: 项目名称，为None时自动检测

    Returns:
        str: 会话保存目录的绝对路径
    """
    if project_name is None:
        project_name = detect_project_name()
    return str(Path.home() / ".claude" / "sessions" / project_name)


def get_jsonl_dir(project_name=None):
    """获取JSONL会话目录: ~/.claude/projects/{encoded_path}/

    将当前工作目录编码为Claude项目路径格式:
    D:/Git/group/project_name -> D--Git-group-project_name

    Args:
        project_name: 项目名称（未使用，保留接口兼容）

    Returns:
        str: JSONL会话目录的绝对路径
    """
    cwd = os.getcwd()
    # Claude项目路径编码规则：冒号和斜杠都替换为短横线
    encoded = cwd.replace(':', '-').replace('\\', '-').replace('/', '-')
    return str(Path.home() / ".claude" / "projects" / encoded)
