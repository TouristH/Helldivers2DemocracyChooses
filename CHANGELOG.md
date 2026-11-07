# 更新记录

## 0.3.0 - 2026-11-08

- 改走插件中心 `Modify Plugin / 修改插件` 流程，申请以新 ID 与新仓库承接旧 PatchFeed 登记；版本序列升至 `0.3.0`，高于旧项目的 `0.2.x`。
- 将旧项目 Git 历史并入以保留所有已收录版本的原提交，合并前后当前文件树完全一致；未恢复推送、订阅或旧数据。
- 保留双方已发布 Tag 和 Release 原内容，旧项目历史 Release 继续留在原仓库。登记迁移、旧 ID 保留与本地安装/配置迁移是不同流程，README 已明确手动迁移步骤。
- 随机配装、单格重抽、离线图卡和全局群白名单功能保持不变。

## 0.1.2 - 2026-11-08

- 将 README 改为超级地球临时军需官口吻，保留“解放你大业的”，加入管理式民主、战备配发、增援与军需手续相关的原创黑色幽默旁白。
- 将安装、命令、群白名单、图卡检修和项目沿革整理为易查阅的手册；保留准确的配置、权限、兼容性、装备数据日期和第三方许可说明。
- 增加插件中心登记申请链接与资讯类插件导向；随机配装、重抽、群白名单和其它运行功能未改动。

## 0.1.1 - 2026-11-08

- 在 GitHub 仓库名与插件 ID 中加入游戏名：`Helldivers2DemocracyChooses`、`github.touristh.helldivers2-democracy-chooses`，同步安装命令、文档链接与维护工具标识。
- 展示名称仍为“绝地潜兵 2：民主帮你选择”；`Democracy Chooses` 表示由民主作出选择。
- 已发布的 `0.1.0` Tag 与安装包保留原内容；已有安装需备份配置、停用旧 ID 后按新 ID 安装。游戏娱乐分类、点头图标和全局群白名单逻辑保持原样。

## 0.1.0 - 2026-11-08

- 从 [TouristH/HelldiversPatchFeed @555c3a5](https://github.com/TouristH/HelldiversPatchFeed/tree/555c3a5) 独立精简配装功能，以“绝地潜兵 2：民主帮你选择”、新仓库和新插件 ID `github.touristh.democracy-chooses` 开始版本记录；分类为游戏娱乐（`game`）。
- 保留八格随机配装、限时单格重抽、按聊天与用户隔离的会话、离线图卡和文字回退。
- 保留 `loadout`、`status`、`help`、`diag` 及现有命令前缀；在允许群内，`diag` 仅宿主操作员和管理员白名单可用，功能命令支持黑名单。
- 将白名单扩展为全局群准入：所有命令先检查 `allowed_groups`，默认空名单、未列出的群及私聊均拒绝，管理员不能绕过；群白名单只能在配置文件内维护。
- 删除更新推送、运行时 Steam/Wiki 查询、后台轮询、群订阅、订阅门禁和公告数据库；配置收敛为 `allowed_groups`、`admin_users`、`command_blacklist`、`loadout_reroll_seconds`。
- 原样保留截至 2026-10-21 的 221 项装备与内嵌图标、维护者刷新工具及原项目和第三方署名。
- 采用用户提供的绿色潜兵头盔点头动画作为本地图标，无损转换为 18 帧 WebP；群白名单字段在 WebUI 表单中隐藏。

本项目不承袭 HelldiversPatchFeed 的版本序列或旧公告数据。源项目的历史变更与贡献见[原仓库](https://github.com/TouristH/HelldiversPatchFeed/tree/555c3a5)；素材的历史来源和许可边界继续记录在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
