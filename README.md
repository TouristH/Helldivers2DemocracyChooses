# 绝地潜兵 2：民主帮你选择

> 当前为 **Dev 开发分支**，包含配备知识库及 Excel 映射。正式稳定版为 [v0.3.2](https://github.com/TouristH/Helldivers2DemocracyChooses/releases/tag/v0.3.2)，本分支改动暂不发布正式 Release。

![军需部门已点头批准这次配装](assets/icon.webp)

[![Tests](https://github.com/TouristH/Helldivers2DemocracyChooses/actions/workflows/tests.yml/badge.svg)](https://github.com/TouristH/Helldivers2DemocracyChooses/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **“解放你大业的！队友已经催第三遍了，我还没决定带哪把枪！”**

绝地潜兵！你能顶着炮火捡回样本，能在虫群里搓出增援，还能把“最后一把”打到凌晨三点，却总在四个战略配备格子面前陷入漫长的独立思考。

超级地球对此深表关切：你在军械库里犹豫的每一分钟，都是敌人没有挨炸的一分钟。

我是你的临时军需官，**“民主帮你选择”**。主武器、副武器、投掷物、强化资源，再加四项不重复的战略配备，我替你抽好整套行头。你负责输入命令，民主负责作出选择；至于这套东西落地以后能活多久，属于前线实践问题。

对配发结果有意见？当然可以。管理式民主充分尊重你的选择权：**接受这套装备，或者在 120 秒内申请民主再选一次。**

这是一款面向 MaiBot Plugin SDK 2.x 的 **HELLDIVERS 2（绝地潜兵2）随机配装**插件，分类为**游戏娱乐**（`game`）。英文 **Democracy Chooses** 意为“由民主作出选择”。现在，停止翻菜单，准备投放。

## 军需部门能替你办什么

- **整套配发，免去思考**：一次抽出八格装备。四项战略配备互不重复；战术价值请在着陆后自行验证。
- **有限度的民主复议**：不满意哪一格，就单独重抽哪一格，另外七格继续服役。默认 120 秒内有效，每次成功重抽都会重新计时。
- **责任落实到人**：配装会话按“聊天流 + 用户”隔离。队友可以质疑你的品味，但不能用自己的重抽命令替你换枪。
- **附带彩色军需清单**：装备图标已经装进插件，配装卡渲染时不访问外网。浏览器或图片发送出了问题，就改发文字——打印机可以罢工，配发工作不能停。
- **军需官专用检修通道**：状态查询、管理员出图诊断、全局群白名单和功能命令黑名单一并提供。权限不以军衔、嗓门或对超级地球的口头忠诚程度为准。

> 本部门负责随机配发，不负责评估搭配合理性，也不会检查你是否已解锁抽到的装备。请在出发前自行核对军械库。

## 先把军需部门装进麦麦

| 项目 | 要求或声明范围 |
|---|---|
| MaiBot Host | manifest 声明 `1.0.0–1.4.99`（1.4.x 已按多实例与命令权限改动适配） |
| MaiBot Plugin SDK | 依赖 `>= 2.7.1, < 3.0.0`；manifest 声明 `2.7.1–2.22.99`（MaiBot 1.4.3 随附 2.22.1） |
| Python | 开发验证使用 3.12；部署以 MaiBot/SDK 支持的版本为准 |
| 图片渲染 | 宿主环境安装 `playwright>=1.54.0` 和 Chromium，并开放渲染能力 |

以上是兼容声明，不代表已经逐个版本实机测试。当前本地验证使用真实 SDK（2.7.1 与 2.22.1 两套测试矩阵）与模拟宿主，尚未完成真实 MaiBot 宿主的加载、图片发送和配置热更新端到端验证。兼容区间格式依据 MaiBot 的 [Manifest 文档](https://docs.maibot.chat/plugin/manifest)；后续宿主版本需重新验证后再扩大范围。

### 在 MaiBot 1.4 上要注意的两件事

- **多实例各读各的数据。** 1.4 允许一个 MAIBOT 跑多只麦麦，每个实例只有自己的 `data/plugins/<插件 ID>/` 目录。装备清单（`loadout_data.json`）和标签库（`loadout_tags.xlsx`、`loadout_knowledge.json`）优先从那里读取，第一次使用时从插件目录复制过去；改这份副本（而不是源码目录里的那份）才会生效，插件更新覆盖源码也不会再把改动删掉。`/hd status` 会显示当前实例实际使用的数据目录。1.3 及更老的宿主没有这个目录接口，仍然读插件目录里的文件，行为与升级前一致。
- **命令权限多了一层。** 1.4 的「配置 → 命令权限」可以按用户或聊天限制插件命令，宿主会在命令到达插件之前先拦一次；插件自己的 `allowed_groups`、`admin_users` 和 `command_blacklist` 照常生效，两层都要放行。命令目录（`/pm cmd`）里本插件显示为 `public`：公开动作与管理指令 `diag` 共用同一个命令组件，`diag` 的管理员判定由插件自己完成。

在 MaiBot 的 `plugins` 目录执行：

```bash
git clone --branch Dev https://github.com/TouristH/Helldivers2DemocracyChooses.git
```

在**运行 MaiBot 宿主的同一个 Python 环境**安装依赖和渲染浏览器：

```bash
python -m pip install -r plugins/Helldivers2DemocracyChooses/requirements.txt
python -m playwright install chromium
```

重启 MaiBot，Runner 会发现根目录的 `_manifest.json` 和 `plugin.py`，并生成 `config.toml`。编辑该文件，在 `[plugin]` 的 `allowed_groups` 中填入允许使用的群号；默认空名单拒绝全部命令。群白名单只能在配置文件中维护，不提供群聊增删或订阅命令。

这一步请认真完成。未经登记的群尚未获准领取民主，管理员本人也不能靠拍桌子领取。

只使用文字配装时无需安装浏览器；图片渲染或发送失败会自动回退文字。插件只声明 `send.text`、`send.image`、`render.html2png` 三项能力。

插件中心的登记与迁移进度见[相关申请](https://github.com/Mai-with-u/plugin-repo/issues?q=is%3Aissue+%22github.touristh.helldivers2-democracy-chooses%22)。审核状态以申请页面为准；在此之前可按上方步骤手动安装。

## 向军需部门递交申请

`/helldivers`、`/hd`、`/潜兵`、`/绝地潜兵` 四个前缀等价。军需官接受简写，不接受“我以为队友帮我带了”。

| 命令 | 用途 | 默认权限 |
|---|---|---|
| `/hd loadout` | 领取一整套随机配装，停止在菜单里服役 | 允许群内成员，可用黑名单限制 |
| `/hd loadout 1-8` | 在有效期内重抽指定格，重新理解民主的安排 | 允许群内成员，可用黑名单限制 |
| `/hd status` | 查看装备库、标签覆盖及修改数、重抽时间窗和出图状态 | 允许群内成员，可用黑名单限制 |
| `/hd help [主题]` | 阅读使用说明；本部门保留“早就写了”的权利 | 允许群内成员，可用黑名单限制 |
| `/hd diag` | 执行真实图片渲染及发送自检 | 允许群内的宿主操作员、管理员白名单 |

可使用中文动作与简写，例如 `/潜兵 配装`、`/hd lo 3`；完整别名见 `/hd help`。所有命令仅在 `allowed_groups` 中的群可用，私聊不可用；**不需要订阅**。

八格依次为：`1 主武器 / 2 副武器 / 3 投掷物 / 4 强化资源 / 5–8 战略配备`，四项战略配备互不重复。默认在 120 秒内可重抽单格，每次成功重抽刷新有效期；会话按“聊天流 + 用户”隔离。过期后需要重新抽取整套配装，另一个人的抽签结果不归你重审。

例如，先领取配装，再让民主重新考虑一下投掷物：

```text
/hd loadout
/hd loadout 3
```

## 军需部的配备标签簿

“尽量合理”先从认识装备开始。当前为既有 **221 项配备**整理了分类与标签，推荐直接编辑根目录 [loadout_tags.xlsx](loadout_tags.xlsx) 的“装备标签”工作表。提供筛选、冻结表头与名称列、分类和占用等下拉选项，以及可查阅的标签字典；浅黄色区域为可编辑字段。保存后插件下一次读取即使用新内容，无需重建 JSON；`/hd status` 会显示实际读取的文件、覆盖数与标签修改数。

读取顺序为 **Excel 优先，Excel 不存在时才读取 [CSV](loadout_tags.csv)**，不会混用两份内容。Excel 有错误时会提示校验问题，不会静默沿用旧 CSV。仍想编辑 CSV 时，请先移走同目录 Excel，再按 UTF-8 CSV 保存；校验工具也支持 `--table loadout_tags.csv` 显式读取。

- **固定玩家标签，独立排列组合**：统一使用 25 个独立标签，覆盖实战职责、操作要求、目标范围、风险与评价。表格显示的“玩家标签集”只是阅读视图，例如 `控场；清杂；易误伤` 或 `反重；简易使用；对单`；程序分别保存和匹配每个标签 ID，组合本身不会成为新标签。
- **机制事实另存**：穿透资料、爆炸、燃烧、单手、背包供弹等独立保留。重甲穿透不会自动变成“反重方便”。
- **玩家标签优先用于实战判断**：“玩具”“评价有分歧”“需精确瞄准”等同样是独立标签，备注保留场景、争议和实用反例。没有单列的反重便利性评分，也不从“有条件”推导难用或从反重推导对单。
- **占用明确登记**：支援武器槽与背包槽分开记录，自带弹药背包也计入背包占用。

分类、独立标签与占用都可以在表格中调整；`id`、装备名称、英文名和槽位请保持不变。Excel 允许排序、筛选、调整列顺序和添加个人备注列，程序按表头映射；请保留“装备标签”工作表名称和必需表头，标签字段使用纯文本。多个标签推荐用中文分号 `；` 分隔，英文分号、竖线、顿号以及中文名称或标签 ID 也能识别。输入顺序不影响匹配，重复标签会去重。固定词表与完整字典见 [标签编辑说明](docs/loadout-tags.md)，查证记录及逐条来源保存在 [loadout_knowledge.json](loadout_knowledge.json)。表格修改不会改写原始研究证据，读取接口会识别标签、分类和占用等结构字段的修改。

维护者可运行 `python tools/check_loadout_knowledge.py --export-csv loadout_tags.csv`，将当前实际使用的 Excel 内容校验后导出为标准 CSV；读取 Excel 使用 Python 标准库，无需额外安装 Excel 库。

**当前已建成战备知识库与读取接口，但尚未启用“尽量合理”的抽取规则。** 已按全部战略配备名与社区简称批量检索国内社区（B站、贴吧、小黑盒），积累 354 条来源、159 件装备带玩家标签；逐条结论都带日期、阵营与使用条件。国内社区证据优先于海外讨论；同一标签在时间线上出现不同结论时以较新证据为准，旧观点保留在备注并标注「历史观点」，不再作为当前标签。Wiki 正文访问受限，使用搜索索引摘录的记录仍标为“部分核实”；缺证据时玩家标签留空，具体限制保留在研究备注中。这本簿子允许补正，军需部暂不接受把“它能穿甲”当成“它打起来一定顺手”的审批依据。

### 请玩家帮军需部校对

欢迎通过 [Dev 标签反馈 Issue](https://github.com/TouristH/Helldivers2DemocracyChooses/issues/new?template=tag-feedback.yml) 提议补充、删除或纠正标签，也可以先[查看已有 Dev 标签反馈](https://github.com/TouristH/Helldivers2DemocracyChooses/issues?q=is%3Aissue+label%3ADev+label%3A%E6%A0%87%E7%AD%BE%E5%8F%8D%E9%A6%88)。请写装备名或 ID、建议增删的独立标签，以及阵营、难度、搭配和使用条件；附上 Reddit、贴吧、B站讨论链接或自己的实战例子会更方便核对。Issue 由仓库共用，表单以 `[Dev 标签反馈]` 和标签标识开发版意见，维护者复核后再更新 Dev 知识库。民主允许你提出意见，军需部负责逐条核对。

## 出勤名单与军需官权限

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

所有命令先检查群白名单：未配置的群、空名单以及没有群号的私聊都拒绝，宿主操作员和管理员也不能绕过。通过群检查后，权限优先级为：宿主操作员 → `admin_users` → 功能命令黑名单 → 允许群成员可用。管理员不受功能命令黑名单限制；黑名单不负责授权 `diag`。

下面给出一份已经填好的出勤表。请替换成自己的群号和账号，不要把示例号码当作超级地球统一编制：

```toml
[plugin]
allowed_groups = ["987654321"]
admin_users = ["123456789"]
loadout_reroll_seconds = 120

[plugin.command_blacklist]
"*" = ["10001"]
loadout = ["10002"]
```

## 军械库清点与打印机检修

图卡使用仓库内的 `loadout_data.json` 和 `loadout_icons.json`，HTML 自包含，渲染时禁止访问外网；运行时不请求 Wiki。缺少单项图标时显示名称，整卡渲染或发送失败时返回文字。

本版保留源项目**截至 2026-10-21** 的 221 项装备及对应内嵌图标：56 件主武器、26 件副武器、24 件投掷物、20 项强化资源、95 项战略配备。这是带日期的数据快照，不保证与后续游戏版本同步。军需部门库存有登记日期，不能靠一句“民主无所不能”自动补货。

装备目录源自 Helldivers Wiki 中英文目录及条目；每项记录保留来源、翻译依据及可用修订号。中文、英文 Wiki 衍生文本分别遵循 CC BY-SA 4.0、CC BY-NC-SA 4.0，英文来源部分具有非商业限制。游戏图像仍归各自权利人，不因来自 Wiki 而自动适用 Wiki 文本许可；原随机配装参考项目及素材来源的完整署名见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

只有维护者手动执行 `python tools/refresh_loadout_database.py` 时才访问外部 Wiki；该工具需要 `requirements-dev.txt` 中的 Beautiful Soup。刷新后必须重新检查目录、翻译、图标来源及授权说明，独立拆分和文案更新都不代表装备数据已经刷新。

若只返回文字，由管理员执行 `/hd diag` 检查：宿主需启用 `plugin_runtime.render.enabled`，安装 Playwright 与 Chromium，并允许 `render.html2png` 和图片发送。首次启动浏览器较慢时可完成初始化后重试。请先检修打印机，暂时不要把显示器列为非法广播。

## 军需部征集下一句标语

觉得配装结果里的随机标语还不够“民主”？欢迎[提交新标语提议](https://github.com/TouristH/Helldivers2DemocracyChooses/issues/new?template=motto-suggestion.yml)。你的独立思考已获准用于宣传，请在指定表格内发挥。

填入想加入的标语即可，也可以补充梗的说明或出处。建议每条控制在 **25 字以内**，方便图卡完整展示；军需审批、增援、样本回收以及管理式民主的黑色幽默都欢迎。提议由维护者审核，采用后随后续版本加入随机标语池。

## 维护人员的战前检查

测试和装备刷新请使用完整 Git 仓库。发行 ZIP 只包含插件运行文件、配置示例及说明与许可文件；测试、刷新工具、开发依赖清单和 GitHub 配置留在仓库中，不随安装包配发。

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

回归验证涵盖随机配装、重抽隔离与过期、全局群白名单及管理员权限、离线渲染与文字回退、真实 SDK 注册，以及数据与图标完整性。模拟宿主验证无法代替真实 MaiBot 的端到端测试。测试报告不接受用“反正还能增援”签字放行。

## 从哪里调来的军需部门

本项目从 [TouristH/HelldiversPatchFeed](https://github.com/TouristH/HelldiversPatchFeed/tree/555c3a5) 的配装功能独立精简而来。自 `0.1.1` 起，仓库为 `Helldivers2DemocracyChooses`，插件 ID 为 `github.touristh.helldivers2-democracy-chooses`。

本部门专职配装娱乐。原来的更新推送、运行时 Steam/Wiki 查询、后台轮询、订阅和公告数据库已经移除；需要战况、地图、公告查询及资讯订阅的潜兵，请前往 [fiatlux2333 的绝地潜兵 2 情报助手](https://github.com/fiatlux2333/maibot_plugin_Helldivers)。看战报和决定带什么枪，是两份不同的工作。

此前 `0.1.0` 使用不含游戏名的 ID `github.touristh.democracy-chooses`，该历史版本保持原样。已安装它的用户请先备份 `config.toml` 并停用旧 ID，再按新 ID 安装并恢复配置；此次 ID 修正不依赖旧插件的自动升级。

`0.3.0` 是用于承接旧插件中心登记的迁移版本，版本号高于旧项目的 `0.2.x`。登记修改使用 `Modify Plugin / 修改插件` 流程，由维护者审核旧 ID `github.touristh.helldivers2-patch-feed` 到当前 ID 与仓库的替换。旧版 Git 提交已保留以供历史核验，当前程序仍只提供配装娱乐功能；旧项目的历史 Release 继续保存在原仓库。

插件中心登记迁移不等于本地安装或配置自动迁移。旧 PatchFeed 用户请先备份配置并停用旧插件，再按当前 ID 安装；手动填写 `allowed_groups`，按需恢复管理员和黑名单配置。旧订阅与公告数据库不迁移。军需部门接受调任，不负责把旧办公室整栋空投过来。

## 地球上的许可与署名

以上军需部门口吻属于社区玩梗。本项目是非官方粉丝作品，与 Arrowhead Game Studios 或 Sony Interactive Entertainment 无关联。代码、Wiki 衍生文本和游戏图像的许可边界见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

原创代码与文档使用 [MIT License](LICENSE)，Copyright © 2026 TouristH。保留 HelldiversPatchFeed 原项目、Helldivers Wiki 贡献者、Xenfo-LC 参考项目及相关素材贡献者的署名；这些第三方内容不自动纳入 MIT。完整贡献说明见 [CONTRIBUTORS.md](CONTRIBUTORS.md)。OpenAI Codex 是 AI 辅助贡献者，不是仓库所有者、维护者或版权持有人。

发现问题请提交至 [GitHub Issues](https://github.com/TouristH/Helldivers2DemocracyChooses/issues)。配装太怪可以重抽；程序有问题请附复现步骤，军需官无法从一句“被民主了”里读出堆栈。
