---
name: session-management
description: 会话管理技能。用于以下场景：(1) 保存会话记录，(2) 更新文档索引，(3) 管理会话历史。触发词：session-management、会话保存、保存会话、结束会话。CRITICAL级别：会话结束时自动执行。
---

# 会话保存与文档管理技能

**级别**: CRITICAL (强制执行)
**执行时机**: 每次会话结束前

---

## 1. 自动触发条件

### 1.1. 自动触发（无需用户提醒）

- 会话中新建了任何文档
- 会话中更新了任何现有文档
- 会话持续时间超过30分钟
- 用户说"完成了"、"好了"、"就这样"等
- **AI体系文档发生变更**（新增/修改/删除）

### 1.2. AI体系文档范围

以下目录的文件变更会在会话保存时更新索引：

| 目录 | 说明 | 需更新的索引文件 |
|:-----|:-----|:-----------------|
| openspec/**/*.md | 工作文档（需求/设计） | ai-docs-list.md 第2节 |
| .claude/skills/*/SKILL.md | 技能文档 | ai-docs-list.md 第3节, CLAUDE.md 8.3节 |
| .claude/prompts/**/*.md | 提示词文档 | ai-docs-list.md 第4节, CLAUDE.md |
| rules/**/*.md | 规则文档 | ai-docs-list.md 第5节, CLAUDE.md 8.2节 |
| context/**/*.md | 知识文档 | ai-docs-list.md 第6节, CLAUDE.md 8.1节 |
| CLAUDE.md | 主入口文件 | ai-docs-list.md |

### 1.3. 手动触发

- "保存会话"
- "更新文档索引"
- "保存工作成果"
- "更新AI文档索引"

### 1.4. 配合 hooks 提醒

hooks.json 配置了 PostToolUse + matcher: "Write|Edit" 提醒：
- 收到提醒后，**无需立即更新索引**
- 只需在会话结束时执行 `/session-management` 统一更新

---

## 2. 执行流程

### 步骤1：读取上次会话记录（变更检测基准）

**上次会话记录位置**：`~/.claude/sessions/[项目名]/YYYY-MM-DD/`

**检测方法**：

```
1. 读取 ~/.claude/sessions/[项目名]/最新日期/ 目录下的会话记录
2. 从会话记录"三、变更文件清单"章节提取上次变更的文件列表
3. 作为本次变更检测的对比基准
```

### 步骤2：确认本次会话的变更

> **[CRITICAL]** 变更检测必须基于本次会话的 jsonl 文件，**禁止使用 `git diff`**。
> 原因：会话通常不会提交 git，`git diff HEAD` 反映的是所有未提交变更的累积（可能跨越多个会话），
> 无法区分哪些是本次会话的变更。jsonl 中的 Edit/Write 工具调用记录才是本次会话变更的唯一准确来源。

```
[ ] 从当前会话的 jsonl 文件中提取所有 Edit/Write 工具调用的 file_path
[ ] 过滤掉临时文件（temp/、会话记录、系统文件、plan文件等）
[ ] 得到本次会话实际变更的项目文件清单
[ ] 标记是否有AI体系文档变更（openspec/、.claude/skills/、rules/、context/、CLAUDE.md 等）
```

**jsonl 提取方法**：
```bash
# 提取所有被 Edit/Write 的文件路径
grep -o '"file_path":"[^"]*"' ~/.claude/projects/<project-id>/<session-id>.jsonl | sort -u
```

### 步骤3：更新AI体系文档索引（如有变更）

**3.1. 更新 ai-docs-list.md**

当以下目录有文件变更时，更新对应章节：
- openspec/ → 第2节
- .claude/skills/ → 第3节
- .claude/prompts/ → 第4节
- context/ → 第6节
- rules/ → 第5节

**3.2. 更新 CLAUDE.md**

| 变更类型 | 更新内容 |
|:---------|:---------|
| 新增技能 | 8.3节技能索引 |
| 新增规则 | 8.2节规范索引 |
| 新增知识文档 | 8.1节知识库索引 |
| 版本变更 | 10.版本历史 |

### 步骤4：更新子目录README

| 文档 | 更新内容 |
|------|----------|
| contents/README.md | 新增文档、版本号 |
| .claude/skills/README.md | 新增技能文档 |
| rules/README.md | 新增规则文档 |

### 步骤5：创建会话记录

**保存位置**: `~/.claude/sessions/[项目名]/YYYY-MM-DD/[序号]-[主题].md`

**路径说明**：
- Windows系统：`C:/Users/[用户名]/.claude/sessions/[项目名]/YYYY-MM-DD/`
- Linux/Mac系统：`~/.claude/sessions/[项目名]/YYYY-MM-DD/`

