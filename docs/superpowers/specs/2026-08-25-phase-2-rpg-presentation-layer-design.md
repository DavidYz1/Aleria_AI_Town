# Phase 2：2D RPG 展示层设计

**日期：** 2026-08-25
**状态：** 待审阅
**目标版本：** Phase 2 MVP
**技术选择：** Vue 3 + Phaser 3.90.0 + 现有 FastAPI Backend

## 1. 背景与目标

Phase 1 已完成腾讯作业最低要求闭环：Backend 提供 World State、NPC 状态与行为、NPC 对话、玩家语义地点和任务状态；Frontend 已能查看 NPC、推进世界、移动语义地点并完成任务。

Phase 2 不扩展核心玩法系统，而是在不破坏现有闭环的前提下增加一层可展示、可操作的 2D RPG 游戏外观：

1. 启动页；
2. 失忆冒险者创建页，支持玩家取名并从法师、游侠、牧师中三选一；
3. 简短、可跳过的剧情过场；
4. 一张可用 WASD/方向键移动的室外地图；
5. 地图展示酒馆、公园、城堡、森林入口以及 3 个由 Backend 驱动的 NPC；
6. 点击 NPC 后继续复用现有详情、状态和对话能力。

成功标准不是制作完整 RPG，而是让面试演示形成清晰的视觉叙事：创建角色 → 了解背景 → 进入世界 → 找到 NPC → 查看状态或交谈，同时保留现有任务闭环。

## 2. 明确不做的范围

本阶段不实现：

- 战斗、敌人和数值平衡；
- 背包、物品、技能、装备和掉落；
- 多张独立地图、室内地图或地图切换；
- Backend Player Schema 变更或数据库迁移；
- 玩家像素坐标持久化、坐标同步或新的 travel API；
- NPC 自由寻路、服务端像素坐标或多人同步；
- 职业属性、职业技能或职业分支；
- 用户账号、云存档或跨设备同步；
- 将全部现有 DOM 面板重写为 Canvas UI。

## 3. 核心架构原则

系统维持三个清晰边界：

| 层 | 唯一职责 | 数据权威 |
| --- | --- | --- |
| Backend | World State、NPC、任务、语义地点、对话生成 | 服务端数据库与领域服务 |
| Vue | 页面流程、本地角色档案、现有状态面板与 API 编排 | Pinia、localStorage、Backend 响应 |
| Phaser | 地图渲染、碰撞、镜头、键盘移动、Sprite 点击 | 当前浏览器内的表现状态 |

Phaser 中的 `(x, y)` 只表示玩家在画面上的位置。Backend 的 `location_id` 仍表示任务和对话使用的语义地点。两者不互相覆盖，也不建立伪精确同步。

现有 `/api/player/travel` 和对应 Vue 控件保留，用于任务闭环和玩家的语义地点变更；本阶段不新增任何由 WASD 移动触发的 travel 请求。这样既满足“玩家位置只作为 Phaser 表现状态”，也不会破坏现有依赖语义地点的任务规则。

## 4. 技术选型

### 4.1 选择 Phaser 而不是 PixiJS

本项目选择固定版本 `phaser@3.90.0`。

原因：

- Phaser 已提供 Scene 生命周期、输入、Arcade Physics、碰撞、相机、动画和 Tilemap；
- 本阶段需求天然是“小型 2D 游戏”，而不只是高性能渲染；
- PixiJS 是优秀的渲染器，但需要自行补齐场景、碰撞、输入约束、相机和地图对象组织，增加非业务代码；
- Phaser 3 生态成熟、资料稳定，比直接采用仍较新的 Phaser 4 更适合限时面试作业；
- 现有 Vue UI 无需迁入 Canvas，可通过小型事件桥接与 Phaser 组合。

不引入 `phaser-jsx`。参考项目中的 JSX 封装与当前 Vue 技术栈不匹配，直接采用会扩大依赖面和学习成本。

### 4.2 Vue 与 Phaser 的分工

- Scene 0～2 使用 Vue 组件实现，便于表单、文本、无障碍和响应式布局；
- Scene 3 由一个 Vue 容器挂载一个 Phaser Game；
- NPC 详情、任务、对话和世界推进继续使用 Vue DOM 面板；
- Phaser 通过窄事件接口只上报 `npcSelected(npcId)`、加载状态等 UI 事件；
- Vue 向 Phaser 提供经过适配的只读 NPC 投影和本地玩家外观配置。

## 5. 用户流程与场景设计

### 5.1 应用流程状态

应用层使用简单有限状态，而不为四个页面额外引入 Vue Router：

```text
boot → create → story → town
  └──────── profile exists + intro completed ────────→ town
  └──────── profile exists + intro not completed ───→ story
```

