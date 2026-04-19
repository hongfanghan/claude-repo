---
name: session-save
description: 会话保存。触发词：保存会话、结束会话
user-invocable: true
---

# 会话保存技能

**级别**: CRITICAL (强制执行)

---

## 1. 自动触发条件

### 1.1. 自动触发（无需用户提醒）

- 会话中新建了任何文档
- 会话中更新了任何现有文档
- 会话持续时间超过30分钟
- 用户说"完成了"、"好了"、"就这样"等
- **AI体系文档发生变更**（新增/修改/删除）

### 1.2. AI体系文档范围

| 目录 | 需更新的索引文件 |
|:-----|:-----------------|
| openspec/**/*.md | ai-docs-list.md 第2节 |
| .claude/skills/*/SKILL.md | ai-docs-list.md 第3节, CLAUDE.md 8.3节 |
| .claude/prompts/**/*.md | ai-docs-list.md 第4节（预留） |
| rules/**/*.md | ai-docs-list.md 第5节, CLAUDE.md 8.2节 |
| context/**/*.md | ai-docs-list.md 第6节（预留） |
| CLAUDE.md | ai-docs-list.md |

### 1.3. 手动触发词

"保存会话"、"更新文档索引"、"保存工作成果"、"更新AI文档索引"

### 1.4. 配合 hooks 提醒

hooks.json 的 PostToolUse + matcher: "Write|Edit" 提醒后，无需立即更新索引，在会话结束时执行 `/session-save` 统一更新。

---

## 2. 执行流程

### 步骤0：已保存会话去重（基于 jsonl 行号）

> **[CRITICAL]** 通过比较 md 记录的 `**jsonl行数**` 与 jsonl 实际行数，判断记录是否完整。

```
1. 扫描 ~/.claude/sessions/ 下所有 .md 文件，提取 jsonl来源（session-id）
2. 对每个已保存的记录：
   a. 读取 md 头部的 **jsonl行数** 字段
   b. 获取对应 jsonl 文件的实际行数
   c. 比较：
      - jsonl实际行数 > md记录行数 → 有新增对话，需**查漏补缺**
      - jsonl实际行数 == md记录行数 → 无新增，跳过
      - md 无 jsonl行数 字段（旧版）→ 视为完整，跳过（向后兼容）
3. 文件大小 < 1KB 视为保存不完整，需重新保存
4. 只处理：未保存的 + jsonl有新增的 会话
```

**去重判断逻辑**：

| 条件 | 判定 | 行为 |
|:-----|:-----|:-----|
| session-id 不存在 | 新会话 | 保存 |
| jsonl实际行数 > md记录行数 | 有新增对话 | **查漏补缺** |
| jsonl实际行数 == md记录行数 | 无新增 | 跳过 |
| md 无 jsonl行数 字段 | 旧版记录 | 视为完整，跳过 |

> **[CRITICAL]** 查漏补缺策略：读取已有 md 找到最后保存的轮次，从 jsonl 中提取新增的对话内容，追加到已有记录中（Edit），而非覆盖重写。

### 步骤0.5：时间范围筛选

手动触发时，使用 AskUserQuestion 询问时间范围：

| 选项 | 含义 | jsonl 筛选方法 |
|:-----|:-----|:---------------|
| a-本次 | 仅当前会话 | 当前 session-id |
| b-当天 | 今天所有会话 | `stat -c "%W"` 筛选当天 |
| c-3天内 | 近3天所有会话 | `stat -c "%W"` 筛选3天内 |
| d-其他 | 用户指定天数 N | `stat -c "%W"` 筛选 N 天内 |

自动触发时默认为"a-本次"。

### 步骤1：读取上次会话记录（变更检测基准）

从 `~/.claude/sessions/[项目名]/最新日期/` 提取上次变更的文件列表作为对比基准。

### 步骤2：确认本次会话的变更

> **[CRITICAL]** 变更检测必须基于本次会话的 jsonl 文件，**禁止使用 `git diff`**。