> **[CRITICAL] md ↔ jsonl 一一对应** 每个会话记录 md 文件**必须**有且仅有一个对应的 jsonl 文件。
> 禁止创建没有 jsonl 来源的 md 文件。jsonl 文件是会话记录的原始数据源，md 是其格式化产物。
> 即使项目路径变更（如从 xqfunds-new 改为 [项目名]），jsonl 文件的 session-id 不变，
> md 文件头部必须记录该 session-id，确保任何时候都能追溯到原始 jsonl。

**jsonl 文件位置**：
- `~/.claude/projects/<project-id>/<session-id>.jsonl`
- project-id 是项目路径的编码（如 `D--Git-group-project`），可能因项目重命名而不同
- 但 session-id（UUID格式）是永久的，不随项目路径变化

**md 文件头部必须记录的字段**：
```
**jsonl来源**: <session-id>.jsonl
**jsonl路径**: ~/.claude/projects/<project-id>/<session-id>.jsonl
```

**jsonl 查找规则**（当项目路径变更时）：
```
1. 先在当前项目目录 ~/.claude/projects/<当前project-id>/ 查找
2. 如未找到，在 ~/.claude/projects/ 下所有目录中搜索该 session-id
3. 如仍未找到，标记为"jsonl已丢失"，但仍记录 session-id
```

**只保存到用户级目录**：
- 用户级目录按项目区分（[项目名]为项目标识）
- 避免在项目中产生会话记录文件，保持项目整洁

> **[CRITICAL]** 会话记录目录的日期**必须使用 jsonl 文件的创建日期**，而非当前日期。
> 跨天会话（如 04-12 打开、04-13 保存）应保存到 `~/.claude/sessions/[项目名]/2026-04-12/` 目录，
> 而不是 04-13 目录。日期通过 `stat -c "%W"` 获取 jsonl 的 birth time 确定。

**每日会话序号规则**：
- 序号代表当天在该项目路径**打开** Claude 会话的绝对顺序（第几次打开），而非保存顺序
- 序号格式：两位数字，补零（01, 02, 03, ... 99）
- 文件名格式：`[序号]-[主题].md`，如 `01-AAA.md`、`02-BBB.md`

**序号确定方法（基于会话打开时间）**：

> **[CRITICAL]** 序号按"会话打开"的先后排序，不是按"会话保存"的先后排序。
> 即使先保存后开的会话，序号仍由打开时间决定。

> **[CRITICAL - 禁止使用 ls -lt]** 严禁使用 `ls -lt` 排序确定序号！`ls -lt` 按修改时间排序，
> 修改时间会在读取/写入 jsonl 时更新，导致跨天文件被错误计入当天排序。
> 必须使用 `stat -c "%W"`（Linux/Git Bash）或 `stat -f "%B"`（macOS）获取文件创建时间（birth time）。

```
1. 获取当前会话的 jsonl 文件路径：~/.claude/projects/<project-id>/<session-id>.jsonl
2. 用 Bash 获取该 jsonl 文件的创建时间（birth time，代表会话打开时间）
3. 用 Bash 列出当天该项目的所有 jsonl 文件及其创建时间
4. 按创建时间从早到晚排序，当前会话的排名即为序号
5. 已保存的会话记录文件（已有序号前缀）不参与计算，避免重复计数
```

**Windows 命令示例（Git Bash）**：
```bash
# 获取所有当天 jsonl 文件并按创建时间排序（%W = birth time）
stat -c "%W %n" ~/.claude/projects/<project-id>/*.jsonl | sort -n | tail -N
```

**Windows 命令示例（CMD）**：
```cmd
REM 注意：CMD 无法直接获取文件创建时间，建议在 Git Bash 中执行
REM 以下 forfiles 命令使用的是修改时间，仅作参考
forfiles /P "C:/Users/<用户名>/.claude/projects/<project-id>" /M *.jsonl /C "cmd /c echo @fdate @ftime @path" | sort
```

> **[WARNING]** Windows CMD 的 `forfiles` 只支持修改时间（@ftime），无法获取文件创建时间。在 Git Bash 中使用 `stat -c "%W"` 获取真正的创建时间。

**Linux 命令示例**：
```bash
# 获取所有当天 jsonl 文件并按创建时间排序（%W = birth time）
stat -c "%W %n" ~/.claude/projects/<project-id>/*.jsonl | sort -n
```

**macOS 命令示例**：
```bash
# 获取所有当天 jsonl 文件并按创建时间排序（%B = birth time）
stat -f "%B %N" ~/.claude/projects/<project-id>/*.jsonl | sort -n
```

**示例**（两个会话有交叉时间段）：
| 会话 | 打开时间 | 保存时间 | 序号 | 输出文件名 |
|:-----|:---------|:---------|:-----|:-----------|
| AAA | 05:00 | 07:30 | 01 | `01-会话记录-AAA.md` |
| BBB | 06:00 | 08:00 | 02 | `02-会话记录-BBB.md` |

> 即使 BBB 先于 AAA 保存，BBB 的打开时间晚于 AAA，因此序号为 02。

**5.1. 压缩前会话保存（重要）**

