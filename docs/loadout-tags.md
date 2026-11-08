# 配备标签编辑说明

插件优先读取 `loadout_tags.xlsx` 的“装备标签”工作表；Excel不存在时才读取 `loadout_tags.csv`。保存后下次读取生效。

MaiBot 1.4 起，标签表从本实例的数据目录读取（`data/plugins/<插件 ID>/`，`/hd status` 会显示实际路径）：首次使用时从插件目录复制一份 `loadout_tags.xlsx` 和 `loadout_knowledge.json`，之后编辑数据目录里的副本才生效；删掉工作簿改用 CSV 时不会被重新播种。1.3 及更老的宿主没有数据目录，仍读取插件目录里的文件。

## 玩家标签集与独立标签

“玩家标签集”是一列便于审阅的显示集合。例如 `控场；清杂；易误伤` 对应三个独立ID：`player.crowd_control`、`player.crowd_clear`、`player.friendly_fire_risk`。另一个例子 `反重；简易使用；对单` 同样是三个标签，组合本身不会注册为标签。

玩家词表固定为25个独立标签，可自行排列组合、重复输入会去重。运行时 `EquipmentKnowledge.player_tags` 是 `frozenset[str]`，支持逐项查询和匹配；`player_tag_display` 只是由这些ID生成的中文分号显示文本。

- 多个标签推荐用中文分号 `；` 分隔；英文分号、竖线和顿号也可识别，中文名称与ID均可填写。
- 标签顺序不影响匹配；导出和显示按词表顺序排列。未知词或跨维度标签会明确报错。
- 已取消独立的反重便利性列、评分和运行时字段。职责、操作要求、目标范围、风险与评价都是独立标签。
- ‘有条件’不自动等于难用，‘反重’不自动等于对单；只在原有玩家证据明确支持时补相应标签。
- 玩家标签优先用于实战判断；机制标签和资料定位仍独立保留，不由穿甲等级推导实战效率。
- ‘玩具’和‘评价有分歧’可以与实用定位共存。未知或缺证据时留空，不强行填满标签。

## 编辑、映射与导出

- 浅黄色区域可编辑，允许排序、筛选、调整列顺序或添加个人备注列；程序按表头映射。
- 请保留‘装备标签’工作表和必需表头；id、名称、英文名、槽位用于匹配原装备，请保持不变。
- 标签用纯文本填写；公式缓存不会作为标签读入。分类、占用和核实状态有单选下拉。
- 支援武器槽/背包槽填：是、否、待核实；核实状态填：已核实、部分核实、人工复核。
- Excel存在但格式有误时不静默回读旧CSV。状态查询提示问题，原随机配装仍可使用。
- `python tools/check_loadout_knowledge.py` 校验实际读取的表；可加 `--item 'P-4 Senator'` 查单件。
- `python tools/check_loadout_knowledge.py --export-csv loadout_tags.csv` 将当前有效表格导出为标准CSV；指定 `--table loadout_tags.csv` 可单独读取CSV。
- 来源和研究条件放在主表右侧；选中长备注单元格后可在编辑栏查看全文。编辑表格不会改写JSON中的逐项证据，结构字段修改会被接口识别。

## 向 Dev 提交标签意见

