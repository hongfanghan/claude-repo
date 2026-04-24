---
name: web-translate-pdf
description: "将目标网站页面抓取并输出高清离线 PDF。支持两种模式：①直接抓取目标语言页面（如 zh-CN）②抓取后翻译为中文。下载高清图片嵌入 PDF、保持原网站目录结构和样式、层级书签导航。当用户要求网站转PDF、网页转PDF、网站内容中文化、翻译网站时触发本技能。"
user-invocable: true
license: Proprietary. LICENSE.txt has complete terms
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python *)
  - Bash(pip install *)
  - Bash(playwright install *)
  - Bash(mkdir *)
  - Bash(ls *)
  - Bash(dir *)
  - Bash(rm *)
  - Bash(cp *)
  - WebSearch
  - mcp__web_reader__webReader
  - Task
---

# 网站抓取 PDF 技能

## 1. 概述

将目标网站的全部页面抓取并生成高清离线 PDF，**下载高清图片嵌入 PDF 实现完全离线**，保持原网站目录结构和文本样式，并生成**层级书签**支持导航。

### 1.1. 两种运行模式

| 项目 | 直接抓取模式 | 翻译模式 |
|------|------------|---------|
| 适用场景 | 目标网站已有目标语言版本（如 `/docs/zh-CN/`） | 目标网站仅有外文版本，需要翻译为中文 |
| 数据源 | 直接抓取目标语言页面（如 zh-CN） | 抓取源语言页面（如 en）→ 翻译为目标语言 |
| 翻译阶段 | **不需要** | 需要（Claude 逐页翻译） |
| 工作流 | 抓取→PDF生成→合并 | 抓取→链接提取→翻译→PDF生成→合并 |
| 链接处理 | webReader 保留链接文本 | 需要从原始 HTML 恢复链接（webReader 会丢失链接） |
| 典型页面量 | zh-CN 约 70 页（如 code.claude.com） | en 约 100+ 页 |
| 质量依赖 | 仅 PDF 渲染质量 | 翻译质量 + PDF 渲染质量 |

**模式选择原则**：
- 如果目标网站存在目标语言版本（如 `/docs/zh-CN/`、`/ja/`），优先使用**直接抓取模式**，避免翻译质量损失
- 如果目标网站只有外文版本，使用**翻译模式**

## 2. 核心要求（CRITICAL）

### 2.1. 图片必须下载嵌入（离线化）

**禁止保留远程图片 URL**。所有图片必须：

1. 下载到本地 `images/` 目录（原始高清分辨率）
2. 转为 base64 编码嵌入 HTML
3. 最终内嵌到 PDF 中，确保完全离线可阅读

```
错误：![截图](https://mintcdn.com/xxx/image.jpg?fit=max...)
正确：![截图](data:image/jpeg;base64,/9j/4AAQ...)
```

### 2.2. SVG 图片特殊处理

**SVG 图片在 Playwright PDF 中会渲染为 14x16 像素的微小图标**。必须：

1. 检测 SVG 格式图片（Content-Type 或 URL 扩展名）
2. 使用 Playwright 截图将 SVG 转为 PNG
3. 嵌入 PNG base64 而非 SVG base64

实现位于 `scripts/md_to_pdf.py` 的 `_svg_to_png_base64()` 函数。

### 2.3. 文本样式保持

PDF 应尽量保持原网站的视觉风格：

- 标题颜色层级（H1 金色、H2 蓝色、H3 深灰）
- 代码块深色背景 + 浅色文字
- 表格样式（表头蓝色、斑马纹、自动换行不溢出）
- 引用块左侧橙色边线 + 浅黄背景
- 行内代码红色高亮
- Callout/Admonition 样式（蓝色信息、橙色警告、绿色提示）
- 标签/徽章样式

### 2.4. 表格管道符处理

**行内代码中的 `|` 会破坏 mistune 表格解析**。在源 MD 中，表格行内代码内的 `|` 必须替换为 `&#124;` HTML 实体。

