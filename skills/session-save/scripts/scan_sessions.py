"""扫描jsonl会话文件，提取首条用户消息和基本信息"""
import json
import os
import sys

base = os.path.expanduser("~/.claude/projects")

sessions = [
    ("D--YHFin-Project-AI--", "4d280b7e-35d9-459b-842f-415db9328af8"),
    ("D--YHFin-Project-AI--", "fa81309c-56a4-4805-87b0-e632a1f2024f"),
    ("D--YHFin-Project-AI---claude-app", "31068e02-8f1f-4f5e-8d8c-63968acfa119"),
    ("D--YHFin-Project-AI---claude-app", "62f56501-4507-4ba5-ab15-a306611749e4"),
    ("D--YHFin-Project-AI---claude-app", "d40ef405-6963-4c9c-af01-c466b477ec9e"),
    ("D--YHFin-Project-AI---claude-app", "a4b9ed31-8d95-4c0f-8d55-3041d85eeade"),
    ("D--YHFin-Project-AI---claude-app", "6194929c-4257-4f17-abbe-6e5266148382"),
    ("D--YHFin-Project-AI---claude-app", "a761d7df-69f1-437e-a10d-2c898831de0c"),
    ("D--YHFin-Project-AI---claude-app", "8e35efd7-0bba-4c77-a224-418055e2880e"),
    ("C--Users-hongfh--claude", "741a0353-a9da-4f79-91d4-ecdbae978756"),
    ("C--Users-hongfh--claude", "39be2988-bf0f-4f68-82ef-686aff2c34d5"),
    ("C--Users-hongfh--claude", "8b101d23-b885-401d-988a-4009f42932bb"),
]

for proj, sid in sessions:
    fpath = os.path.join(base, proj, f"{sid}.jsonl")
    if not os.path.exists(fpath):
        print(f"[{sid[:8]}] FILE NOT FOUND")
        continue

    lines_count = sum(1 for _ in open(fpath, encoding="utf-8", errors="replace"))
    user_count = 0
    asst_count = 0
    first_msg = ""

    with open(fpath, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                obj = json.loads(line.strip())
            except Exception:
                continue
            t = obj.get("type", "")
            if t == "user":
                user_count += 1
                if not first_msg:
                    msg = obj.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        texts = [
                            x.get("text", "")
                            for x in content
                            if isinstance(x, dict) and x.get("type") == "text"
                        ]
                        content = " ".join(texts)
                    if isinstance(content, str) and len(content) > 10:
                        if (
                            "<system-reminder>" not in content
                            and "This session is being continued" not in content
                            and "<command-" not in content
                        ):
                            first_msg = content[:150].replace("\r", "").replace("\n", " ")[:120]
            elif t == "assistant":
                asst_count += 1

    print(f"[{sid[:8]}] {lines_count}行 u={user_count} a={asst_count} | {first_msg}")