当会话即将被压缩时（上下文接近限制），执行以下步骤：

**jsonl文件位置**：
- 用户级：`~/.claude/projects/<project-id>/*.jsonl`
- 项目级：`项目目录/.claude/history/*.jsonl`

**使用 jsonl-extraction 技能提取（推荐）**：

> **[CRITICAL]** 提取 jsonl 内容时，必须使用用户级技能 `jsonl-extraction`（位于 `~/.claude/skills/jsonl-extraction/`）。

```bash
# 提取完整会话（默认仅对话记录，无时间戳）
python ~/.claude/skills/jsonl-extraction/scripts/extract_jsonl.py \
  ~/.claude/projects/<project-id>/<session-id>.jsonl \
  --output ~/.claude/sessions/<项目名>/YYYY-MM-DD/完整会话.md

# 紧凑模式（适合归档）
python ~/.claude/skills/jsonl-extraction/scripts/extract_jsonl.py \
  ~/.claude/projects/<project-id>/<session-id>.jsonl \
  --output ~/.claude/sessions/<项目名>/YYYY-MM-DD/完整会话.md \
  --compact --no-tools

# 查看统计信息（确认行数）
python ~/.claude/skills/jsonl-extraction/scripts/extract_jsonl.py \
  ~/.claude/projects/<project-id>/<session-id>.jsonl --summary
```

**5.1.1. V3.1 格式化（使用 format_sessions.py）**

> 提取后的 markdown 需要转换为 V3.1 模板格式（含 AI思考链、工具调用示例等）。

```bash
# 单文件格式化
python .claude/skills/session-management/scripts/format_sessions.py \
  <提取的md文件> \
  --date YYYY-MM-DD --seq 01 --topic "会话主题" \
  --jsonl-id <session-id>

# 批量格式化（通过配置JSON）
python .claude/skills/session-management/scripts/format_sessions.py \
  --config <配置文件.json> \
  --sessions-dir ~/.claude/sessions/[项目名]
```

**配置 JSON 格式**：
```json
[
  {"prefix": "730dc0cb", "date": "2026-04-09", "seq": "01", "topic": "CLAUDE.md文档更新", "jsonl_id": "730dc0cb-..."},
  {"prefix": "8167fb22", "date": "2026-04-09", "seq": "02", "topic": "项目创建+openspec讨论", "jsonl_id": "8167fb22-..."}
]
```

**批量处理完整流程**：
```bash
# Step 1: 批量提取所有 jsonl（使用默认 conversation 过滤 + 无时间戳）
for id in <session-id-1> <session-id-2> ...; do
  python ~/.claude/skills/jsonl-extraction/scripts/extract_jsonl.py \
    ~/.claude/projects/<project-id>/${id}.jsonl --compact \
    -o <临时目录>/${id%%-*}.md
done

# Step 2: 批量格式化为 V3.1
python .claude/skills/session-management/scripts/format_sessions.py \
  --config <配置文件.json>

# Step 3: 清理旧文件
rm -f <旧会话文件...>
```

**jsonl文件格式**：
- 每行是一个JSON对象
- 用户消息：`{"type":"user","message":{"role":"user","content":"..."}}`
- AI回复：`{"type":"assistant","message":{"role":"assistant","content":"..."}}`

**保存要求**：
- 在会话记录中新增"压缩前完整会话"章节
- 保留所有用户输入和AI回复
- 标注"[含压缩前完整会话]"

**5.2. 主题命名规范**

**文件名格式**：`[每日序号]-[主题].md`

**每日序号确定方法**：

> **[CRITICAL]** 序号由"会话打开时间"决定，不是由"保存时间"决定。

```
1. 获取当前会话的 jsonl 文件路径
2. 用 Bash 获取该 jsonl 文件的创建时间（即会话打开时间）
3. 列出当天该项目的所有 jsonl 文件，按创建时间从早到晚排序
4. 当前会话在排序中的位置即为序号
```

**单主题命名**：
- 格式：`[序号]-[主题].md`，如：`01-CLAUDE.md文档更新.md`

**多主题命名**：
- 使用"+"连接多个主题，按重要性排序
- 主题数量建议不超过5个，超过则使用概要描述
- 格式：`[序号]-[主题A]+[主题B]+[主题C]+[主题D]+[主题E].md`

**示例**（假设当天已有1个会话文件，本次为第2次）：
| 场景 | 命名 |
|:-----|:-----|
| 单主题 | `02-资讯数据变动需求规格说明书更新.md` |
| 双主题 | `02-MD转Word+技能脚本补充.md` |
| 三主题 | `02-todo命令创建+技能遍历+脚本补充.md` |
| 多主题概要 | `02-技能体系完善与文档转换等等.md` |
| 当天第1次 | `01-XXX.md` |
| 当天第3次 | `03-YYY.md` |

**主题提取原则**：
1. 从会话中的主要任务提取关键词
2. 按任务耗时/重要性排序
3. 优先使用用户明确提到的任务名称
4. 避免过于细节的描述，保持简洁

