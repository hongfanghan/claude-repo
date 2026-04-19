# session-save 详细参考文档

> 本文件为 SKILL.md 的补充参考资料，包含完整模板、详细示例和权限配置。

---

## 1. 会话记录完整模板

```markdown
# 会话记录：[主题]

**日期**: YYYY-MM-DD
**会话序号**: 第N次（当天）
**会话轮次**: N轮
**jsonl来源**: <session-id>.jsonl
**jsonl路径**: ~/.claude/projects/<project-id>/<session-id>.jsonl
**保存模式**: 完整模式（必须从 jsonl 提取完整对话内容）

## 一、会话概述

本次会话执行了以下工作：

1. **[任务1名称]**：[一句话描述]
2. **[任务2名称]**：[一句话描述]

## 二、对话交互完整记录

### 第1轮对话

**用户输入**:
> [用户原始输入内容，完整保留]

**AI回复**:
[AI回复的完整文本内容，包括表格、代码块、列表等]

**AI文档产出**:
- `D:\Git\group\project\路径\文件名.md` — 说明

**AI思考链**:
1. **需求分析**：
   - 用户要求：[具体要求]
   - 隐含需求：[隐含需求]
2. **方案制定**：
   - 方案选项：(A) ... (B) ... (C) ...
   - 选择依据：选择X，因为[原因]
3. **工具选择**：
   - 选择工具：[工具名称]
   - 选择原因：[原因]
4. **执行验证**：
   - 关键检查点：[检查点]
   - 结果确认：[确认结果]

**参考文档**:
- `文件路径` - 参考内容说明

**工具调用示例**:
- **Bash**: `命令描述` → 结果摘要
- **Read**: `文件描述` → 结果摘要
- （本轮无工具调用）

---

### 第N轮对话

[结构同上]

## 三、变更文件清单

### 3.1. 新增文件
| 文件路径 | 说明 |
|:---------|:-----|
| `路径\文件名.md` | 说明 |

### 3.2. 修改文件
| 文件路径 | 变更内容 |
|:---------|:---------|
| `路径\文件名.md` | 变更描述 |

## 四、涉及的规则/技能/提示词
- `.claude/skills/xxx/SKILL.md` — 技能说明
- `rules/xxx/xxx.md` — 规则说明
```

---

## 2. 详细规范

### 2.1. AI思考链规范

**禁止使用的通用占位符**：
- ~~"根据用户输入确定任务目标"~~
- ~~"选择合适的工具和方法"~~
- ~~"执行操作并验证结果"~~

**正确示例**：
```
1. **需求分析**：
   - 用户要求检查openspec完整性并更新
   - 隐含需求：需要对比代码实际状态和规范文档
2. **方案制定**：
   - 选择B（Agent并行探索），因为3个目录间无依赖
3. **工具选择**：
   - Agent(subagent_type=Explore) x 3 并行
4. **执行验证**：
   - 确认每个规范文件的最新版本与代码状态一致
```

### 2.2. "完整AI回复内容"的定义

**必须保留**：结论性文字、表格、代码块、列表/步骤、关键引用、Mermaid图表

**可精简**：工具原始输出（保留关键信息）、中间过程描述（精简为一行）、格式化问候语（省略）

**判定标准**：省略后读者无法还原 AI 的核心分析和结论 → 即为"摘要"而非"完整内容"。

### 2.3. 轮次合并规则详细说明

| jsonl 消息序列 | 轮次处理 | 说明 |
|:---------------|:---------|:-----|
| user(文本) → assistant → user(文本) → assistant | 2轮 | 正常对话 |
| user(文本) → assistant(tool_call) → user(tool_result) → assistant(tool_call) → user(tool_result) → assistant(文本) | **1轮** | 工具结果链合并 |
| user(文本) → assistant(文本) | 1轮 | AI直接回复 |

### 2.4. 系统注入消息过滤代码

```python
def is_system_injected(content):
    if not content or not content.strip():
        return True
    if 'This session is being continued' in content:
        return True
    if content.startswith('Summary:') or content.startswith('Analysis:'):
        return True
    if '<system-reminder>' in content:
        return True
    return False
```

### 2.5. 序号确定方法

```
1. 获取当前会话的 jsonl 文件路径
2. 用 stat -c "%W" 获取该 jsonl 的创建时间（birth time）
3. 列出当天该项目的所有 jsonl 文件，按创建时间从早到晚排序
4. 当前会话在排序中的位置即为序号
5. 已保存的会话记录文件（已有序号前缀）不参与计算
```