启动页每次加载都短暂展示品牌、加载状态和“继续冒险”。首次进入或本地档案无效时前往角色创建；已有有效档案时根据 `introCompleted` 进入剧情或城镇。

### 5.2 Scene 0：启动页面

- 展示游戏标题、简短副标题、加载进度和开始/继续按钮；
- 预加载关键字体、启动图和角色预览；
- Phaser 的地图资源在进入 Scene 3 时由 `BootScene` 加载，并提供明确的加载与重试状态；
- 不用人为延时阻塞用户。

### 5.3 Scene 1：失忆冒险者创建

- 玩家输入显示名；
- 玩家从法师、游侠、牧师中选择一个；
- 卡片展示职业外观、称谓和一句风格描述；
- 只有名称有效且职业已选择时才可继续；
- 提交后保存本地档案，进入剧情过场。

职业只表示失忆后选择的冒险方式，不定义角色失忆前的真实身份，避免与当前 Story Bible 冲突。

### 5.4 Scene 2：剧情过场

- 使用 3～5 个短段落交代：玩家在 Aleria 醒来、记忆缺失、小镇居民正面对异常事件；
- 支持点击/按键逐段推进；
- 提供“跳过”按钮；
- 完成或跳过后将 `introCompleted` 写为 `true` 并进入地图；
- 首版不制作视频和复杂时间轴动画，仅使用背景、淡入淡出、轻量音效和文本节奏。

### 5.5 Scene 3：2D RPG 地图

- 一张室外地图同时可见或可抵达酒馆、公园、城堡、森林入口；
- 玩家使用 WASD 或方向键八方向移动；
- 地图边界、建筑、水体和主要装饰具有碰撞；
- 相机跟随玩家，并限制在地图边界内；
- 地图展示来自 Backend 的 3 个 NPC；
- 鼠标点击 NPC 打开现有 NPC 详情；详情中继续提供现有对话入口；
- DOM HUD 保留世界推进、任务、玩家语义地点和错误提示等能力；
- 不要求玩家 Sprite 必须走到 NPC 身边才能点击或对话，以免把表现层移动误变成新的任务规则。

## 6. 本地玩家档案

### 6.1 数据模型

Frontend 定义版本化本地结构：

```ts
type AdventurerClass = 'mage' | 'ranger' | 'cleric'

interface LocalPlayerProfileV1 {
  version: 1
  displayName: string
  adventurerClass: AdventurerClass
  introCompleted: boolean
}
```

localStorage key 固定为 `aleria.player-profile.v1`。

本地档案只影响：

- 玩家 Sprite 和角色卡外观；
- UI 中的职业称谓；
- 当前 NPC 对话请求中的玩家自述上下文。

它不改变 Backend 玩家实体、任务条件、NPC 状态或 World State。

### 6.2 校验与故障处理

- 名称去除首尾空格后长度为 1～16 个字符；
- 允许中文、英文字母、数字、空格、间隔点和连字符；禁止换行及控制字符；
- 职业必须是固定枚举；
- 读取时执行结构和版本校验，不能直接信任 `JSON.parse` 后的对象；
- 档案损坏、字段未知或版本不支持时回到创建页，不让应用崩溃；
- localStorage 不可用时退化为当前会话内存状态，并显示“本次选择无法长期保存”的非阻断提示；
- 显示名称始终以文本方式渲染，不使用 `innerHTML`。

首版不保存 Phaser 像素坐标。刷新后从地图默认出生点开始。

## 7. NPC 对话上下文扩展

### 7.1 API 形态

为了让职业和玩家名称影响 NPC 称谓与对话上下文，同时不修改 Player Schema，现有聊天请求增加可选字段：

```json
{
  "conversation_id": null,
  "message": "你认识我吗？",
  "player_profile": {
    "display_name": "洛恩",
    "adventurer_class": "ranger"
  }
}
```

`player_profile` 整体可选，以保持现有客户端和测试兼容。Backend 使用与 Frontend 相同的长度、字符和职业枚举约束；新增的 `player_profile` 对象拒绝额外字段。现有 `conversation_id` 续聊机制保持不变。

### 7.2 安全与权威边界

- `player_profile` 是“玩家选择的自述信息”，不是 World Fact；
- Prompt 中使用明确标签和结构化映射，例如职业枚举映射为“游侠”，不拼接任意职业文本；
- 显示名通过长度和字符白名单后才进入 Prompt；
- 显示名不得改变系统指令、NPC 事实、任务事实或安全规则；
- 每次请求只在当次 Prompt 构建中使用，不写入数据库，不添加到 NPC memory，不修改玩家或世界实体；
- 请求未携带档案时保持现有 Prompt 行为；
- Mock Provider 与真实 Provider 都获得同一份已校验上下文，保证离线演示一致。