**5.3. 完整会话文件整理规范**

> **[CRITICAL]** 所有会话保存统一使用完整模式，无精简模式。

- AI回复：必须保留完整文本内容（见5.3.6"完整内容"定义）
- 工具调用：必须包含关键工具调用的JSON参数和结果摘要
- 思考链：必须基于实际执行过程还原（见5.3.3）
- 数据来源：必须从 jsonl 提取完整对话内容

**5.3.1. 章节层次化组织**

**[CRITICAL]** 完整会话文件必须按"对话轮次"组织，禁止按"消息条数"碎片化

**组织原则**：

| 项目 | 禁止做法 | 正确做法 |
|:-----|:---------|:---------|
| 组织单位 | 每条消息一个章节（### N. 用户/AI助手） | 每轮对话一个章节（### 第N轮对话） |
| 时间标记 | 带时间标记 `### 第1轮对话 (19:11)` | 无时间标记 `### 第N轮对话` |
| 内容分割 | 用户输入和AI回复分散在多条消息 | 每轮对话集中：用户输入+AI回复+思考链+工具调用 |
| AI回复内容 | 只写一两句摘要 | 保留完整文本（至少包含关键结论、表格、代码块） |

**5.3.1.1. 轮次合并规则**

> **[CRITICAL]** jsonl 中的工具结果链（tool_result 消息）**必须**与前一轮用户消息合并，不得拆分为独立轮次。

**什么是工具结果链**：
- AI 调用工具后，系统会发送 tool_result 给 AI（作为 user 类型消息）
- AI 收到结果后可能继续调用下一个工具，产生新的 tool_result
- 这一系列连续的 tool_result + assistant 消息构成"工具结果链"

**合并规则**：

| jsonl 消息序列 | 轮次处理 | 说明 |
|:---------------|:---------|:-----|
| user(文本) → assistant → user(文本) → assistant | 2轮 | 正常对话，每轮一次用户文本 |
| user(文本) → assistant(tool_call) → user(tool_result) → assistant(tool_call) → user(tool_result) → assistant(文本) | **1轮** | 工具结果链合并到第一个 user(文本) |
| user(文本) → assistant(文本) | 1轮 | AI直接回复，无工具调用 |

**合并后的一轮对话包含**：
- 最初的用户文本输入
- AI 的最终文本回复（不含中间 tool_call）
- 所有工具调用记录（在"工具调用示例"子节中汇总）

**禁止**：将每个 tool_result 都作为独立轮次输出（会导致几百个碎片化轮次）

**5.3.2. 每轮对话的标准结构**

> **[CRITICAL]** 以下4个子节（用户输入/AI回复/AI思考链/工具调用示例）是每轮对话的**强制结构**，
> 缺少任何一个即视为不合规。

```markdown
### 第N轮对话

**用户输入**:
> [用户原始输入内容，完整保留]

**AI回复**:
[AI回复的完整文本内容，不得只写摘要]

**AI文档产出**:
- [产出的文档列表，含绝对路径]

**AI思考链**:
1. **需求分析**：[实际分析内容，禁止使用"根据用户输入确定任务目标"等通用占位符]
2. **方案制定**：[实际方案选择]
3. **工具选择**：[实际使用的工具及原因]
4. **执行验证**：[实际验证过程]

**参考文档**:
- [文档路径] - [具体参考内容]

**工具调用示例**:
- Bash: [命令描述] → [结果摘要]
- Read: [文件描述] → [结果摘要]
- （如有工具调用则必须列出，如无则写"本轮无工具调用"）
```

**5.3.3. AI思考链规范**

**[必须]** 每个AI回复后增加"AI思考链"小节
**[必须]** 展示AI的分析过程、决策依据、参考来源
**[必须]** 使用有序列表展示思考步骤

> **[CRITICAL - 禁止通用占位符]** 思考链内容必须反映本轮对话的**实际执行过程**。
> 以下为**禁止使用的通用模板**：
> - ~~"根据用户输入确定任务目标"~~
> - ~~"选择合适的工具和方法"~~
> - ~~"执行操作并验证结果"~~
>
> 必须替换为本轮的具体内容，例如：
> - "用户要求检查openspec完整性，需要对比 docs/requirements、openspec/specs、src/ 三个目录"
> - "使用 Agent 工具并行探索3个目录，因为它们之间无依赖关系"
> - "通过对比发现6个规范文件滞后于代码实现"

**AI思考链正确示例**：