```
错误：`Edit|Write`    ← mistune 将 | 视为列分隔符
正确：`Edit&#124;Write`  ← HTML 实体不被拆解
```

## 3. 技术栈

| 功能模块 | 工具/库 | 关键约束 |
|---------|---------|---------|
| 网站爬取（内容） | `mcp__web_reader__webReader` MCP 工具 | 获取 Markdown 格式内容 |
| 链接提取（翻译模式 CRITICAL） | `requests` + `BeautifulSoup`（`scripts/extract_links.py`） | webReader 不保留链接，必须从原始 HTML 解析 `<a>` 标签 |
| 内容翻译（翻译模式） | Claude 直接翻译 Markdown 文本 | 翻译时必须保留链接格式 |
| 图片下载嵌入 | `requests` + base64 编码（`scripts/md_to_pdf.py`） | SVG 自动转 PNG |
| SVG→PNG 转换 | Playwright 截图（`scripts/md_to_pdf.py`） | 必须处理，否则 SVG 渲染为 14x16px |
| Markdown→HTML | `mistune` 3.x | **必须启用 `plugins=['table']`** |
| HTML→PDF | Playwright `page.pdf()`（`scripts/md_to_pdf.py`） | `print_background=True` |
| PDF 合并 + 书签 | `pypdf`（`scripts/merge_pdfs.py`） | 层级书签 + 目录页 |
| 样式排版 | 内置 CSS 模板（`md_to_pdf.py` 中 PDF_CSS） | 中文字体优先 |

## 4. 核心工作流

### 4.0. 阶段零：工具链验证（CRITICAL，必须最先执行）

> **血的教训**：曾在未验证工具链的情况下直接批量处理 101 页，导致表格渲染失败、SVG 图片不可见，需多次返工。

**在开始任何批量处理之前，必须先对 1 个页面完成端到端验证：**

#### 4.0.1. 验证清单

| 序号 | 验证项 | 验证方法 | 通过标准 | 适用模式 |
|------|--------|---------|---------|---------|
| V1 | webReader 能获取页面内容 | 抓取 1 页，检查 content 字段 | 非空，包含正文 | 通用 |
| V2 | 图片下载到本地 | 检查 images/ 目录 | 有文件生成 | 通用 |
| V3 | 图片 base64 嵌入 PDF | 检查 PDF 文本中是否有远程图片 URL | 不含 `http` 开头的图片 URL | 通用 |
| V4 | SVG 图片正确渲染 | 检查含 SVG 的 PDF 页面 | SVG 渲染为正常大小（非 14x16px） | 通用 |
| V5 | mistune table 插件 | 检查 HTML 是否含 `<table>` 元素 | 表格正确渲染 | 通用 |
| V6 | PDF 样式与原网页一致 | 打开 PDF 对比原网页目视检查 | 标题颜色、代码块、表格、Callout 正常 | 通用 |
| V7 | 中文字体渲染正常 | Windows 上打开 PDF | 中文不乱码、不缺字 | 通用 |
| V8 | 表格管道符处理 | 检查含 `\|` 的行内代码 | `&#124;` 替换后表格正常 | 通用 |
| V9 | webReader 不保留 HTML 链接 | 检查 content 中是否有 `[text](url)` | **预期：不保留** | 翻译模式 |
| V10 | HTML 链接提取脚本可用 | extract_links.py 提取同页面链接 | 返回非空链接列表 | 翻译模式 |
| V11 | 翻译 MD 保留页间链接 | 搜索 MD 中的 `[中文](/docs/...)` 格式 | 每个原始链接都有对应 | 翻译模式 |
| V12 | 页内锚点链接保留 | 搜索 MD 中的 `#anchor` 格式 | 原始页内跳转链接都保留 | 翻译模式 |

#### 4.0.2. 验证流程

```
1. 选 1 个含表格+图片的典型页面（如 hooks）
2. webReader 抓取目标语言内容 → 保存原始 MD
3. md_to_pdf.py 生成 PDF
4. 逐项验证 V1-V8（翻译模式额外验证 V9-V12）
5. 人工打开 PDF 验证样式和可读性
6. 只有全部通过后才允许进入批量流程
```