Windows 命令（Git Bash）：
```bash
stat -c "%W %n" ~/.claude/projects/<project-id>/*.jsonl | sort -n | tail -N
```

### 2.6. 常见格式缺陷与修复

| 缺陷类型 | 表现 | 修复方式 |
|:---------|:-----|:---------|
| TODO占位符 | `<!-- TODO: ... -->` 残留 | 手动删除或重新生成 |
| 过长工具调用行 | 超过200字符 | `fix-session-format.py` 自动截断 |
| 裸露代码行 | 多行Bash命令换行导致 | `fix-session-format.py` 自动合并 |
| 代码围栏未闭合 | 奇数个 ` ``` ` | 手动修复 |
| 用户输入缺少引用 | 无 `>` 前缀 | 手动修复 |

---

## 3. 批量处理完整流程

```bash
# Step 1: 批量提取所有 jsonl
for id in <session-id-1> <session-id-2> ...; do
  python ${CLAUDE_SKILL_DIR}/scripts/read-jsonl.py \
    ~/.claude/projects/<project-id>/${id}.jsonl --compact \
    -o <临时目录>/${id%%-*}.md
done

# Step 2: 批量格式化为 V3.3
python ${CLAUDE_SKILL_DIR}/scripts/format_sessions.py \
  --config <配置文件.json>

# 配置 JSON 格式：
# [{"prefix":"730dc0cb","date":"2026-04-09","seq":"01","topic":"主题","jsonl_id":"730dc0cb-..."}]
```

---

## 4. 权限配置

### 4.1. 必需权限清单

| 工具 | 权限规则 | 用途 |
|:-----|:---------|:-----|
| Read | `Read(~/.claude/**)` | 读取技能文件、会话记录 |
| Read | `Read(~/.claude/**/*.jsonl)` | 读取 jsonl 文件 |
| Write | `Write(~/.claude/sessions/**)` | 创建会话记录 |
| Edit | `Edit(~/.claude/sessions/**)` | 修改会话记录 |
| Bash | `Bash(~/.claude/projects/**)` | 对 jsonl 执行操作 |
| Bash | `Bash(~/.claude/sessions/**)` | 操作会话目录 |
| Bash | `Bash(stat:*)` | 获取文件创建时间 |
| Bash | `Bash(sort:*)` | 排序 jsonl 文件 |
| Bash | `Bash(wc:*)` | 统计行数 |
| Bash | `Bash(python:*)` | 运行脚本 |
| Glob | `Glob(~/.claude/**)` | 搜索文件 |
| Grep | `Grep(~/.claude/**)` | 搜索文件内容 |

### 4.2. 注意事项

- `Bash(mkdir:*)` 不可靠，创建会话目录应使用 Write 工具
- `Bash(stat:*)` 是确定会话序号的必需权限
- 权限变更后需重启 Claude Code 会话

---

## 5. 完整版本历史

| 版本 | 日期 | 变更说明 |
|:-----|:-----|:---------|
| V4.0 | 2026-04-20 | 从 session-management 拆分独立；新增步骤0.5时间范围筛选；移除审计功能 |
| V3.7 | 2026-04-19 | A05规则增加预留目录豁免机制 |
| V3.6 | 2026-04-19 | 新增步骤0已保存会话去重 |
| V3.5 | 2026-04-19 | 新增步骤2.5审计（已移至 session-audit） |
| V3.4 | 2026-04-18 | 轮次合并规则、系统消息过滤、格式检查修复 |
| V3.3 | 2026-04-13 | 统一完整模式；变更检测从jsonl提取；跨天规则 |
| V3.1 | 2026-04-11 | 新增每日会话序号前缀 |
| V3.0 | 2026-04-07 | 新增完整会话文件整理规范 |
| V2.9 | 2026-04-02 | 主题命名规范 |
| V2.8 | 2026-04-02 | 验证报告模板更新 |
| V2.7 | 2026-04-01 | 完整性强制验证 |
| V2.6 | 2026-04-01 | hooks 配合提醒 |
| V2.5 | 2026-04-01 | 新增 read-jsonl.py |
| V2.4 | 2026-04-01 | 压缩前会话保存 |
| V2.3 | 2026-04-01 | 用户级单位置保存 |
| V2.2 | 2026-04-01 | 双位置保存 |
| V2.0 | 2026-03-26 | 重构为官方格式 |
| V1.8 | 2026-03-25 | 压缩前保存 |
| V1.7 | 2026-03-14 | 完整AI回复 |
| V1.6 | 2026-03-13 | 对话交互记录 |
