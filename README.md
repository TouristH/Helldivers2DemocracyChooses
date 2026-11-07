# 绝地潜兵 2：民主帮你选择

![红色潜兵头盔动图标](assets/icon.webp)

[![Tests](https://github.com/TouristH/DemocracyChooses/actions/workflows/tests.yml/badge.svg)](https://github.com/TouristH/DemocracyChooses/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

面向 MaiBot Plugin SDK 2.x 的 **HELLDIVERS 2（绝地潜兵2）随机配装**插件，分类为**游戏娱乐**（`game`）。生成八格配装，支持限时单格重抽、自包含离线图卡、文字回退，以及管理员渲染诊断。

本项目从 [TouristH/HelldiversPatchFeed](https://github.com/TouristH/HelldiversPatchFeed/tree/555c3a5) 的配装功能独立精简而来，使用新仓库、新 ID `github.touristh.democracy-chooses`，首版为 `0.1.0`。不沿用原项目版本号、配置或旧公告数据；运行时没有资讯推送、订阅、Steam/Wiki 查询、后台轮询或公告数据库。

这是非官方粉丝作品，与 Arrowhead Game Studios 或 Sony Interactive Entertainment 无关联。代码、Wiki 衍生文本和游戏图像的许可边界见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 安装与兼容

| 项目 | 要求或声明范围 |
|---|---|
| MaiBot Host | manifest 声明 `1.0.0–1.3.99` |
| MaiBot Plugin SDK | 依赖 `>= 2.7.1, < 3.0.0`；manifest 声明 `2.7.1–2.21.99` |
| Python | 开发验证使用 3.12；部署以 MaiBot/SDK 支持的版本为准 |
| 图片渲染 | 宿主环境安装 `playwright>=1.54.0` 和 Chromium，并开放渲染能力 |

以上是兼容声明，不代表已经逐个版本实机测试。当前本地验证使用真实 SDK 与模拟宿主，尚未完成真实 MaiBot 宿主的加载、图片发送和配置热更新端到端验证。兼容区间格式依据 MaiBot 的 [Manifest 文档](https://docs.maibot.chat/plugin/manifest)；后续宿主版本需重新验证后再扩大范围。

在 MaiBot 的 `plugins` 目录执行：

```bash
git clone https://github.com/TouristH/DemocracyChooses.git
```

在**运行 MaiBot 宿主的同一个 Python 环境**安装依赖和渲染浏览器：

```bash
python -m pip install -r plugins/DemocracyChooses/requirements.txt
python -m playwright install chromium
```

重启 MaiBot，Runner 会发现根目录的 `_manifest.json` 和 `plugin.py`，并生成 `config.toml`。编辑该文件，在 `[plugin]` 的 `allowed_groups` 中填入允许使用的群号；默认空名单拒绝全部命令。群白名单只能在配置文件中维护，不提供群聊增删或订阅命令。

只使用文字配装时无需安装浏览器；图片渲染或发送失败会自动回退文字。插件只声明 `send.text`、`send.image`、`render.html2png` 三项能力。

## 命令

`/helldivers`、`/hd`、`/潜兵`、`/绝地潜兵` 四个前缀等价。

| 命令 | 用途 | 默认权限 |
|---|---|---|
| `/hd loadout` | 随机生成一整套配装 | 允许群内成员，可用黑名单限制 |
| `/hd loadout 1-8` | 在有效期内重抽指定格 | 允许群内成员，可用黑名单限制 |
| `/hd status` | 查看装备库、重抽时间窗和出图状态 | 允许群内成员，可用黑名单限制 |
| `/hd help [主题]` | 查看总览或命令说明 | 允许群内成员，可用黑名单限制 |
| `/hd diag` | 执行真实图片渲染及发送自检 | 允许群内的宿主操作员、管理员白名单 |

可使用中文动作与简写，例如 `/潜兵 配装`、`/hd lo 3`；完整别名见 `/hd help`。所有命令仅在 `allowed_groups` 中的群可用，私聊不可用；**不需要订阅**。

八格依次为：`1 主武器 / 2 副武器 / 3 投掷物 / 4 强化资源 / 5–8 战略配备`，四项战略配备互不重复。默认在 120 秒内可重抽单格，每次成功重抽刷新有效期；会话按“聊天流 + 用户”隔离。

## 配置与权限

仅有四项插件配置，编辑 `config.toml` 维护，完整注释见 [config.example.toml](config.example.toml)：

```toml
[plugin]
allowed_groups = []
admin_users = []
command_blacklist = {}
loadout_reroll_seconds = 120
```

- `allowed_groups`：全局群白名单，值为群号字符串列表；默认 `[]` 拒绝所有命令，只能在配置文件内添加或移除群，WebUI 配置表单隐藏此项。
- `admin_users`：管理员账号白名单；在允许群内，仅宿主操作员和这些账号能执行 `diag`。
- `command_blacklist`：功能命令黑名单，键为 `loadout`、`status`、`help` 或 `"*"`，值为账号字符串列表。
- `loadout_reroll_seconds`：单格重抽有效秒数，配置模型允许 `10–3600`。

所有命令先检查群白名单：未配置的群、空名单以及没有群号的私聊都拒绝，宿主操作员和管理员也不能绕过。通过群检查后，权限优先级为：宿主操作员 → `admin_users` → 功能命令黑名单 → 允许群成员可用。管理员不受功能命令黑名单限制；黑名单不负责授权 `diag`。例如：

```toml
[plugin]
allowed_groups = ["987654321"]
admin_users = ["123456789"]
loadout_reroll_seconds = 120

[plugin.command_blacklist]
"*" = ["10001"]
loadout = ["10002"]
```

## 图卡与装备数据

图卡使用仓库内的 `loadout_data.json` 和 `loadout_icons.json`，HTML 自包含，渲染时禁止访问外网；运行时不请求 Wiki。缺少单项图标时显示名称，整卡渲染或发送失败时返回文字。

本版保留源项目**截至 2026-10-21** 的 221 项装备及对应内嵌图标：56 件主武器、26 件副武器、24 件投掷物、20 项强化资源、95 项战略配备。这是带日期的数据快照，不保证与后续游戏版本同步。

装备目录源自 Helldivers Wiki 中英文目录及条目；每项记录保留来源、翻译依据及可用修订号。中文、英文 Wiki 衍生文本分别遵循 CC BY-SA 4.0、CC BY-NC-SA 4.0，英文来源部分具有非商业限制。游戏图像仍归各自权利人，不因来自 Wiki 而自动适用 Wiki 文本许可；原随机配装参考项目及素材来源的完整署名见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

只有维护者手动执行 `python tools/refresh_loadout_database.py` 时才访问外部 Wiki；该工具需要 `requirements-dev.txt` 中的 Beautiful Soup。刷新后必须重新检查目录、翻译、图标来源及授权说明，本版未因独立拆分而刷新数据。

若只返回文字，由管理员执行 `/hd diag` 检查：宿主需启用 `plugin_runtime.render.enabled`，安装 Playwright 与 Chromium，并允许 `render.html2png` 和图片发送。首次启动浏览器较慢时可完成初始化后重试。

## 开发验证

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

回归验证涵盖随机配装、重抽隔离与过期、全局群白名单及管理员权限、离线渲染与文字回退、真实 SDK 注册，以及数据与图标完整性。模拟宿主验证无法代替真实 MaiBot 的端到端测试。

## 许可与贡献

原创代码与文档使用 [MIT License](LICENSE)，Copyright © 2026 TouristH。保留 HelldiversPatchFeed 原项目、Helldivers Wiki 贡献者、Xenfo-LC 参考项目及相关素材贡献者的署名；这些第三方内容不自动纳入 MIT。完整贡献说明见 [CONTRIBUTORS.md](CONTRIBUTORS.md)。OpenAI Codex 是 AI 辅助贡献者，不是仓库所有者、维护者或版权持有人。

问题与建议请提交至 [GitHub Issues](https://github.com/TouristH/DemocracyChooses/issues)。
