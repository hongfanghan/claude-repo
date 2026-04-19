---
name: session-audit
description: 会话审计。触发词：审计会话、检查会话质量、文档优化检查
user-invocable: true
---

# 会话审计技能

对已保存的会话记录和 AI 体系文档进行质量审计，识别缺陷和优化机会。

---

## 1. 触发条件

### 1.1. 手动触发

- "审计会话"
- "检查会话质量"
- "文档优化检查"
- "文档审计"

### 1.2. 自动触发（由 session-save 调用）

| 条件 | 判断方法 |
|:-----|:---------|
| 本次会话有AI体系文档变更 | 步骤2已标记（`.claude/skills/`、`rules/`、`CLAUDE.md`等） |
| 会话持续时间超过60分钟 | jsonl文件首末消息时间差 |
| 距上次审计超过5次会话 | 对比 `audit-todos.json` 中的 `last_audit_session` |
| 新增了技能或规则文件 | 变更清单含 `skills/*/SKILL.md` 或 `rules/*.md` |

---

## 2. 执行流程

### 步骤1：时间范围筛选

手动触发时，使用 AskUserQuestion 询问时间范围：

| 选项 | 含义 | jsonl 筛选方法 |
|:-----|:-----|:---------------|
| a-本次 | 仅当前会话 | 当前 session-id |
| b-当天 | 今天所有会话 | `stat -c "%W"` 筛选当天 |
| c-3天内 | 近3天所有会话 | `stat -c "%W"` 筛选3天内 |
| d-其他 | 用户指定天数 N | `stat -c "%W"` 筛选 N 天内 |

### 步骤2：静态检查（A01-A08 规则引擎）

> **[IMPORTANT]** 使用纯规则引擎检测（路径存在性、标题匹配等），不消耗 LLM 资源。

| 规则ID | 规则名称 | 检测方法 | 优先级 |
|:-------|:---------|:---------|:-------|
| A01 | 引用文件缺失 | 遍历SKILL.md中引用的文件路径，检查是否存在 | HIGH |
| A02 | 章节引用悬空 | 检查SKILL.md中引用的章节编号在目标文件中是否存在 | HIGH |
| A03 | 文档内容重复 | 检查CLAUDE.md与 `rules/*.md` 之间是否存在相同标题的规则条目 | LOW |
| A04 | 索引文件过期 | 检查 `skills/README.md` 技能清单与实际文件是否一致 | MEDIUM |
| A05 | 目录结构缺失 | 检查SKILL.md引用的目录是否存在。**豁免**：标注"预留"的目录 | MEDIUM |
| A06 | 版本号不一致 | 检查SKILL.md版本历史最新版本与README.md中标注的版本是否一致 | LOW |
| A07 | 权限配置过时 | 检查 `settings.json` 权限是否覆盖SKILL.md必需权限 | MEDIUM |
| A08 | 脚本引用验证 | 检查SKILL.md中引用的脚本路径是否在 `scripts/` 下实际存在 | MEDIUM |

```bash
# A01: 检查引用文件是否存在
grep -oP '(?<=`)[^`]*\.md(?=`)' ~/.claude/skills/<skill>/SKILL.md | while read f; do
  [ ! -f "$f" ] && echo "A01:MISSING:$f"
done

# A08: 检查脚本路径是否存在
grep -oP '~/.claude/skills/[^/ ]+/scripts/[^\s`)]+\.py' ~/.claude/skills/<skill>/SKILL.md | while read f; do
  [ ! -f "$f" ] && echo "A08:MISSING:$f"
done
```

### 步骤3：会话内容语义审计（S01-S07）

> **[CRITICAL]** 这是审计的核心能力。读取被审计会话的 jsonl 内容，分析对话中的执行过程，识别缺陷和优化机会。

| 模式ID | 模式名称 | 检测方法 | 优先级 |
|:-------|:---------|:---------|:-------|
| S01 | 技能执行失败/绕行 | AI 执行某技能时遇到错误，不得不绕过或手动替代 | HIGH |
| S02 | 脚本缺陷 | 调用的 .py 脚本报错、输出错误、或需要手动修补 | HIGH |
| S03 | 用户多次纠正同类错误 | 用户在同一会话中 2 次以上纠正 AI 的同类行为 | HIGH |
| S04 | 规则违反 | AI 执行了 rules 中明确禁止的操作 | HIGH |
| S05 | 规则缺失 | AI 不得不自行判断，而此事应有明确规则但没有 | MEDIUM |
| S06 | 知识缺失 | AI 多次搜索/查阅同一外部信息 | MEDIUM |
| S07 | 重复低效模式 | 同一手动绕行方式在多个会话中出现 | MEDIUM |

**执行方法**：
```
[ ] 逐轮阅读对话内容，标记以下事件：
    - AI 报错/异常（S01, S02）
    - 用户纠正 AI 的内容（S03, S04）
    - AI 表示不确定/需要猜测/自行判断（S05）
    - AI 多次搜索同一主题（S06）
