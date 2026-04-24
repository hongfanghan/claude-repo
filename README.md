# claude-repo

Claude Code 用户级配置仓库，包含技能（skills）、规则（rules）、插件（plugins）等自定义配置。

## 目录结构

```
~/.claude/
├── CLAUDE.md                  # 全局用户指令
├── skills/                    # 自定义技能
│   ├── session-management/    # 会话管理调度入口
│   ├── session-save/          # 会话保存
│   ├── session-audit/         # 会话审计
│   └── web-translate-pdf/     # 网站转PDF
├── rules/                     # 全局强制规则
├── plugins/                   # MCP插件配置
├── commands/                  # 自定义命令
└── sessions/                  # 会话记录存档
```