### 4.1. 并行 Agent 架构

#### 4.1.1. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    控制器 Agent（主线程）                    │
│  职责：阶段调度、任务分配、进度跟踪、异常处理                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  阶段一：网站分析（单 agent）                               │
│    → sitemap 解析、manifest.json 生成                     │
│                                                         │
│  ── 直接抓取模式 ────────────────────────────────────     │
│  阶段二A：内容抓取+PDF 生成（多 agent 并行）                 │
│    ├── Agent 1：页面 1-5  （webReader + md_to_pdf）        │
│    ├── Agent 2：页面 6-10                                │
│    └── ...                                              │
│    每个 Agent 内部：webReader → 保存MD → md_to_pdf.py     │
│                                                         │
│  ── 翻译模式 ────────────────────────────────────────     │
│  阶段二B-1：链接提取（多 agent 并行）                       │
│    ├── 提取 Agent 1：页面 1-20 链接提取                    │
│    └── 提取 Agent N：页面 ...                             │
│    → 汇总 links_database.json                           │
│  阶段二B-2：翻译+PDF 生成（多 agent 并行）                  │
│    ├── 翻译 Agent 1：页面 1-5（webReader+翻译+PDF）        │
│    └── ...                                              │
│                                                         │
│  阶段三：质量校验（多 agent 并行）                           │
│  阶段四：合并（单 agent）                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 4.1.2. 并行策略

| 阶段 | 模式 | 可并行 | Agent 数量 | 每批页面数 | 依赖 |
|------|------|--------|-----------|-----------|------|
| 网站分析 | 通用 | 否 | 1 | 全部 | 无 |
| 抓取+PDF | 直接抓取 | **是** | 3-5 | 5 | manifest.json |
| 链接提取 | 翻译 | **是** | 3-5 | 20-25 | manifest.json |
| 翻译+PDF | 翻译 | **是** | 3-5 | 5 | links_database.json |
| 质量校验 | 通用 | **是** | 2-3 | 25-30 | PDF 生成完成 |
| 合并 | 通用 | 否 | 1 | 全部 | 所有校验通过 |

#### 4.1.3. 控制器调度伪代码

```
# 阶段零：验证
通用验证: V1-V8
翻译模式额外验证: V9-V12
if not all(对应模式验证项 通过):
    修复并重验证 → 中止

# 阶段一：网站分析（串行）
sitemap → manifest.json

# 阶段二：按模式分流
if 直接抓取模式:
    # 二A：抓取+PDF（并行）
    batches = split(pages, batch_size=5)
    parallel_launch(fetch_agent, batches)
    wait_all_complete()

elif 翻译模式:
    # 二B-1：链接提取（并行）
    batches = split(pages, batch_size=20)
    parallel_launch(extract_agent, batches)
    wait_all_complete()
    merge_links_database()

    # 二B-2：翻译+PDF（并行）
    batches = split(pages, batch_size=5)
    parallel_launch(translate_agent, batches)
    wait_all_complete()

# 阶段三：校验（并行）
parallel_launch(validate_agent, pdf_batches)
wait_all_complete()

# 阶段四：合并（串行）
merge_pdfs()
```

#### 4.1.4. 抓取 Agent 工作模板（直接抓取模式）

每个抓取 Agent 接收一组页面，独立完成端到端处理：

```
输入参数：
  - pages: ["zh-CN/overview", "zh-CN/quickstart", ...]  # 本批页面列表
  - base_url                                              # 站点基础 URL
  - output_dir                                            # 输出目录

每个页面的处理流程：
  1. webReader 抓取目标语言页面内容 → 保存 pages/{page}.md
  2. 处理表格中的管道符（| → &#124;）
  3. 运行 md_to_pdf.py 生成 PDF → 保存 pages/{page}.pdf
  4. 更新 manifest.json 该页面的 status

输出：
  - 抓取后的 MD 文件（已是目标语言）
  - 生成的 PDF 文件
  - 更新的 manifest.json status
```