```markdown
**AI思考链**:
1. **需求分析**：
   - 用户要求：检查openspec内容完整性并更新
   - 隐含需求：需要对比代码实际状态和规范文档，确认哪些规范已实现但未更新

2. **方案制定**：
   - 方案选项：(A) 逐文件人工对比 (B) 用Agent并行探索 (C) 只看git diff
   - 选择依据：选择B，因为3个目录间无依赖，并行效率最高

3. **工具选择**：
   - 选择工具：Agent(subagent_type=Explore) x 3 并行
   - 选择原因：3个agent分别探索openspec/、docs/、src/，互不依赖

4. **执行验证**：
   - 关键检查点：确认每个规范文件的最新版本与代码状态一致
   - 结果确认：发现6个规范滞后，已列出具体差异

**参考文档**:
- `openspec/project.md` - 项目约定和版本信息
- `.claude/skills/session-management/SKILL.md` - 会话保存规范
```

**5.3.4. 工具调用示例规范**

**[必须]** 每个AI回复后增加"工具调用示例"小节
**[必须]** 展示工具类型、关键参数、结果摘要
**[必须]** 如本轮无工具调用，写"本轮无工具调用"，不得留空或省略该小节
**[推荐]** 相同模式的工具调用可合并展示

**工具调用示例模板**：

```markdown
**工具调用示例**:
- **Bash**: `find openspec/ -name "*.md"` → 找到42个文件
- **Read**: `openspec/project.md` → 读取项目配置（230行）
- **Edit**: `openspec/specs/设置弹窗/任务.md` → 标记FR-077~081为已完成
- **Write**: `openspec/specs/日志系统/需求.md` → 新建日志系统需求（FR-300~331）
- **Grep**: `pattern="已完成" path="openspec/"` → 8个匹配文件
- **Glob**: `openspec/specs/**/*.md` → 列出35个规范文件
- **Agent**: 3个并行Explore agent分别探索openspec/docs/src目录

**注**: Read/Edit工具调用模式与第1轮相同，此处省略JSON参数详情
```

> **[CRITICAL]** 工具调用示例小节**不得省略**。即使本轮没有任何工具调用，
> 也必须写"本轮无工具调用"。这是验证报告完整性检查的必检项。

**5.3.5. 重复模式省略规则**

当工具调用模式与前面相同时，可省略JSON参数详情，但必须保留工具名称和结果摘要：

```markdown
**工具调用示例**:
- **Grep**: 搜索 `TB_BOND` → 找到3个匹配文件
- **Read**: 读取匹配文件内容（模式同第2轮，省略JSON详情）
```

**禁止**：整节写"（工具调用模式与第X节相同，此处省略）"后不留任何内容。
**允许**：省略JSON参数块，但必须保留工具名称 + 一行结果摘要。

**5.3.6. "完整AI回复内容"的定义**

> **[CRITICAL]** 这是"完整内容"与"摘要"的判定标准。违反此定义即为不合规。

**必须保留的内容**（不得省略）：

| 内容类型 | 说明 | 示例 |
|:---------|:-----|:-----|
| 结论性文字 | AI给出的最终判断、分析结果、建议 | "发现6个规范滞后于代码实现" |
| 表格 | AI输出的所有表格（完整行列） | 完整性检查报告表、文件清单表 |
| 代码块 | AI输出的代码片段（完整内容） | 配置JSON、SQL语句、脚本代码 |
| 列表/步骤 | AI给出的有序/无序列表 | 任务清单、操作步骤、发现列表 |
| 关键引用 | AI引用的文档路径、规则条款 | `openspec/specs/xxx/需求.md` FR-077 |
| Mermaid图表 | AI输出的流程图/时序图等 | ```mermaid ... ``` |

**可精简的内容**（仍需保留，但可省略冗长原始数据）：

| 内容类型 | 精简方式 |
|:---------|:---------|
| 工具原始输出 | 保留关键信息，省略冗长原始数据 |
| 中间过程描述 | "让我先读取文件..."可精简为一行 |
| 重复说明 | 多次出现的相同解释可保留首次完整版本 |
| 格式化问候语 | "让我来帮你..."等引导语可省略 |

**判定标准**：如果省略后，读者无法从会话记录中还原出AI的核心分析和结论，即为"摘要"而非"完整内容"。

**5.3.7. 系统注入消息过滤规范**

> **[CRITICAL]** 从 jsonl 提取会话内容时，**必须**过滤掉以下系统注入的消息，不得作为用户输入保存。

**必须过滤的消息类型**：

| 消息特征 | 来源 | 处理 |
|:---------|:-----|:-----|
| `This session is being continued from a previous conversation that ran out of context.` | Claude Code 上下文压缩 | **删除**，不是用户输入 |
| `Summary:\n\nAnalysis:` 开头的长文本 | Claude Code 压缩后的对话摘要 | **删除**，不是用户输入 |
| 空的 tool_result 消息（无实际内容） | 工具返回空结果 | **删除** |
| bash 通知消息（如 `RunInBackground` 状态） | 系统工具通知 | **删除** |
| `<system-reminder>` 标签包裹的内容 | 系统提醒 | **删除** |