```
[ ] 从 jsonl 提取所有 Edit/Write 工具调用的 file_path
[ ] 过滤掉临时文件（temp/、会话记录、系统文件、plan文件等）
[ ] 标记是否有AI体系文档变更
```

### 步骤3：更新AI体系文档索引（如有变更）

- openspec/ 变更 → ai-docs-list.md 第2节
- .claude/skills/ 变更 → ai-docs-list.md 第3节 + CLAUDE.md 8.3节
- rules/ 变更 → ai-docs-list.md 第5节 + CLAUDE.md 8.2节

### 步骤4：更新子目录README

| 文档 | 更新内容 |
|------|----------|
| .claude/skills/README.md | 新增技能文档 |
| rules/README.md | 新增规则文档 |

### 步骤5：创建会话记录

**保存位置**: `~/.claude/sessions/[项目名]/YYYY-MM-DD/[序号]-[主题].md`

**[CRITICAL] md ↔ jsonl 一一对应**：每个 md 必须有且仅有一个对应的 jsonl 文件。

**md 头部必须记录**：
```
**jsonl来源**: <session-id>.jsonl
**jsonl路径**: ~/.claude/projects/<project-id>/<session-id>.jsonl
**jsonl行数**: <保存时jsonl的总行数>
**保存模式**: 完整模式（必须从 jsonl 提取完整对话内容）
```

**[CRITICAL] jsonl行数用途**：
- 下次 session-save 去重时，比较此值与 jsonl 实际行数
- 实际行数 > 此值 → 有新增对话，查漏补缺
- 实际行数 == 此值 → 无新增，跳过

**[CRITICAL] 日期规则**：会话记录目录的日期**必须使用 jsonl 文件的创建日期**（通过 `stat -c "%W"` 获取），而非当前日期。

**[CRITICAL] 序号规则**：序号按"会话打开时间"排序，不是保存时间排序。使用 `stat -c "%W"` 获取 birth time。

**5.1. jsonl 提取与格式化**

```bash
# 提取（备选脚本）
python ${CLAUDE_SKILL_DIR}/scripts/read-jsonl.py <jsonl路径> --compact --no-tools

# 格式化为 V3.3 模板
python ${CLAUDE_SKILL_DIR}/scripts/format_sessions.py <提取md> \
  --date YYYY-MM-DD --seq 01 --topic "主题" --jsonl-id <session-id>
```

**5.2. 主题命名**：`[序号]-[主题].md`，多主题用"+"连接（不超过5个）。

**5.3. 每轮对话的标准结构（4个强制子节）**

> **[CRITICAL]** 缺少任何一个子节即视为不合规。

```markdown
### 第N轮对话

**用户输入**:
> [完整保留用户原始输入]

**AI回复**:
[完整文本，保留结论、表格、代码块、列表]

**AI思考链**:
1. **需求分析**：[实际分析，禁止通用占位符]
2. **方案制定**：[实际方案选择]
3. **工具选择**：[实际使用的工具及原因]
4. **执行验证**：[实际验证过程]

**工具调用示例**:
- **Bash**: `命令` → 结果摘要
- （无工具调用则写"本轮无工具调用"）
```

可选子节（有则添加）：`**AI文档产出**:`、`**参考文档**:`

**5.3.1. 轮次合并规则**：jsonl 中 tool_result 链必须与前轮用户消息合并，禁止拆分为独立轮次。

**5.3.2. 系统注入消息过滤**：必须删除以下非用户输入：
- `This session is being continued from a previous conversation...`
- `Summary:\n\nAnalysis:` 开头的压缩摘要
- `<system-reminder>` 标签内容
- 空的 tool_result 消息

**5.4. 会话记录模板**（见 reference.md 第一节）

**5.5. 格式检查与修复**

```bash
python ${CLAUDE_SKILL_DIR}/scripts/check-session-completeness.py --check-all --format
python ${CLAUDE_SKILL_DIR}/scripts/fix-session-format.py <session_md_file>
```

**5.6. 上下文窗口保护规则**