[ ] 将标记的事件与检测模式匹配
[ ] 对比 audit-todos.json 历史条目，识别重复模式（S07）
[ ] 去重后写入 audit-todos.json
```

> **[CRITICAL]** S05/S07 必须先检查 `rules/global-mandatory-rules.md` 是否已有覆盖，只有全局规则确实未覆盖时才创建新条目。

### 步骤4：输出审计报告

```
[审计结果]
  本次新发现：N条（IMMEDIATE: N, DEFERRED: N）
  历史未解决：N条（IMMEDIATE: N, DEFERRED: N）
  已解决：N条

[IMMEDIATE 条目详情]
  - A01-001: [描述] → [建议]
  - S01-002: [描述] → [建议]

[WARNING] 积累 IMMEDIATE 审计条目已达 N 条，建议安排专门会话处理。
```

---

## 3. 审计条目管理

### 3.1. 审计条目格式

写入 `~/.claude/audit-todos.json`：

```json
{
  "id": "A01-001",
  "rule_id": "A01",
  "priority": "HIGH",
  "target_path": "ai-docs-list.md",
  "description": "SKILL.md引用的 ai-docs-list.md 文件不存在",
  "suggestion": "创建 ai-docs-list.md 或移除SKILL.md中的引用",
  "status": "OPEN",
  "type": "IMMEDIATE",
  "created_at": "2026-04-19",
  "created_in_session": "01-XXX",
  "resolved_at": null
}
```

语义审计条目额外字段：
```json
{
  "source_session": "session-id",
  "source_round": "第3轮"
}
```

### 3.2. IMMEDIATE vs DEFERDED

| 类型 | 含义 | 处理方式 |
|:-----|:-----|:---------|
| IMMEDIATE | 文档结构性问题，应尽快修复 | 写入审计报告，提醒用户确认是否立即修复 |
| DEFERRED | 优化改进项，可在后续会话处理 | 仅写入 audit-todos.json |

**优先级映射**：HIGH → IMMEDIATE，MEDIUM/LOW → DEFERRED

| 模式 | 默认类型 | 理由 |
|:-----|:---------|:-----|
| S01 技能执行失败 | IMMEDIATE | 技能缺陷直接影响后续使用 |
| S02 脚本缺陷 | IMMEDIATE | 脚本 bug 导致自动化失败 |
| S03 用户多次纠正 | IMMEDIATE | 规则严重缺失 |
| S04 规则违反 | IMMEDIATE | 违反规则是严重问题 |
| S05 规则缺失 | DEFERRED | 新规则建议可延后 |
| S06 知识缺失 | DEFERRED | 知识补充可批量处理 |
| S07 重复低效模式 | DEFERRED | 优化改进项 |

### 3.3. 条目生命周期

```
OPEN --[用户或AI修复]--> RESOLVED
OPEN --[用户标记不修复]--> CLOSED
OPEN --[下次审计仍检测到]--> 保持OPEN（去重，更新created_at）
```

### 3.4. audit-todos.json 结构

```json
{
  "meta": {
    "version": "1.0",
    "last_audit_date": null,
    "last_audit_session": null,
    "total_created": 0,
    "total_resolved": 0
  },
  "items": []
}
```

去重规则：相同 `rule_id` + `target_path` 的条目不重复添加，仅更新 `created_at`。

---

## 4. 权限配置

| 工具 | 权限规则 | 用途 |
|:-----|:---------|:-----|
| Read | `Read(~/.claude/**)` | 读取技能文件、会话记录、jsonl |
| Read | `Read(~/.claude/**/*.jsonl)` | 读取 jsonl 进行语义审计 |
| Write | `Write(~/.claude/audit-todos.json)` | 创建/更新审计持久化文件 |
| Edit | `Edit(~/.claude/audit-todos.json)` | 编辑审计文件 |
| Glob | `Glob(~/.claude/**)` | 搜索文件 |
| Grep | `Grep(~/.claude/**)` | 搜索文件内容 |

---

## 5. 版本历史

| 版本 | 日期 | 变更说明 |
|:-----|:-----|:---------|
| V4.0 | 2026-04-20 | 从 session-management 拆分独立；新增时间范围筛选 |
| V3.7 | 2026-04-19 | A05规则增加预留目录豁免；语义审计增加交叉引用全局规则 |
| V3.5 | 2026-04-19 | 新增审计功能（A01-A08静态检查 + S01-S07语义审计） |