**过滤方法**（从 jsonl 提取时）：
```python
def is_system_injected(content):
    """判断是否为系统注入消息（非用户真实输入）"""
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

**为什么必须过滤**：
- 上下文续接消息不是用户输入，保存后会话记录中出现大量重复的"第N轮对话"只有系统文本
- 一次长会话可能产生10+次上下文续接，每次都是一大段英文摘要
- 03号会话记录（528轮 → 过滤合并后99轮）就是因为没有过滤系统消息导致的典型反面案例

**5.4. 会话记录模板**：

> **[CRITICAL]** 此模板与5.3.2节的标准结构**完全一致**，是会话记录的最终输出格式。

```markdown
# 会话记录：[主题]

**日期**: YYYY-MM-DD
**会话序号**: 第N次（当天）
**会话轮次**: N轮
**jsonl文件**: [session-id].jsonl（N条记录）
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
1. **需求分析**：[实际分析内容]
2. **方案制定**：[实际方案选择]
3. **工具选择**：[实际使用的工具及原因]
4. **执行验证**：[实际验证过程]

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
| `D:\Git\group\project\路径\文件名.md` | 说明 |

### 3.2. 修改文件
| 文件路径 | 变更内容 |
|:---------|:---------|
| `D:\Git\group\project\路径\文件名.md` | 变更描述 |

### 3.3. 重命名文件（如有）
| 原路径 | 新路径 |
|:-------|:-------|
| `旧路径` | `新路径` |

## 四、涉及的规则/技能/提示词
- `.claude/skills/xxx/SKILL.md` — 技能说明
- `rules/xxx/xxx.md` — 规则说明
```

**5.5. 格式检查与修复**

> 生成会话记录后，**推荐**运行格式检查脚本确认无格式缺陷。

**5.5.1. 常见格式缺陷**（从 jsonl 生成时产生）

| 缺陷类型 | 表现 | 修复方式 |
|:---------|:-----|:---------|
| TODO占位符 | `<!-- TODO: ... -->` 残留在会话记录中 | 手动删除或重新生成 |
| 过长工具调用行 | `- **Bash**: 命令内容...` 超过200字符 | `fix-session-format.py` 自动截断 |
| 裸露代码行 | 多行 Bash 命令（如 `python -c "..."`）中的换行导致代码裸露 | `fix-session-format.py` 自动合并 |
| 代码围栏未闭合 | 奇数个 ` ``` ` | 手动修复 |
| 用户输入缺少引用 | `**用户输入**:` 后面的内容没有 `>` 前缀 | 手动修复 |

**5.5.2. 检查脚本**（`check-session-completeness.py`）

```bash
# 检查完整性（默认）
python ~/.claude/skills/session-management/scripts/check-session-completeness.py --check-all

# 同时检查格式问题
python ~/.claude/skills/session-management/scripts/check-session-completeness.py --check-all --format
```

**5.5.3. 修复脚本**（`fix-session-format.py`）

```bash
# 修复单个文件
python ~/.claude/skills/session-management/scripts/fix-session-format.py <session_md_file>

# 修复所有会话记录
python ~/.claude/skills/session-management/scripts/fix-session-format.py --fix-all
```

### 步骤6：输出验证报告

**[CRITICAL]** 验证报告必须包含以下检查项。保存前必须逐项确认，任一关键项不通过则不得保存。

```
=== 验证报告 ===

1. 上次会话记录：存在 / 无
2. 本次变更文件：
   - 新增：[文件绝对路径列表]
   - 修改：[文件绝对路径列表]
3. 会话记录确认：
   - 位置：[会话记录文件绝对路径]
   - 当天序号：第N次（当天已有N-1个会话文件）
   - jsonl完整性：[行数]行 / [是否含压缩前完整会话]
   - 保存模式：完整模式（必须从 jsonl 提取完整对话内容）
4. md↔jsonl映射检查：
   - jsonl来源（session-id）：已记录 / 缺失
   - jsonl路径（完整路径）：已记录 / 缺失
   - jsonl文件存在性：存在 / 已丢失
5. AI体系文档索引：已更新 / 无变更
6. 结构完整性检查（逐项打勾）：
   [ ] 每轮对话是否包含4个强制子节（用户输入/AI回复/AI思考链/工具调用示例）？
   [ ] AI回复是否包含完整内容（结论、表格、代码块），而非纯摘要？
   [ ] AI思考链是否为实际执行过程，无通用占位符？
   [ ] 工具调用示例是否每轮都有（无工具调用则写"本轮无工具调用"）？
   [ ] 是否包含所有用户输入？
   [ ] 是否包含变更文件清单（绝对路径）？
```

**验证报告判定规则**：

| 检查项 | 不通过处理 |
|:-------|:-----------|
| jsonl来源（session-id）缺失 | **禁止保存**，必须先记录 session-id |
| jsonl文件已丢失 | 警告，记录 session-id 后可保存 |
| 4个强制子节缺失 | **必须补全后再保存** |
| AI回复为纯摘要 | **必须补充完整内容后再保存** |
| 思考链使用通用占位符 | **必须替换为实际内容后再保存** |
| 工具调用示例整节缺失 | **必须补全后再保存** |
| 变更文件清单缺失 | 警告，补充后保存 |

