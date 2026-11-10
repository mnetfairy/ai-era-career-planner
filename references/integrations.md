# v2.0 生态集成

> ⚠️ 以下所有集成为**可选项**，仅在用户**明确提出需求**时才激活，且每次操作需获得用户确认。
> 🔒 2026-11-10 安全整改：本 skill **不写入** `MEMORY.md`，也不写入工作区 `memory/`；
> 需要长期沉淀的内容**仅写入 `./exports/tracking/`**（与 frontmatter
> `permissions.filesystem.write` 声明的 `./exports/` 边界一致），并把摘要文本提供给
> 用户自行复制。

## AgentMail 集成
如用户明确要求将报告发送到邮箱，按用户提供的地址发送。

## agent-reach 集成
如用户明确要求订阅职业方向资讯，根据用户选择的方向提供订阅服务（可随时取消）。

## MEMORY.md 集成（🔒 已禁用写入）
- **本 skill 不写入 `MEMORY.md`，也不写入工作区 `memory/` 目录。**
- 如用户明确要求保存规划摘要：
  1. 摘要文本**在回复中直接提供给用户**，由用户自行复制到自己的笔记系统；
  2. 如需留存在 skill 自己的目录内，**仅写入 `./exports/tracking/`**
     （见 `references/tracker_system.md` 的保存路径与保留期限规则）。
- 该约定与 frontmatter `permissions.filesystem.write: [./exports/]` 完全一致；
  任何指向 `./exports/` 之外的记忆写入一律不做。

## 多语言支持
`references/i18n/en.md` - 英文版报告模板（如用户要求，提供英文版本）

## 实时数据接入
Tavily API：仅在用户明确需要实时招聘数据且当前环境可用时接入。

## 重要原则

- **不自动发送**：不自动发送任何报告、资讯或推送
- **不自动订阅**：不自动订阅任何内容
- **不自动记录**：不自动写入任何 memory 或追踪文件
- **写入边界**：持久化写入只发生在 `./exports/`（含 `./exports/tracking/`）之内
- **用户授权**：每次外部操作均需用户明确授权
