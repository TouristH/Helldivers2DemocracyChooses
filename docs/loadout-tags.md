# 配备标签编辑说明

插件优先直接读取根目录 `loadout_tags.xlsx` 的“装备标签”工作表；Excel不存在时才读取 `loadout_tags.csv`。保存后下次读取生效，无需重新生成 JSON。

- `id`、名称、英文名和槽位用于匹配原装备，请保持不变。
- 标签用 `|` 分隔；可以填写下表中文标签，也可以填写标签 ID。空白玩家定位或评价表示尚无足够反馈。
- 玩家定位与玩家评价优先描述实战体验；资料定位和机制保留资料事实。重甲穿透不等于反重方便。
- 反重便利性可填：方便、有条件、应急、不适用、有分歧、待评价。请在编辑说明写适用敌人、距离、弱点、弹药或其他条件。
- 支援武器槽和背包槽可填：是、否、待核实；未知不会当成不占用。
- 核实状态可填：已核实、部分核实、人工复核。请勿把搜索摘要当成完整实机验证。
- 原始研究与来源保存在 `loadout_knowledge.json`，编辑表格不会覆盖原始证据；读取接口会自动标出分类、标签、便利性或占用等结构字段与研究基线不同的行。
- “玩具”仅表示带条件、有分歧的社区整活/扮演评价。可以与实用定位共存，不代表装备完全无效，也不会自动禁止抽取。
- 当前版本仅建立知识库与读取接口，尚未启用“尽量合理”的抽取规则。`/hd status` 会显示实际读取的文件、覆盖数及修改数。

维护者可执行 `python tools/check_loadout_knowledge.py` 校验，或加 `--item 'P-4 Senator'` 查看一件装备。表格缺行、重复ID、未知标签等会给出行号；原随机配装不依赖知识库成功读取。


## Excel 映射与 CSV 导出

- 推荐编辑 `loadout_tags.xlsx` 的浅黄色区域。表头和名称列已冻结，可以筛选和排序。
- 程序按表头映射，允许调整列顺序和增加个人备注列；请保留“装备标签”工作表名称及必需表头。
- 标签字段使用纯文本，多个标签以 `|` 分隔；公式字段会明确拒绝，不读取可能过期的缓存结果。
- 字典页供查阅；新增词汇需要在 `loadout_knowledge.json` 的 taxonomy 中登记，已有分类与标签可直接选用。
- Excel存在但损坏或字段有误时不会回读旧CSV，避免误以为Excel修改已经生效；普通随机配装仍可使用。
- 运行 `python tools/check_loadout_knowledge.py --export-csv loadout_tags.csv` 可将当前实际表格校验后导出；仅校验CSV可加 `--table loadout_tags.csv`。
- 长研究备注和来源放在主表右侧，选中单元格后可在编辑栏查看全文。

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

## 标签字典

| 标签 | 类型 | ID | 含义 |
|---|---|---|---|
| 机器人玩家推荐 | 玩家评价 | `community.automaton_recommended` | 玩家机器人战线配装清单中推荐；具体任务与使用条件见来源。 |
| 光能玩家推荐 | 玩家评价 | `community.illuminate_recommended` | 玩家光能战线配装清单中推荐；不等同于通用强度或方便反重。 |
| 玩具 | 玩家评价 | `community.toy` | 有玩家认为偏整活、角色扮演或耍帅，实用性有限；保留版本、条件及反例，不表示完全无效。 |
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
| 对空 | 实战职责 | `role.anti_air` | 有来源支持的对空用途，不承诺通用锁定或击杀。 |
| 反中型 | 实战职责 | `role.anti_medium` | 处理中型威胁的定位，不直接等同于某个穿甲等级。 |
| 反重 | 实战职责 | `role.anti_tank` | 承担重型威胁处理职责；便利程度、弱点和弹药条件另列。 |
| 区域封锁 | 实战职责 | `role.area_denial` | 持续影响一片区域，限制敌方通行或驻留。 |
| 清杂 | 实战职责 | `role.crowd_clear` | 处理轻型敌群的实战职责；不等同于控制敌人行动。 |
| 控场 | 实战职责 | `role.crowd_control` | 通过眩晕、错乱、击退等手段限制敌方行动。 |
| 机动 | 实战职责 | `role.mobility` | 提供移动或转移方面的帮助。 |
| 任务辅助 | 实战职责 | `role.objective_support` | 有助于样本、撤离或其他任务流程。 |
| 防护 | 实战职责 | `role.protection` | 用于减伤、挡弹或掩护。 |
| 潜行 | 实战职责 | `role.stealth` | 有隐蔽或脱离交战用途；不保证完全不被发现。 |
| 拆迁 | 实战职责 | `role.structure_demolition` | 可处理部分生成点或设施；具体对象和限制见备注。 |
| 续航支援 | 实战职责 | `role.sustain` | 提供补给、治疗等续航用途。 |
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

## 本轮研究范围

当前覆盖221项装备，共157条来源记录。沿用2026-10-21装备目录，研究日期为2026-11-08；未声称补全后续新增装备。Wiki正文访问受限，使用搜索索引的条目明确标为部分核实；社区评价保留所引讨论的时间与使用条件。

资料与社区意见的许可、署名边界见根目录 `THIRD_PARTY_NOTICES.md`。