## 8. 地图与 Phaser 设计

### 8.1 Scene 结构

Phaser 内部只使用两个 Scene：

- `BootScene`：加载 tileset、地图 JSON、三套玩家外观、NPC Sprite 和必要音效；
- `TownScene`：创建地图、玩家、NPC、碰撞、相机、输入与点击交互。

Vue 卸载游戏容器时必须调用 `game.destroy(true)` 并清理事件订阅，避免热更新、测试或页面切换产生重复 Canvas 和监听器。

### 8.2 Tilemap 约定

地图使用 Tiled JSON，首版采用 32×32 tile。约定图层：

- `ground`：地面；
- `decor-below`：玩家下方装饰；
- `collision`：带碰撞属性的建筑、边界、水体和障碍；
- `decor-above`：树冠、屋檐等前景遮挡；
- `objects`：出生点、NPC 锚点、地点标签和视觉兴趣点。

`objects` 至少包含：

- `player_spawn`；
- `location:tavern`；
- `location:park`；
- `location:castle`；
- `location:forest`；
- 一个安全的 `location:fallback`。

### 8.3 玩家移动

- Arcade Physics 负责速度、归一化斜向移动和碰撞；
- WASD 与方向键映射到同一动作状态；
- 按职业选择不同 Sprite Sheet 或外观变体；
- 根据方向和移动状态播放 idle/walk 动画；
- 浏览器失焦或 Scene pause 时清零速度，避免卡键；
- Canvas 获得交互后阻止方向键滚动页面，但不影响表单输入和 DOM 面板操作。

### 8.4 Backend NPC 的画面投影

Backend 仍只返回 NPC 的语义 `location_id`。Frontend 的适配层把它映射为 Tiled 对象锚点：

```text
backend location_id → visual anchor → npc sprite target position
```

NPC 初次加载时出现在对应锚点。World tick 后若语义地点变化，Sprite 以短 tween 移动到新锚点；这只是对 Backend 状态变化的视觉表达，不反向写回服务端。

如果收到未知地点：

1. 将 NPC 放到 `location:fallback`；
2. 在开发环境输出可诊断警告；
3. 不阻断其他 NPC 和地图交互。

同一地点的多个 NPC 使用稳定的小幅偏移，避免完全重叠。偏移由 NPC id 决定，不能每次渲染随机变化。

### 8.5 交互桥接

Phaser 与 Vue 之间使用显式、可测试的桥接接口，不让 Phaser 直接访问 Pinia 或调用 HTTP：

```ts
interface TownGameInput {
  profile: LocalPlayerProfileV1
  npcs: NpcVisualProjection[]
}

interface TownGameEvents {
  npcSelected: (npcId: string) => void
  loadFailed: (reason: string) => void
}
```

Vue 收到 `npcSelected` 后调用现有 store 获取详情并打开现有面板。NPC 数据变化通过桥接层更新 Sprite，不重建整个 Phaser Game。

## 9. UI 与视觉方向

视觉目标是“温暖但带轻微失忆悬疑感的像素奇幻小镇”。Scene 0～2 和 DOM HUD 使用同一套颜色、边框、字体层级与按钮样式，避免 Canvas 和网页像两个产品。

地图采用桌面优先布局：

- Canvas 使用 Phaser Scale `FIT` 并保持像素清晰；
- 最小可演示视口以常见笔记本尺寸为准；
- 窄屏时 DOM 面板改为抽屉或底部覆盖层；
- 关键按钮和表单仍由 DOM 提供，以保留可读性和键盘操作；
- 不把长对话文本绘制到 Canvas。

## 10. 素材策略与许可

首版采用 CC0 优先策略。可优先评估 Kenney RPG Base、Kenney UI Pack，以及 OpenGameArt 上明确标注 CC0 的角色与火焰素材。

素材进入仓库前必须逐项记录：

- 原始名称和来源 URL；
- 作者；
- 许可证；
- 是否修改；
- 在项目中的文件路径。

仓库新增 `THIRD_PARTY_ASSETS.md`。不能仅依据参考仓库代码的 MIT 许可证推断其中所有图片都可自由复用。若候选三职业素材存在方向帧不完整或授权不清，优先自行绘制简化变体或换用许可明确的整套素材，而不是在交付前承担来源风险。

## 11. 错误处理

- 本地档案损坏：回到创建页并允许覆盖；
- localStorage 写入失败：保留会话状态并提示；
- Phaser 资源加载失败：展示可读错误和重试按钮，不留下空白 Canvas；
- Backend 初次加载失败：地图仍可显示，但 NPC/HUD 展示现有重试状态；
- 单个 NPC 未知地点：使用 fallback 锚点；
- 点击 NPC 后详情请求失败：沿用现有面板错误状态，不影响玩家继续移动；
- Phaser 初始化异常：销毁已创建实例并将错误交给 Vue 边界展示。