欢迎通过 [Dev标签反馈表单](https://github.com/TouristH/Helldivers2DemocracyChooses/issues/new?template=tag-feedback.yml) 补充、删除或纠正标签。请写装备名或ID、建议的独立标签，以及阵营/难度/搭配等使用条件；有Reddit、贴吧、B站链接或自己的实战例子更方便核对。

Issue由仓库共用，表单以 `[Dev 标签反馈]` 标识开发版意见。提议经维护者核对后更新Dev知识库，不会自动把任意组合当成新标签。

## 固定玩家词表

| 标签 | ID | 含义 |
|---|---|---|
| 反重 | `player.anti_tank` | 玩家反馈可承担重型威胁处理；适用目标与条件见研究备注。 |
| 反中 | `player.anti_medium` | 处理中型威胁的玩家定位，不由穿甲等级自动生成。 |
| 对空 | `player.anti_air` | 有玩家实战依据的对空用途。 |
| 控场 | `player.crowd_control` | 通过眩晕、错乱、硬直等限制敌人行动。 |
| 清杂 | `player.crowd_clear` | 适合清理轻型敌群的玩家定位。 |
| 拆迁 | `player.structure_demolition` | 有玩家依据的生成点或设施处理用途，具体对象见备注。 |
| 区域封锁 | `player.area_denial` | 持续影响区域、限制敌方通行或驻留。 |
| 续航支援 | `player.sustain` | 补给或治疗等续航支援用途。 |
| 防护 | `player.protection` | 玩家认可的减伤、挡弹或掩护用途。 |
| 机动 | `player.mobility` | 帮助移动、转移或接近目标。 |
| 潜行 | `player.stealth` | 有实际隐蔽或脱战反馈，不将出现在潜行配装中等同无声属性。 |
| 任务辅助 | `player.objective_support` | 对样本、撤离、增援等任务流程有帮助。 |
| 简易使用 | `player.easy_to_use` | 玩家在备注场景中认为操作直观或命中要求较宽容，不保证无条件有效。 |
| 需精确瞄准 | `player.precise_aim_required` | 较依赖弱点或精确命中，适用目标与距离见备注。 |
| 需准备 | `player.preparation_required` | 发挥依赖蓄力、架设、等待或合适站位等准备条件。 |
| 补给依赖 | `player.supply_dependent` | 玩家明确指出弹量或持续作战对补给的依赖。 |
| 对单 | `player.single_target` | 有明确单个或指定目标的实战定位，不由反重标签自动推导。 |
| 对群 | `player.area_target` | 有明确多目标或范围作战反馈，不由清杂标签自动推导。 |
| 易误伤 | `player.friendly_fire_risk` | 玩家明确讨论的友军误伤风险。 |
| 易自伤 | `player.self_damage_risk` | 玩家明确讨论的自伤风险。 |
| 应急补位 | `player.emergency_backup` | 在备注所述目标或场景中更适合作为补充，不等于整件装备只能应急。 |
| 玩具 | `player.toy` | 部分玩家认为偏整活、角色扮演或耍帅，保留实用反例，不等于完全无效。 |
| 评价有分歧 | `player.disputed` | 存在不同玩家体验或不同条件下的相反反馈，具体内容见备注。 |
| 机器人推荐 | `player.automaton_recommended` | 玩家机器人战线配装推荐，不是通用强度评级。 |
| 光能族推荐 | `player.illuminate_recommended` | 玩家光能族战线配装推荐，不是通用强度评级。 |

## 分类字典

| 分类 | ID |
|---|---|
| 突击步枪 | `assault_rifle` |
| 下挂榴弹突击步枪 | `assault_rifle_with_underbarrel_grenade_launcher` |
| 下挂霰弹突击步枪 | `assault_rifle_with_underbarrel_shotgun` |
| 背包 | `backpack` |
| 栓动狙击步枪 | `bolt_action_sniper_rifle` |
| 强化资源 | `booster` |
| 连发等离子狙击步枪 | `burst_plasma_sniper_rifle` |
| 蓄力等离子步枪 | `chargeable_plasma_rifle` |
| 飞鹰支援 | `eagle` |
| 部署设施 | `emplacement` |
| 能量精确步枪 | `energy_marksman_rifle` |
| 能量武器 | `energy_weapon` |
| 爆炸栓动步枪 | `explosive_bolt_action_rifle` |
| 爆炸弩 | `explosive_crossbow` |
| 喷火器 | `flamethrower` |
| 毒气手枪 | `gas_pistol` |
| 制导导弹手枪 | `guided_missile_pistol` |
| 激光左轮 | `laser_revolver` |
| 自动手枪 | `machine_pistol` |
| 精确射手步枪 | `marksman_rifle` |
| 近战武器 | `melee_weapon` |
| 雷区 | `minefield` |
| 轨道支援 | `orbital` |
| 手枪 | `pistol` |
| 等离子发射器 | `plasma_launcher` |
| 等离子步枪 | `plasma_rifle` |
| 泵动榴弹发射器 | `pump_action_grenade_launcher` |
| 自动哨戒炮 | `sentry` |
| 霰弹枪 | `shotgun` |
| 单发爆炸手枪 | `single_shot_explosive_pistol` |
| 特殊主武器 | `special_primary` |
| 特殊副武器 | `special_secondary` |
| 特殊投掷物 | `special_throwable` |
| 常规投掷物 | `standard_throwable` |
| 黏附燃烧导弹手枪 | `sticky_incendiary_missile_pistol` |
| 治疗手枪 | `stim_pistol` |
| 冲锋枪 | `submachine_gun` |
| 支援武器 | `support_weapon` |
| 载具 | `vehicle` |

## 资料与机制标签

| 标签 | 类型 | ID | 含义 |
|---|---|---|---|
| 不可常规拆迁 | 辅助与限制 | `limitation.no_demolition` | 来源明确限制普通生成点拆除用途，例外见备注。 |
| 反坦克特征（资料） | 资料机制 | `mechanic.anti_tank_trait` | 仅记录Wiki展示的Anti-Tank特征，不表示实战反重效率或便利性。 |
| 电弧 | 资料机制 | `mechanic.arc` | 电弧机制；不把所有电击或眩晕都归为电弧。 |
| 自动运作 | 资料机制 | `mechanic.autonomous` | 部署后由装备自动攻击或触发。 |
| 背包供弹 | 资料机制 | `mechanic.backpack_fed` | 装备使用配套背包供应弹药；槽位占用单独记录。 |
| 动能投射 | 资料机制 | `mechanic.ballistic` | 实弹或其他动能投射物机制；不推断穿甲和伤害。 |
| 蓄力 | 资料机制 | `mechanic.charge` | 存在蓄力机制或蓄力模式。 |
| 消耗式 | 资料机制 | `mechanic.expendable` | 用后丢弃或消耗，需要后续重新获得。 |
| 爆炸 | 资料机制 | `mechanic.explosive` | 存在爆炸机制；不自动推断拆迁或反重能力。 |
| 对敌燃烧 | 资料机制 | `mechanic.fire` | 对敌方造成燃烧或火焰效果，区别于装备自燃风险。 |
| 引信延时 | 资料机制 | `mechanic.fuse` | 使用延时引信，不给出固定秒数。 |
| 毒气 | 资料机制 | `mechanic.gas` | 毒气伤害或状态机制。 |
| 制导 | 资料机制 | `mechanic.guided` | 存在制导或追踪机制，不意味着无需瞄准。 |
| 热量管理 | 资料机制 | `mechanic.heat` | 具有热量相关机制，需要考虑冷却和过热。 |
| 重甲穿透（资料） | 资料机制 | `mechanic.heavy_penetration_trait` | 界面或Wiki展示的重甲穿透特征；条件和模式见备注，不等同可靠反重。 |
| 喷射舱相关 | 资料机制 | `mechanic.hellpod` | 效果与喷射舱投放相关。 |
| 触碰起爆 | 资料机制 | `mechanic.impact` | 碰撞后触发爆炸。 |
| 激光 | 资料机制 | `mechanic.laser` | 激光机制；不自动意味着热量武器或无限弹药。 |
| 轻甲穿透（资料） | 资料机制 | `mechanic.light_penetration_trait` | 界面或Wiki展示的轻甲穿透特征，不是实战定位。 |
| 次数有限 | 资料机制 | `mechanic.limited_uses` | 单次任务或部署存在使用次数限制。 |
| 中甲穿透（资料） | 资料机制 | `mechanic.medium_penetration_trait` | 界面或Wiki展示的中甲穿透特征，不是实战定位。 |
| 近战 | 资料机制 | `mechanic.melee` | 可直接进行近战攻击；投掷刀具不自动归入。 |
| 单手使用 | 资料机制 | `mechanic.one_handed` | 装备资料标注单手使用，不等同于无背包。 |
| 等离子 | 资料机制 | `mechanic.plasma` | 等离子机制。 |
| 近炸 | 资料机制 | `mechanic.proximity` | 接近目标后触发，条件见备注。 |
| 需单手武器配合 | 资料机制 | `mechanic.requires_one_handed` | 使用时需要单手武器配合，具体条件见来源。 |
| 护盾 | 资料机制 | `mechanic.shield` | 具有护盾或屏障机制。 |
| 烟雾 | 资料机制 | `mechanic.smoke` | 烟幕机制。 |
| 固定部署 | 资料机制 | `mechanic.stationary` | 部署后通常固定于位置，不随玩家携带。 |
| 黏附 | 资料机制 | `mechanic.sticky` | 可附着在命中目标或表面。 |
| 眩晕 | 资料机制 | `mechanic.stun` | 存在眩晕、麻痹等控制效果，适用对象见来源。 |
| 友伤风险 | 辅助与限制 | `risk.friendly_fire` | 来源明确讨论的友伤风险，非统一危险性排名。 |
| 自伤风险 | 辅助与限制 | `risk.self_damage` | 有来源支持的自伤风险。 |
| 对空 | 资料定位 | `role.anti_air` | 有来源支持的对空用途，不承诺通用锁定或击杀。 |
| 反中型 | 资料定位 | `role.anti_medium` | 处理中型威胁的定位，不直接等同于某个穿甲等级。 |
| 反重 | 资料定位 | `role.anti_tank` | 承担重型威胁处理职责；便利程度、弱点和弹药条件另列。 |
| 区域封锁 | 资料定位 | `role.area_denial` | 持续影响一片区域，限制敌方通行或驻留。 |
| 清杂 | 资料定位 | `role.crowd_clear` | 处理轻型敌群的实战职责；不等同于控制敌人行动。 |
| 控场 | 资料定位 | `role.crowd_control` | 通过眩晕、错乱、击退等手段限制敌方行动。 |
| 机动 | 资料定位 | `role.mobility` | 提供移动或转移方面的帮助。 |
| 任务辅助 | 资料定位 | `role.objective_support` | 有助于样本、撤离或其他任务流程。 |
| 防护 | 资料定位 | `role.protection` | 用于减伤、挡弹或掩护。 |
| 潜行 | 资料定位 | `role.stealth` | 有隐蔽或脱离交战用途；不保证完全不被发现。 |
| 拆迁 | 资料定位 | `role.structure_demolition` | 可处理部分生成点或设施；具体对象和限制见备注。 |
| 续航支援 | 资料定位 | `role.sustain` | 提供补给、治疗等续航用途。 |
| 弹药辅助 | 辅助与限制 | `utility.ammo` | 与弹药供应或携带相关。 |
| 反重装备配发 | 辅助与限制 | `utility.anti_tank_supply` | 提供反重装备，不等于强化本身直接反重。 |
| 落地物资 | 辅助与限制 | `utility.deployment_supplies` | 影响投放时携带或获得的物资。 |
| 侦测 | 辅助与限制 | `utility.detection` | 与探测、雷达等信息获取有关。 |
| 遭遇间隔 | 辅助与限制 | `utility.encounter_delay` | 影响敌方增援或遭遇间隔。 |
| 撤离辅助 | 辅助与限制 | `utility.extraction` | 影响撤离流程。 |
| 灭火辅助 | 辅助与限制 | `utility.fire_recovery` | 帮助应对着火状态。 |
| 增援辅助 | 辅助与限制 | `utility.reinforcement` | 影响增援资源或恢复。 |
| 补给辅助 | 辅助与限制 | `utility.resupply` | 与补给过程有关。 |
| 样本辅助 | 辅助与限制 | `utility.samples` | 与样本发现、回收或保留有关。 |
| 减速恢复 | 辅助与限制 | `utility.slow_recovery` | 帮助应对减速状态。 |
| 耐力辅助 | 辅助与限制 | `utility.stamina` | 影响耐力或奔跑续航。 |
| 治疗剂强化 | 辅助与限制 | `utility.stim_effect` | 影响治疗剂使用或效果。 |

当前为Dev知识库和读取接口，尚未启用合理抽取规则。覆盖既有221项装备；157条来源记录、研究日期2026-11-08，沿用2026-10-21装备目录。Wiki索引资料仍为部分核实；社区讨论的时间、条件、分歧和原出处继续保留。

素材与来源的许可、署名边界见 `THIRD_PARTY_NOTICES.md`。