#### 4.1.5. 翻译 Agent 工作模板（翻译模式）

每个翻译 Agent 接收一组页面，独立完成端到端处理：

```
输入参数：
  - pages: ["en/hooks", "en/hooks-guide", ...]  # 本批页面列表
  - links_database.json 路径                       # 全站链接数据
  - base_url                                      # 站点基础 URL
  - output_dir                                    # 输出目录

每个页面的处理流程：
  1. webReader 抓取源语言页面内容 → 保存 raw/{page}.md
  2. 从 links_database.json 加载该页面的 internal_links
  3. 翻译为目标语言（参考链接数据，同时注入链接）→ 保存 pages/{page}.md
  4. 运行 md_to_pdf.py 生成 PDF → 保存 pages/{page}.pdf
  5. 更新 manifest.json 该页面的 status

输出：
  - 翻译后的 MD 文件
  - 生成的 PDF 文件
  - 更新的 manifest.json status
```

##### 翻译规则（按优先级排列）

1. 技术术语保留英文（API、SDK、MCP、Playwright、React、Claude Code）
2. 代码块和行内代码不翻译
3. 保留原始 Markdown 格式（标题层级、列表、表格、代码块）
4. **图片链接不翻译，不修改**（由脚本自动处理下载嵌入）
5. **页间内部链接必须保留为 Markdown 格式**：翻译链接文本，保留 URL 路径
6. **页内锚点链接必须保留**：`[text](#anchor)` 格式保持不变
7. **页面开头目录必须保留**：翻译目录文字，保留锚点链接格式

##### 三种链接翻译规则

```
【页间链接】原文：[guide](/docs/en/hooks-guide)
           翻译：[指南](/docs/en/hooks-guide)     ← 文本翻译，路径不变

【页内锚点】原文：[Hook lifecycle](#hook-lifecycle)
           翻译：[Hook 生命周期](#hook-lifecycle)  ← 文本翻译，锚点不变

【页面目录】原文：[Configuration](#configuration)
           翻译：[配置](#configuration)            ← 文本翻译，锚点不变
```

#### 4.1.6. 关键约束

- **抓取 Agent 之间无依赖**：每个页面独立处理
- **manifest.json 写冲突**：多个 Agent 同时更新会冲突 → 每个 Agent 返回状态给控制器统一更新
- **images/ 目录写冲突**：不同 Agent 可能下载相同图片 → 使用文件哈希命名，天然去重
- **最大并行数建议 3-5**：过多会触发 API 速率限制

### 4.2. 阶段一：网站分析与页面发现

1. 获取目标网站 sitemap.xml
2. 解析提取指定语言前缀的所有页面 URL（如 `/docs/zh-CN/` 或 `/docs/en/`）
3. 构建 URL 列表，按目录结构排序
4. 初始化 `manifest.json`（URL → 页面映射表）

**页面示例**（以 code.claude.com 为例）：

```
# 直接抓取模式
https://code.claude.com/docs/zh-CN/overview
https://code.claude.com/docs/zh-CN/hooks
... 约 70 页

# 翻译模式
https://code.claude.com/docs/en/overview
https://code.claude.com/docs/en/agent-sdk/overview
... 约 100+ 页
```