## 12. 测试策略

### 12.1 Frontend 单元测试

- 本地档案序列化、读取、版本和损坏数据回退；
- 名称边界、非法字符和职业枚举校验；
- `boot/create/story/town` 流程分支；
- `location_id` 到视觉锚点的适配与 fallback；
- 同地点 NPC 稳定偏移；
- Phaser/Vue 事件桥接和销毁清理；
- 聊天请求正确携带或省略 `player_profile`；
- 现有 Pinia 和组件测试保持通过。

Phaser 的纯计算逻辑放在无 Canvas 依赖的模块中测试。真正的 Scene 生命周期只做少量集成测试，避免把大量单元测试绑定到 WebGL/jsdom 限制。

### 12.2 Backend 测试

- 可选 `player_profile` 的合法和非法请求；
- `player_profile` 内多余字段、超长名称、换行和未知职业被拒绝；
- Prompt context 正确包含已校验的名称、中文职业称谓和“玩家自述”边界；
- 不携带档案时保持原有输出与兼容性；
- 对话请求不会写入 Player、NPC、Quest 或 World State；
- Mock 与真实 Provider 路径共享相同上下文组装。

### 12.3 人工验收

- 首次访问可创建三种职业中的任意一种；
- 刷新后名称和职业保留；
- 剧情可逐段播放和跳过；
- WASD 与方向键均能移动，斜向速度正常，不能穿过主要障碍；
- 四个地点在一张地图上清晰可识别；
- 能看到 3 个 Backend NPC，world tick 后其画面位置按语义地点更新；
- 点击任一 NPC 可查看状态并发起对话；
- NPC 能以安全、有限的方式使用玩家名称和职业称谓；
- 原有世界推进、语义地点移动和失踪孩子任务闭环仍可完成；
- 刷新不会产生重复 Canvas 或事件监听器。

## 13. 预计代码影响范围

实现阶段预计：

- 新增 Frontend 本地档案 store/service、流程场景组件和共享视觉样式；
- 新增 `frontend/src/game/`，包含 Phaser 配置、Scene、地图适配和事件桥；
- 修改应用入口和 `TownView`，将 Phaser 地图与现有 DOM 面板组合；
- 扩展 Frontend chat request 类型；
- 扩展 Backend chat request schema 与 Prompt context builder，但不修改 ORM Player Schema；
- 新增 Tilemap、角色/NPC/UI 素材和许可清单；
- 补充 Frontend、Backend 测试和 Story Bible 中的失忆后职业说明。

## 14. 主要风险与控制

| 风险 | 影响 | 控制措施 |
| --- | --- | --- |
| 把像素位置与语义地点混为一谈 | 任务状态错乱、需要新 API | 明确双层状态；WASD 不触发 Backend travel |
| Canvas 重写全部 UI | 工期膨胀、可测试性下降 | Phaser 只管地图，复杂 UI 保留 DOM |
| 职业演变成玩法系统 | 超出面试作业范围 | 职业只影响外观、称谓和 Prompt 上下文 |
| 本地名称形成 Prompt 注入 | NPC 偏离事实或指令 | 白名单、限长、枚举映射、结构化不可信上下文 |
| Phaser 与 Vue 生命周期泄漏 | 重复 Canvas、重复事件 | 单一实例、显式 destroy、订阅清理测试 |
| Phaser 4 生态变化 | API 与示例不稳定 | 固定 Phaser 3.90.0 |
| 素材许可或动画帧不完整 | 无法安全交付或表现粗糙 | CC0 优先、逐项许可清单、导入前验帧 |
| 地图制作消耗过多时间 | 核心交互延期 | 单地图、固定图层约定、先做灰盒再换美术 |

## 15. 验收边界

Phase 2 MVP 在以下条件全部满足时完成：

1. 四个场景可按设计连贯进入；
2. 名称与职业在 localStorage 中版本化保存，Backend 无 Player Schema 变更；
3. 单张室外地图包含四个指定地点；
4. 玩家可用 WASD/方向键移动并发生合理碰撞；
5. 三个 NPC 来自 Backend World State，并可点击查看或对话；
6. 名称和职业安全地进入当次 NPC 对话上下文，但不持久化到 Backend；
7. 不新增像素坐标或 travel API；
8. 原有 Backend 权威、世界推进和任务闭环通过回归测试；
9. 未引入战斗、背包、技能、装备或多地图系统；
10. 所有第三方素材具有可追溯许可证记录。
