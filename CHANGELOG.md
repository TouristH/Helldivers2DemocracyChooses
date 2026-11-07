# 更新记录

## 0.1.0 - 2026-11-08

- 从 [TouristH/HelldiversPatchFeed @555c3a5](https://github.com/TouristH/HelldiversPatchFeed/tree/555c3a5) 独立精简配装功能，以“绝地潜兵 2：民主帮你选择”、新仓库和新插件 ID `github.touristh.democracy-chooses` 开始版本记录；分类为游戏娱乐（`game`）。
- 保留八格随机配装、限时单格重抽、按聊天与用户隔离的会话、离线图卡和文字回退。
- 保留 `loadout`、`status`、`help`、`diag` 及现有命令前缀；在允许群内，`diag` 仅宿主操作员和管理员白名单可用，功能命令支持黑名单。
- 将白名单扩展为全局群准入：所有命令先检查 `allowed_groups`，默认空名单、未列出的群及私聊均拒绝，管理员不能绕过；群白名单只能在配置文件内维护。
- 删除更新推送、运行时 Steam/Wiki 查询、后台轮询、群订阅、订阅门禁和公告数据库；配置收敛为 `allowed_groups`、`admin_users`、`command_blacklist`、`loadout_reroll_seconds`。
- 原样保留截至 2026-10-21 的 221 项装备与内嵌图标、维护者刷新工具及原项目和第三方署名。
- 采用用户提供的绿色潜兵头盔点头动画作为本地图标，无损转换为 18 帧 WebP；群白名单字段在 WebUI 表单中隐藏。

本项目不承袭 HelldiversPatchFeed 的版本序列或旧公告数据。源项目的历史变更与贡献见[原仓库](https://github.com/TouristH/HelldiversPatchFeed/tree/555c3a5)；素材的历史来源和许可边界继续记录在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