**V2.8要求（验证报告完整性）**：

**[CRITICAL]** 验证报告必须体现jsonl完整性检查
**[CRITICAL]** 即使没有压缩，也要报告jsonl行数
**[CRITICAL]** 标注是否包含压缩前完整会话

---

## 3. 重要要求

### 3.1. V1.7要求（内容完整性）

**[必须]** 保存AI回复的完整内容，不得只写摘要
**[必须]** 保留格式化内容：表格、代码块、列表、引用块、Mermaid图表
**[必须]** 保留关键分析过程和思考路径

### 3.2. V2.4要求（压缩前会话保存）

**[必须]** 在会话压缩前，读取~/.claude/projects/项目名/*.jsonl文件
**[必须]** 解析jsonl文件提取完整对话内容
**[必须]** 将压缩前的完整会话内容保存到会话记录中
**[必须]** 在会话记录中标注"[含压缩前完整会话]"

### 3.3. V2.2要求（用户级单位置保存）

**[必须]** 会话记录只保存到用户级目录
**[必须]** 用户级目录：`~/.claude/sessions/[项目名]/YYYY-MM-DD/`
**[必须]** 按项目区分会话目录，避免项目目录污染

### 3.4. V2.3要求（AI体系文档索引更新）

**[必须]** 检测AI体系文档变更（openspec/skills/prompts/rules/context目录）
**[必须]** 在会话保存时统一更新ai-docs-list.md对应章节
**[必须]** 在会话保存时统一更新CLAUDE.md对应索引章节
**[必须]** 在验证报告中确认索引更新状态

### 3.5. V2.6要求（hooks提醒配合）

**[必须]** hooks.json 提醒后，无需立即更新索引
**[必须]** 在会话结束时执行 /session-management 统一更新
**[必须]** 索引更新放在会话保存流程中执行

### 3.6. V2.7要求（会话记录完整性强制验证）

**[CRITICAL]** 创建会话记录前，**必须**先读取jsonl文件提取完整对话内容

**[CRITICAL]** 会话记录**必须**通过完整性检查才能保存

**[CRITICAL]** 完整性检查清单（7项全部通过才可保存）：
```
[ ] md文件头部是否记录了 jsonl来源（session-id）？
[ ] md文件头部是否记录了 jsonl完整路径？
[ ] 每轮对话是否包含4个强制子节（用户输入/AI回复/AI思考链/工具调用示例）？
[ ] AI回复是否包含完整内容（结论、表格、代码块），而非纯摘要？
[ ] AI思考链是否为实际执行过程，无通用占位符？
[ ] 工具调用示例是否每轮都有（无工具调用则写"本轮无工具调用"）？
[ ] 是否包含变更文件清单（绝对路径）？
```

**执行流程（强制）**：
1. 获取当前会话的 session-id 和 jsonl 路径
2. **必须**先读取 jsonl 提取完整对话内容 → 创建会话记录 → 完整性检查 → 保存
3. **禁止**：创建没有 jsonl 来源的 md 文件
4. **禁止**：不读取jsonl直接凭记忆写摘要
5. **禁止**：只写摘要不包含完整AI回复
6. **禁止**：使用通用占位符填充AI思考链（如"根据用户输入确定任务目标"）

---

## 4. 版本历史

| 版本 | 日期 | 变更说明 |
|:-----|:-----|:---------|
| V3.4 | 2026-04-18 | **[FEATURE]** 新增5.3.1.1轮次合并规则：jsonl中tool_result链必须与前轮用户消息合并，禁止拆分为独立轮次；新增5.3.7系统注入消息过滤规范（上下文续接、空tool_result等必须过滤）；新增5.5格式检查与修复（check-session-completeness.py支持--format参数，新增fix-session-format.py修复脚本） |
| V3.3 | 2026-04-13 | **[CRITICAL]** 移除场景A/B区分，所有会话保存统一使用完整模式（必须从 jsonl 提取完整对话内容）；步骤2 变更检测改为从 jsonl 提取 Edit/Write 路径，禁止使用 git diff；新增跨天会话目录规则（使用 jsonl 创建日期）；format_sessions.py 新增 --auto-date + _get_single_birth_time() |
| V3.1 | 2026-04-11 | **[FEATURE]** 新增每日会话序号前缀：按当天在该项目路径**打开**Claude会话的绝对顺序编号（01, 02, ...），文件名格式改为 `[序号]-[主题].md`；序号通过 jsonl 文件创建时间排序确定，与保存顺序无关；新增 scripts/format_sessions.py 批量格式化工具 |
| V3.1.1 | 2026-04-11 | 修复：脚本统一放在技能目录 scripts/ 下；extract_jsonl.py 默认过滤仅对话记录、默认不显示时间戳；read-jsonl.py 同上 |
| V3.0 | 2026-04-07 | **[CRITICAL]** 新增5.3节完整会话文件整理规范：章节层次化组织（按轮次非条数）、删除时间标记、每轮对话包含AI思考链+参考文档+工具调用示例；新增5.3.3 AI思考链规范 |
| V2.9 | 2026-04-02 | 新增5.2节主题命名规范：单主题直接命名，多主题使用"+"连接（不超过3个），超过则使用概要描述 |
| V2.8 | 2026-04-02 | **[CRITICAL]** 更新步骤6验证报告模板：必须体现jsonl完整性检查；即使无压缩也要报告jsonl行数；新增3.7节V2.8要求 |
| V2.7 | 2026-04-01 | **[CRITICAL]** 新增3.6节V2.7要求：会话记录完整性强制验证；强制要求先读jsonl再创建记录；禁止只写摘要；新增完整性检查清单 |
| V2.6 | 2026-04-01 | 新增1.2节 openspec/ 目录；新增1.4节配合hooks提醒说明；明确索引更新在会话保存时统一执行（非立即）；新增3.5节V2.6要求 |
| V2.5 | 2026-04-01 | 新增scripts/read-jsonl.py脚本；更新步骤5.1引用脚本 |
| V2.4 | 2026-04-01 | 补充变动检测基准（步骤1）；补充压缩前会话保存具体实现（步骤5.1）；更新V2.4要求 |
| V2.3 | 2026-04-01 | 新增AI体系文档变更检测和自动索引更新功能；新增步骤3"更新AI体系文档索引" |
| V2.2 | 2026-04-01 | 改为只保存用户级目录；用户级路径改为按项目区分（[项目名]） |
| V2.1 | 2026-03-27 | 新增双位置保存要求（项目级+用户级） |
| V2.0 | 2026-03-26 | 重构为官方格式目录结构 |
| V1.8 | 2026-03-25 | 新增压缩前会话内容保存要求 |
| V1.7 | 2026-03-14 | 要求保存完整AI回复内容 |
| V1.6 | 2026-03-13 | 新增对话交互完整记录功能 |

---

## 5. 权限配置要求

> 本技能执行过程中涉及的目录和命令，必须在 ~/.claude/settings.json 中预先放行，否则会被权限系统拦截导致执行失败。

### 5.1. 必需权限清单

以下权限应配置在全局 settings.json 的 permissions.allow 数组中：

**Read（读取）**:
| 权限规则 | 用途 |
|:---------|:-----|
| `Read(~/.claude/**)` | 读取用户级技能文件、会话记录 |
| `Read(~/.claude/**/*.jsonl)` | 读取jsonl会话历史文件 |

**Write（写入）**:
| 权限规则 | 用途 |
|:---------|:-----|
| `Write(~/.claude/sessions/**)` | 创建会话记录文件 |

**Edit（编辑）**:
| 权限规则 | 用途 |
|:---------|:-----|
| `Edit(~/.claude/sessions/**)` | 修改会话记录文件 |

**Bash（命令）**:
| 权限规则 | 用途 |
|:---------|:-----|
| `Bash(~/.claude/projects/**)` | 对jsonl文件执行stat/wc/grep等操作 |
| `Bash(~/.claude/sessions/**)` | 操作会话目录（ls、文件管理） |
| `Bash(stat:*)` | 获取jsonl文件创建时间（birth time），用于确定会话序号 |
| `Bash(sort:*)` | 按创建时间排序jsonl文件 |
| `Bash(wc:*)` | 统计jsonl文件行数 |
| `Bash(python:*)` | 运行会话管理脚本（extract_jsonl.py、format_sessions.py等） |

**Glob/Grep（搜索）**:
| 权限规则 | 用途 |
|:---------|:-----|
| `Glob(~/.claude/**)` | 搜索用户级目录下的文件 |
| `Grep(~/.claude/**)` | 搜索用户级目录下的文件内容 |

### 5.2. 权限配置方法

使用 `/update-config` 技能自动添加权限，或手动编辑 ~/.claude/settings.json：

```json
{
  "permissions": {
    "allow": [
      "Read(~/.claude/**)",
      "Read(~/.claude/**/*.jsonl)",
      "Write(~/.claude/sessions/**)",
      "Edit(~/.claude/sessions/**)",
      "Bash(~/.claude/projects/**)",
      "Bash(~/.claude/sessions/**)",
      "Bash(stat:*)",
      "Bash(python:*)",
      "Glob(~/.claude/**)",
      "Grep(~/.claude/**)"
    ]
  }
}
```

### 5.3. 注意事项

- [重要] `Bash(mkdir:*)` 不可靠，创建会话目录时应使用 Write 工具（自动创建父目录），而非 Bash mkdir
- [重要] `Bash(stat:*)` 是确定会话序号的必需权限，缺少时无法按创建时间排序
- [重要] 权限变更后需重启 Claude Code 会话才能生效
- 项目级权限（settings.local.json）中如有重复规则，全局权限优先
