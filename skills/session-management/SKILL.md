---
name: session-management
description: 会话管理调度入口。触发词：session-management、会话保存、保存会话、结束会话
user-invocable: true
---

# 会话管理调度入口

本技能是会话管理的统一入口，负责调度以下两个子技能：

| 子技能 | 职责 | 斜杠命令 |
|:-------|:-----|:---------|
| session-save | 会话保存（去重→变更检测→索引更新→创建记录→验证） | /session-save |
| session-audit | 会话审计（A01-A08静态检查 + S01-S07语义审计） | /session-audit |

---

## 执行流程

### 步骤1：询问操作类型

使用 AskUserQuestion 询问用户要执行的操作：

| 选项 | 说明 |
|:-----|:-----|
| 保存会话 | 执行会话保存流程（调用 /session-save） |
| 审计会话 | 执行会话审计流程（调用 /session-audit） |

### 步骤2：询问时间范围

使用 AskUserQuestion 询问时间范围：

| 选项 | 含义 |
|:-----|:-----|
| a-本次 | 仅当前会话 |
| b-当天 | 今天所有会话 |
| c-3天内 | 近3天所有会话 |
| d-其他 | 用户指定天数 |

### 步骤3：调用对应子技能

根据用户选择，使用 Skill 工具调用对应的子技能，将时间范围作为参数传入：

- 保存 → Skill(session-save, "[时间范围选项]")
- 审计 → Skill(session-audit, "[时间范围选项]")

---

## 说明

- scripts/ 目录下的脚本文件由 session-save 和 session-audit 共同引用
- 历史版本的完整文档已归档到各子技能的 reference.md 中