> **[CRITICAL]** 多会话保存时，并行 agent 输出会快速消耗主会话上下文，导致 context window 超限崩溃。必须严格遵守以下规则。

**并行 agent 数量限制**：

| 需保存会话数 | agent 并行策略 | 说明 |
|:------------|:-------------|:-----|
| 1-2个 | 最多并行2个 | 直接并行即可 |
| 3个及以上 | **串行执行** | 逐个启动 agent，完成后处理下一个 |

**串行执行流程**（需保存 ≥ 3个会话时）：
```
1. 启动第1个 agent（run_in_background: true）
2. TaskOutput 等待完成 → 确认结果 → 继续下一步
3. 启动第2个 agent（run_in_background: true）
4. TaskOutput 等待完成 → 确认结果 → 继续下一步
5. ... 依此类推
```

**agent prompt 精简要求**：
- agent prompt 中**不要**传入完整的 jsonl 提取内容
- 只传入：已有 md 路径、jsonl 路径、需要追加的行号范围
- agent 只返回“成功/失败 + 简要摘要（1-2句话）”

**禁止行为**：
- 一次性并行启动 ≥ 3个 agent
- 在 agent prompt 中传入大量文本（提取内容、完整对话等）
- 多个 TaskOutput 结果同时存在于主会话上下文中

### 步骤6：输出验证报告

```
=== 验证报告 ===
1. 上次会话记录：存在 / 无
2. 本次变更文件：新增/修改列表
3. 会话记录确认：位置、序号、jsonl行数、保存模式
4. md↔jsonl映射：session-id、路径、文件存在性
5. AI体系文档索引：已更新 / 无变更
6. 结构完整性检查：
   [ ] 4个强制子节完整？
   [ ] AI回复包含完整内容？
   [ ] 思考链无通用占位符？
   [ ] 工具调用示例每轮都有？
   [ ] 变更文件清单有绝对路径？
```

| 检查项不通过 | 处理 |
|:------------|:-----|
| jsonl来源缺失 | **禁止保存** |
| 4个强制子节缺失 | **必须补全** |
| AI回复为纯摘要 | **必须补充** |
| 思考链用通用占位符 | **必须替换** |

---

## 3. 重要要求

**[CRITICAL]** 完整性检查清单（全部通过才可保存）：
```
[ ] md头部记录了 jsonl来源（session-id）？
[ ] md头部记录了 jsonl完整路径？
[ ] md头部记录了 jsonl行数？
[ ] 每轮对话包含4个强制子节？
[ ] AI回复包含完整内容（结论、表格、代码块）？
[ ] AI思考链为实际执行过程，无通用占位符？
[ ] 工具调用示例每轮都有？
[ ] 包含变更文件清单（绝对路径）？
```

**禁止行为**：
- 创建没有 jsonl 来源的 md 文件
- 不读取 jsonl 直接凭记忆写摘要
- 只写摘要不包含完整 AI 回复
- 使用通用占位符填充思考链

---

## 4. 版本历史

| 版本 | 日期 | 变更说明 |
|:-----|:-----|:---------|
| V4.2 | 2026-04-20 | 新增步骤5.6上下文窗口保护规则：限制并行agent数量≤2，≥3个时串行执行，agent prompt精简要求 |
| V4.1 | 2026-04-20 | 步骤0去重机制优化：基于 jsonl 行号比较判断记录完整性，有新增则查漏补缺 |
| V4.0 | 2026-04-20 | 从 session-management 拆分独立；新增步骤0.5时间范围筛选；移除审计功能 |
| V3.7 | 2026-04-19 | A05规则增加预留目录豁免 |
| V3.6 | 2026-04-19 | 新增步骤0已保存会话去重 |
| V3.4 | 2026-04-18 | 轮次合并规则、系统消息过滤、格式检查修复 |
| V3.3 | 2026-04-13 | 统一完整模式；变更检测从 jsonl 提取 |
| V3.1 | 2026-04-11 | 新增每日会话序号前缀 |
| V3.0 | 2026-04-07 | 新增完整会话文件整理规范 |

详细历史见 `reference.md`。