**注意**：不同语言版本的页面数量可能不同（如 zh-CN 无 agent-sdk/* 子页面）。

### 4.3. 阶段二：按模式分流

#### 4.3.1. 直接抓取模式：内容抓取 + PDF 生成（并行）

**并行启动多个抓取 Agent，每个处理 5 页：**

```
Agent 1: webReader抓取页面内容 → 保存MD → md_to_pdf.py
Agent 2: webReader抓取页面内容 → 保存MD → md_to_pdf.py
Agent 3: ...
```

#### 4.3.2. webReader 参数（两种模式通用）

```
return_format="markdown", retain_images=true, with_images_summary=true
```

#### 4.3.3. 直接抓取模式：内容后处理

抓取的 MD 内容可能需要以下后处理：

1. **表格管道符修复**：行内代码中的 `|` → `&#124;`
2. **图片 URL 检查**：确保图片 URL 格式正确
3. **标题层级检查**：确保与原网页一致

#### 4.3.4. 翻译模式：链接提取（并行）

> **关键设计**：webReader 将 HTML 转为纯文本时会丢弃所有 `<a>` 标签，翻译模式必须先从原始 HTML 提取链接。

```bash
# 并行启动多个 Agent，每个处理 20 页
python scripts/extract_links.py --manifest manifest.json --site-domain "code.claude.com"
```

每页保存的链接信息：

```json
{
  "url": "https://code.claude.com/docs/en/hooks",
  "url_path": "en/hooks",
  "internal_links": [
    {"text": "guide", "href": "/docs/en/hooks-guide", "context": "start with the guide instead"},
    {"text": "settings", "href": "/docs/en/settings", "context": "see settings"}
  ]
}
```

#### 4.3.5. 翻译模式：翻译 + PDF 生成（并行，核心瓶颈）

**并行启动多个翻译 Agent，每个处理 5 页：**

```
Agent 1: webReader抓取 → 参考links → 翻译(含链接注入) → md_to_pdf.py
Agent 2: webReader抓取 → 参考links → 翻译(含链接注入) → md_to_pdf.py
Agent 3: ...
```

翻译时的操作步骤（链接数据驱动）：

1. 加载该页面的 `internal_links` 数据（从 links_database.json）
2. 加载原始 HTML 中的页内锚点数据（`#anchor` 链接）
3. 翻译正文时，**同时参考链接数据**：
   - 遇到链接文本对应的上下文 → 注入 `[中文](url_path)` 格式
   - 遇到 `#anchor` 格式 → 保留原样
   - 遇到页面目录 → 保留为 `[中文](#anchor)` 格式
4. 翻译完成后，对照 `internal_links` 逐条检查：每个原始链接在翻译 MD 中都有对应

### 4.4. 阶段三：质量校验（并行）

校验在 PDF 生成完成后并行执行，检查每个 PDF 的质量。

### 4.5. 阶段四：合并与层级书签

#### 4.5.1. 合并 PDF（`scripts/merge_pdfs.py`）

```bash
python scripts/merge_pdfs.py --manifest manifest.json --output full.pdf
```

合并时自动：
1. 生成目录页（含页码，可点击跳转）
2. 添加层级书签（按网站目录结构嵌套）

## 5. 输出结构

### 5.1. 目录结构映射规则

```
URL 路径映射：
https://code.claude.com/docs/zh-CN/overview  → pages/zh-CN/overview.pdf
https://code.claude.com/docs/zh-CN/hooks     → pages/zh-CN/hooks.pdf
```

### 5.2. 完整输出目录

```
output/
├── web-translate-{domain}/
│   ├── images/                              # 下载的原始高清图片（备份）
│   │   ├── a1b2c3d4e5f6.jpg
│   │   └── ...
│   ├── raw/                                 # 翻译模式：原始抓取 MD
│   │   └── en-hooks.md
│   ├── links/                               # 翻译模式：每页的链接数据
│   │   └── en-hooks.json
│   ├── pages/                               # 保持网站目录结构
│   │   └── {lang}/                          # 语言目录（zh-CN、en 等）
│   │       ├── overview.pdf
│   │       ├── overview.md
│   │       └── ...
│   ├── {domain}-full.pdf                    # 合并后的完整离线 PDF
│   ├── manifest.json                        # 页面清单 + 处理状态
│   ├── links_database.json                  # 翻译模式：全站链接数据库
│   └── sitemap_parsed.json                  # 解析后的 URL 列表
```

### 5.3. 合并 PDF 导航结构

- **目录页**：首页展示全部页面标题和页码，按网站结构分组
- **层级书签**：侧边栏嵌套书签，可折叠展开

## 6. 辅助脚本

| 脚本 | 功能 | 优先级 |
|------|------|--------|
| `scripts/md_to_pdf.py` | MD → 离线 PDF（图片下载嵌入 + SVG→PNG + 样式保持） | 核心 |
| `scripts/merge_pdfs.py` | PDF 合并（目录页 + 层级书签） | 核心 |
| `scripts/extract_links.py` | 从原始 HTML 提取页面内所有链接 | 辅助（需要链接数据时使用） |
| `scripts/download_images.py` | 独立图片下载工具 | 辅助 |

## 7. 操作步骤

### 7.1. 环境准备

```bash
pip install mistune playwright pypdf requests beautifulsoup4 lxml
playwright install chromium
```

### 7.2. 完整执行流程

```
阶段零：工具链验证（4.0 节）—— 对 1 页做端到端测试
    ↓ 全部通过
阶段一：网站分析（串行）
    → 解析 sitemap → manifest.json
    ↓
阶段二：按模式分流
    ├─ 直接抓取模式：抓取+PDF（并行 3-5 个 Agent，每 Agent 5 页）
    │   Agent 内：webReader → 保存MD → md_to_pdf.py
    │
    └─ 翻译模式：
        ├─ 二B-1：链接提取（并行 3-5 个 Agent，每 Agent 20 页）
        │   → 汇总 links_database.json
        └─ 二B-2：翻译+PDF（并行 3-5 个 Agent，每 Agent 5 页）
            Agent 内：webReader → 参考links → 翻译 → md_to_pdf.py
    ↓
阶段三：质量校验（并行 2-3 个 Agent）
    → PDF 格式、图片嵌入、表格渲染
    ↓ 全部通过
阶段四：合并（串行）
    → merge_pdfs.py → 目录页 + 层级书签
```

### 7.3. 并行启动方式

使用 Claude Code 的 Task 工具并行启动多个 Agent：

```
# 阶段二：并行启动抓取
Task(description="抓取第1组", prompt="...5个zh-CN URL...", run_in_background=true)
Task(description="抓取第2组", prompt="...5个zh-CN URL...", run_in_background=true)
Task(description="抓取第3组", prompt="...5个zh-CN URL...", run_in_background=true)
→ 等待所有完成 → 汇总状态
```

### 7.4. 注意事项

- 图片下载失败时在 PDF 中显示占位文字
- 每次处理 5-10 页为宜
- `print_background=True` 保留代码块背景色
- `mistune.create_markdown(plugins=['table'])` 必须启用 table 插件
- 超长表格（>50 行）可能导致 mistune 解析失败：需要特殊处理

### 7.5. PDF 格式质量校验（CRITICAL）

**合并前必须对每个 PDF 执行以下校验，不合格的必须重新生成：**

#### 7.5.1. 自动校验项

| 校验项 | 检查方法 | 合格标准 |
|--------|---------|---------|
| 页数 ≥ 1 | `pypdf.PdfReader(pdf).pages` | 每个文件至少 1 页 |
| 页面尺寸 | 检查页面宽高是否为 A4（595×842 pt） | 允许 ±5pt 误差 |
| 文件大小 | `os.path.getsize(pdf)` | 不为 0，且不超过 50MB |
| 图片离线化 | 读取 PDF 文本内容搜索 `http` 开头的图片 URL | 不应包含远程图片 URL |
| 表格渲染 | 检查含 `\| --- \|` 的 MD 对应 PDF 是否有 `<table>` | 必须渲染为表格 |
| SVG 图片 | 检查 PDF 中图片尺寸 | 宽高均 > 10px |

#### 7.5.2. 校验脚本

```python
from pypdf import PdfReader
import os

def validate_pdf(pdf_path):
    """校验单个 PDF 文件质量"""
    issues = []

    reader = PdfReader(pdf_path)
    if len(reader.pages) < 1:
        issues.append("空 PDF（0 页）")

    page = reader.pages[0]
    w = float(page.mediabox.width)
    h = float(page.mediabox.height)
    if abs(w - 595) > 5 or abs(h - 842) > 5:
        issues.append(f"非 A4 尺寸: {w:.0f}×{h:.0f}")

    size = os.path.getsize(pdf_path)
    if size == 0:
        issues.append("文件大小为 0")
    elif size > 50 * 1024 * 1024:
        issues.append(f"文件过大: {size / 1024 / 1024:.1f}MB")

    return issues
```

## 8. 已知陷阱与失败案例

> **本节记录实际执行中遇到的坑，避免重复踩坑。**

### 8.1. SVG 图片在 Playwright PDF 中渲染为微小图标

| 项目 | 说明 |
|------|------|
| **现象** | `data:image/svg+xml;base64,...` 在 Playwright `page.pdf()` 中渲染为 14×16 像素的微小图标 |
| **影响** | 所有 SVG 图片在 PDF 中不可见 |
| **原因** | Playwright 的 PDF 渲染引擎对 base64 SVG data URL 处理存在缩放问题 |
| **修复** | 使用 `_svg_to_png_base64()` 将 SVG 通过 Playwright 截图转为 PNG，再嵌入 PNG base64 |
| **脚本位置** | `scripts/md_to_pdf.py` 中的 `_svg_to_png_base64()` 函数 |

### 8.2. mistune 默认不启用 table 插件

| 项目 | 说明 |
|------|------|
| **现象** | 表格渲染为纯文本段落 |
| **影响** | 所有含表格的页面格式错误 |
| **正确写法** | `mistune.create_markdown(plugins=['table'])` |
| **错误写法** | `mistune.create_markdown()` |

### 8.3. 行内代码中的管道符破坏 mistune 表格解析

| 项目 | 说明 |
|------|------|
| **现象** | MD 表格行内代码中的 `\|`（如 `\`Edit\|Write\``）被 mistune 误认为表格列分隔符 |
| **影响** | 表格解析失败，渲染为纯文本 `<p>` 段落 |
| **原因** | mistune table 插件不理解行内代码边界，将 `\`` 内的 `\|` 也作为列分隔符 |
| **修复** | 将行内代码中的 `\|` 替换为 `&#124;`（HTML 实体） |
| **修复后效果** | 表格渲染率达到 99.7% |

### 8.4. CSS 表格溢出问题

| 项目 | 说明 |
|------|------|
| **现象** | 表格内容过长时溢出 A4 纸面边界，导致内容被截断 |
| **修复** | 在 PDF_CSS 中添加 `table-layout: fixed; word-wrap: break-word; overflow-wrap: break-word;` |

### 8.5. 超长表格解析失败

| 项目 | 说明 |
|------|------|
| **现象** | 77 行的命令参考表格无法渲染为 `<table>` |
| **原因** | mistune table 插件对超长表格解析能力有限 |
| **兜底方案** | 将超长表格手动转为 HTML `<table>` 标签直接嵌入 MD |

### 8.6. 批量处理前未验证导致返工

| 项目 | 说明 |
|------|------|
| **现象** | 直接处理全部页面 → 生成 PDF → 发现问题 → 全部重来 |
| **教训** | **必须先完成阶段零（工具链验证），对 1 页做端到端测试** |

### 8.7. Windows Git Bash 路径自动转换

| 项目 | 说明 |
|------|------|
| **现象** | 命令行传入 `--base-path "/docs/zh-CN/"` 时，Git Bash 自动将其转换为 Windows 绝对路径 |
| **原因** | MSYS/Git Bash 会将以 `/` 开头的参数自动转换 |
| **修复** | 检测并还原被转换的路径 |
| **规避** | 使用双斜杠 `--base-path "//docs/zh-CN/"` 防止转换 |

### 8.8. webReader 不保留 HTML 链接（链接恢复场景）

| 项目 | 说明 |
|------|------|
| **现象** | webReader 返回纯文本，所有 `<a href>` 链接被剥离 |
| **影响** | 如需恢复原始链接结构，需要额外的 HTML 解析 |
| **正确方案** | 使用 `requests` + `BeautifulSoup` 直接解析原始 HTML |
| **脚本** | `scripts/extract_links.py` |

### 8.9. 翻译阶段遗漏含链接的段落

| 项目 | 说明 |
|------|------|
| **现象** | 翻译后的 MD 中，某些包含内部链接的英文段落被整体省略（如子章节、代码示例说明） |
| **影响** | 链接完整性检查不通过，部分内容丢失 |
| **原因** | 翻译 Agent 处理长页面时可能跳过细节段落 |
| **预防** | 翻译时参考 `internal_links` 数据，确保每个链接的上下文段落都被翻译 |

### 8.10. Mintlify 页面正文选择器不匹配

| 项目 | 说明 |
|------|------|
| **现象** | extract_links.py 使用 `.prose` 选择器匹配到空壳 div，实际内容在 `.mdx-content` 中，导致链接提取结果为 0 |
| **影响** | Mintlify 框架的网站（如 code.claude.com）所有页面链接提取全部失败 |
| **原因** | `.prose` 在选择器列表中排在 `.mdx-content` 前面，且可能匹配到空壳 div |
| **修复** | 将 `.mdx-content` 添加到选择器列表并排在 `.prose` 之前 |

## 9. 中间信息保留规范（CRITICAL）

> **原则：批量处理过程中的每一步中间产物都必须持久化保存，确保任何环节失败后可从断点恢复。**

### 9.1. 必须保留的中间文件

| 阶段 | 中间文件 | 保存位置 | 适用模式 |
|------|---------|---------|---------|
| 网站分析 | `sitemap_parsed.json` | 输出根目录 | 通用 |
| 抓取完成 | `{url_path}.md` | `pages/{lang}/` 目录 | 通用 |
| 翻译模式原始抓取 | `{url_path}.raw.md` | `raw/` 目录 | 翻译 |
| 链接提取 | `{url_path}.links.json` | `links/` 目录 | 翻译 |
| 全站链接 | `links_database.json` | 输出根目录 | 翻译 |
| PDF 生成 | `{url_path}.pdf` | `pages/{lang}/` 目录 | 通用 |
| 图片下载 | `{hash}.{ext}` | `images/` 目录 | 通用 |
| 质量校验 | `validation_report.json` | 输出根目录 | 通用 |
| 工具链验证 | `verification_result.json` | 输出根目录 | 通用 |

### 9.2. 断点恢复机制

每个阶段的处理进度必须记录在 `manifest.json` 的 `status` 字段中：

```json
{
  "mode": "direct",
  "pages": [
    {
      "url_path": "zh-CN/hooks",
      "status": "completed",
      "phases": {
        "scraped": true,
        "pdf_generated": true,
        "validated": true
      }
    }
  ]
}
```

翻译模式的 manifest 示例：

```json
{
  "mode": "translate",
  "pages": [
    {
      "url_path": "en/hooks",
      "status": "in_progress",
      "phases": {
        "scraped": true,
        "links_extracted": true,
        "translated": true,
        "pdf_generated": false,
        "validated": false
      }
    }
  ]
}
```

**恢复逻辑**：
1. 读取 manifest.json，找到第一个 `status != "completed"` 的页面
2. 检查其 `phases`，从第一个 `false` 的阶段继续
3. 已完成的阶段跳过，使用已保存的中间文件

### 9.3. 禁止的操作

| 禁止 | 原因 |
|------|------|
| 不保存中间文件直接生成 PDF | 任何环节失败需要从头重来 |
| 只保存最终 PDF 不保存 MD | 无法修复问题或重新生成 |
| 不记录处理状态 | 无法断点恢复 |
| 一次性处理全部 70+ 页 | 风险集中，失败代价大 |
| 删除或覆盖原始 MD 数据 | 原始数据丢失无法恢复 |

## 10. 依赖安装

```bash
pip install mistune playwright pypdf requests beautifulsoup4 lxml
playwright install chromium
```

## 11. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| V1.0 | 2026-04-17 | 初始版本：英文→中文翻译模式，101 页 |
| V2.0 | 2026-04-17 | 双模式架构：新增直接抓取模式（zh-CN 等已有中文版的网站），翻译模式保留；新增 SVG→PNG、表格管道符修复、CSS 溢出修复等经验 |
