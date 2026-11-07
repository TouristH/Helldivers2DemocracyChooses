# DemocracyChooses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 发布独立身份的“绝地潜兵 2：民主帮你选择”0.1.0，删除运行时资讯推送并保留配装及白名单。

**Architecture:** 从 0.2.2 导出受版本控制文件到独立仓库，精简 plugin.py 与测试；不继承旧 Git 历史。装备数据与离线图片继续复用，外部访问仅保留在维护者刷新脚本中。

**Tech Stack:** Python 3.12、maibot-plugin-sdk >=2.7.1,<3、pytest；可选宿主 Playwright 渲染。

**Spec:** ../specs/2026-11-07-democracy-chooses-design.md

## Global Constraints

- ID github.touristh.democracy-chooses；版本 0.1.0；展示名称 绝地潜兵 2：民主帮你选择。
- allowed_groups 是全局群门禁，默认空列表；所有命令和管理员均受限，私聊拒绝，群内无增删白名单指令。允许群内保留已有管理员与功能黑名单权限优先级。
- 运行时不采集、不推送、不建公告数据库、不需要群订阅。
- 保留数据来源、素材许可边界与旧项目贡献署名。
- 用户已授权创建新 GitHub 仓库；不提交插件市场登记或评论。

## Review Focus

- 无订阅与无数据目录的配置允许群仍可抽装；空名单、其他群、私聊及这些环境内的管理员都不可使用命令。
- 无操作者 ID 的管理命令不可绕过白名单。
- 拒绝旧推送命令且不会触发外部请求。
- 用户间重抽隔离、会话超时与重复战略配备约束保持。
- SDK 命令元数据、真实配置解析与渲染能力声明一致。

### Task 1: 精简运行时与回归测试

Files: plugin.py, tests/test_plugin.py。
Produces: DemocracyChoosesPlugin、create_plugin()、保留的配装函数与四条动作。
- [x] 先保留适用配装与权限测试，新增无订阅加载/抽装、全局 allowed_groups 门禁/名单热更新、拒绝旧资讯动作的失败测试。
- [x] 运行失败测试，确认失败源自旧资讯耦合。
- [x] 删除资讯采集/SQLite/轮询/订阅和关联配置，重命名插件身份与帮助文本。
- [x] 执行完整 pytest，确认配装、重抽、权限、渲染及 SDK 测试通过。

### Task 2: 新身份、依赖与发布文档

Files: _manifest.json, README.md, CHANGELOG.md, CONTRIBUTORS.md, THIRD_PARTY_NOTICES.md, config.example.toml, requirements*.txt, .github/workflows/tests.yml, tools/refresh_loadout_database.py。
Consumes: Task 1 的四动作与四项配置（allowed_groups、admin_users、command_blacklist、loadout_reroll_seconds）。
- [x] 对齐新 ID、版本、仓库链接、名称及 game 分类，只声明 send.text/send.image/render.html2png。
- [x] 仅记录保留功能，明确 admin_users 白名单用途与图卡依赖，移除旧推送部署说明。
- [x] 保留装备库与维护工具的来源、许可和历史贡献；整理刷新工具中过期品牌字样。
- [x] 检查配置/依赖/CI 与实际实现一致。

### Task 3: 验证与创建新仓库

- [ ] 进行独立代码审查并修复重要问题；运行完整测试与编译检查。
- [ ] 打包安装源码 ZIP，确认无旧配置/数据库/本地环境/开发缓存。
- [ ] 创建 TouristH/DemocracyChooses 公开仓库，提交并上传 main；创建匹配 v0.1.0 的首版 Release。
- [ ] 验证远端 SHA、Release 及原仓库未修改；报告测试和本地产物路径。
