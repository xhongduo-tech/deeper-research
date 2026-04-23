# 深研 AI · 产品与工程设计总纲（v2.0）

> 这份文档是后续所有前后端改造的**唯一北极星**。任何新增/修改界面、接口、数据结构前，先来这里对齐；如果决定偏离，先改这份文档。
>
> v2 关键变化（v1 过时）：
> 1. 交互模型从"订单式生产"改为**Supervisor 协作式生产**——用户和 Supervisor 持续对话，Supervisor 动态组队、追问、同步
> 2. 部署环境锁定为**银行内网离线**，无互联网/无知识库，所有信息源=用户上传材料
> 3. 系统是**API-first** 产品，Web UI 只是 API 的一个官方消费者；任何 UI 能做的事，API 也能做

---

## 0 · 产品定位（一句话）

> **深研 AI 是一个在行内离线环境下的「报告生产主管」系统**：用户提交一份「我要什么报告 + 相关材料」的委托，Supervisor 主管与用户协作对话、动态组建数字员工团队、基于上传材料生产出一份可交付的专业报告。同一份能力对外既提供 Web UI，也提供 REST API。

### 三个"不是"

1. **不是问答系统**：不是聊天气泡流，不是"继续问"的心智。每次交互都围绕一份具体的报告推进。
2. **不是联网研究系统**：不允许联网搜索，不依赖外部知识库。所有证据必须来自用户在本次或本报告中提交的材料。
3. **不是画布式工作流系统**：用户不画 DAG、不手工编排。Supervisor 决定工作流，用户只看结果和关键决策点。

### 三个"是"

1. **是 Supervisor-led 的报告工厂**：有一个看得见的"项目主管" Supervisor 负责全程，用户和 Supervisor 对话，Supervisor 和员工干活。
2. **是基于材料的结构化生产**：一切从用户上传的材料出发，严格以材料为证据，不编造外部信息。
3. **是 API 和 UI 等价的系统**：UI 能触发的任何生产动作，都可以通过 REST API 完成；API 返回的是结构化报告对象，能在用户自己的系统里进一步使用。

---

## 1 · 核心交互模型：Supervisor 协作式生产

这是整个产品最需要"专业统筹"的地方。下面定义清楚后，所有 UI/API 都围绕这个模型展开。

### 角色定义

- **用户 User**：业务人员，提出"我要这份报告"的人
- **Supervisor 主管**：一个特殊的高权限 Agent，负责：
  - 理解用户意图、转写为明确的报告目标
  - 基于材料初判可行性（材料够不够？缺什么？）
  - 选择并派遣员工、动态增减团队
  - 向用户追问关键缺失（不是一次性问死，是按需问）
  - 汇总员工产出，做最后的报告拼装和质检
  - 接受用户反馈，决定局部重做或全报告重生产
- **Employee 员工**：执行具体工序的 Agent（材料解析、数据整理、写作、合规校对、排版…）
- **User ↔ Supervisor**：对话关系
- **Supervisor ↔ Employees**：调度+汇报关系
- **User ↔ Employees**：**用户不直接和员工对话**，但用户看得到 Supervisor 派了谁、为什么派、他在做什么

### 生产生命周期

一份报告从创建到交付分 5 个 phase，Supervisor 在每个 phase 决定推进或追问：

```
1. intake    用户提交委托 + 初始材料；Supervisor 第一次发话
2. scoping   Supervisor 和用户对齐范围（报告类型、深度、结构）
               └─ 可能追问 1-N 轮（不设上限，但每轮必带建议默认答案）
3. producing 组建团队，员工并行/串行干活，Supervisor 监理
               └─ 生产中发现问题 Supervisor 可随时 pause 向用户追问
               └─ Supervisor 可动态增减员工
4. review    初稿完成，Supervisor 呈报用户预览
5. refine    用户反馈；Supervisor 派员工局部重做或整体重写
           （3/5 可多次循环，直到用户 accept；accept 后进入 delivered）
delivered    终态，报告归档
```

任何 phase 用户都可以**取消**；任何 phase Supervisor 都可以**追问**；任何 phase 系统都支持 **API 轮询/订阅**状态。

---

## 2 · 部署与使用边界（硬约束）

### 环境假设

- **离线内网**：无 Google / Bing / Serper / 任何外网 API
- **零知识库**：系统初始不带任何知识库；每份报告的信息源 = 该报告上传的材料
- **LLM 接入**：通过行内接入的大模型（可能是行内自部署或授权），仅通过配置里的 `llm_base_url` 访问
- **文件存储**：本地磁盘（`./uploads`、`./data`），不连对象存储
- **数据库**：SQLite（现状）或 PostgreSQL（生产环境，当前 docker-compose 已预留）

### 因此而来的设计约束

| 约束 | 产品层体现 |
|---|---|
| 没有联网搜索 | 移除"研究员工"中所有联网调研叙事；员工的 description 改为"基于您提供的材料做 X"；明确不生造外部事实 |
| 没有知识库 | 报告模板在**系统内置**（代码层静态数据），不是从知识库检索 |
| 材料是第一公民 | 上传体验必须很好；每个证据引用可以点回原文件原位置 |
| API 是一等公民 | 所有功能都由 REST API 提供；UI 是 API 的 thin client |
| 多租户未来 | 现在不做，但 Report、Employee、API Key 都带 `owner_user_id`，为日后多租户留口 |

---

## 3 · 先做的 5 类报告（Report Types）

| 代号 | 名字 | 典型输入 | 典型交付 | 核心员工团队 |
|---|---|---|---|---|
| `ops_review` | 经营分析报告 | 部门/分行经营数据 Excel、历史报告、业务口径说明 | 月/季度经营分析 Word（含图表） | 材料解析 + 数据整理 + 图表绘制 + 结构化写作 + 质检 + 排版 |
| `internal_research` | 内部专题研究报告 | 专题相关的内部材料、政策文件、制度文本 | 专题研究 Word 或 PPT | 材料解析 + 结构化写作 + 合规校对 + 排版 |
| `risk_assessment` | 风险评估报告 | 客户/项目材料、风险数据、历史案例 | 风险评估 Word（含评级、缓释建议） | 材料解析 + 风险分析 + 结构化写作 + 合规校对 + 排版 |
| `regulatory_filing` | 合规监管报送材料 | 监管模板、行内原始数据、历史报送 | 按指定模板填充完成的文档 | 材料解析 + 模板填充 + 合规校对 + 排版 |
| `training_material` | 内部培训/学习材料 | 制度文件、产品说明、操作手册 | 培训 Word / PPT | 材料解析 + 结构化写作 + 排版 |

**每种报告的结构**是**系统内置**的（代码常量），用户选了类型就拿到结构骨架，Supervisor 基于结构派工。

### 3.1 支持的输入文件格式

行内实际流通的格式，材料解析员 Remy 必须都能吃：

| 格式 | 扩展名 | 解析策略 |
|---|---|---|
| Word | `.docx .doc` | python-docx；`.doc` 走 libreoffice 转 `.docx` |
| Excel | `.xlsx .xls` | openpyxl / xlrd |
| PDF | `.pdf` | pdfplumber + PyMuPDF；扫描件走 OCR |
| PowerPoint | `.pptx .ppt` | python-pptx；`.ppt` 走 libreoffice 转 `.pptx` |
| **WPS 专属** | `.wps .et .dps` | libreoffice 统一转换为对应 OOXML 格式 |
| 纯文本 | `.txt .md .csv` | 直接读取 |
| 图片（截图/扫描件） | `.png .jpg .jpeg .tiff` | OCR（离线引擎，如 PaddleOCR） |

**硬约束**：libreoffice 和 OCR 引擎都必须是**行内可离线部署**的组件。Dockerfile 中需预装。

---

## 4 · 员工编制表（Roster v2）

**设计原则**：
- 人数少而精，每人职责边界清晰，避免两个员工能力大量重叠
- 全部离线可工作（不依赖联网）
- 每个员工都有完整的身份牌字段 (`first_name_en / role_title_en / tagline_en`)
- 英文名取自稳定人名库，给人"团队成员"的感觉而不是"功能模块"

### 10 名核心员工

| # | id | first_name_en | role_title_en | tagline_en | 中文角色 | 适用报告 |
|---|---|---|---|---|---|---|
| 01 | `intake_officer` | **Elin** | Intake Officer | Distill your intent into a plan | 需求接待员 | 全部 |
| 02 | `material_analyst` | **Remy** | Material Analyst | Read every page you gave me | 材料解析员 | 全部 |
| 03 | `data_wrangler` | **Quinn** | Data Wrangler | Turn messy tables into clean signals | 数据整理员 | ops_review / risk_assessment |
| 04 | `chart_maker` | **Iris** | Chart Maker | Make the numbers speak | 图表绘制员 | ops_review / internal_research |
| 05 | `risk_auditor` | **Adler** | Risk Auditor | Weigh exposure against safeguards | 风险分析员 | risk_assessment |
| 06 | `structured_writer` | **Li Bai** | Structured Writer | Compose sections that hold together | 结构化写作员 | 全部 |
| 07 | `template_filler` | **Nash** | Template Filler | Fill the form exactly as required | 模板填充员 | regulatory_filing |
| 08 | `compliance_checker` | **Orin** | Compliance Checker | Catch what the regulator would catch | 合规校对员 | risk_assessment / regulatory_filing / internal_research |
| 09 | `qa_reviewer` | **Sage** | QA Reviewer | Stress-test every claim | 质检员 | 全部 |
| 10 | `layout_designer` | **Milo** | Layout Designer | Hand off a polished deliverable | 排版交付员 | 全部 |

此外还有一个**特殊 Agent**，不在"员工"名单里但在 UI 可见：

| id | first_name_en | role_title_en | tagline_en | 中文角色 |
|---|---|---|---|---|
| `supervisor` | **Chief** | Production Supervisor | Run the project, not the task | 项目主管 |

Supervisor 有独立的身份牌样式（用**金色调** vs 员工的黑白调）以区分它的"主管"身份。

### 员工数据契约（每人必填）

```python
class Employee:
    # 身份
    id: str                     # 唯一 key，如 "material_analyst"
    name: str                   # 中文名（含角色）："Remy · 材料解析员"
    first_name_en: str          # 身份牌顶部黑牌："Remy"
    role_title_en: str          # 大号标题："Material Analyst"
    tagline_en: str             # 一句英文职责："Read every page you gave me"
    portrait_seed: str          # 像素头像 seed，= id

    # 定位
    category: str               # intake/material/data/chart/risk/writing/template/compliance/qa/layout
    description: str            # 完整中文描述（展开身份牌时显示）

    # 能力
    skills: list[str]           # ["pdf_parse", "excel_parse", "table_extract"]
    tools: list[str]            # 后端工具白名单
    default_model: str          # 默认 LLM

    # 适用范围
    applicable_report_types: list[str]   # ["ops_review", "risk_assessment", ...]

    # 输入/输出契约（Supervisor 靠这个派工）
    inputs: list[str]           # 本员工期望的输入类型
    outputs: list[str]          # 本员工产出物类型

    enabled: bool
```

### 迁移计划

- 写一个 `backend/scripts/seed_employees_v2.py`，**原子替换**现有员工表（清空 + 按上表种子）
- 老任务的 `assigned_employees` 通过 id 映射表迁移（尽量对得上），对不上的记为 `legacy`

---

## 5 · 视觉与产品性格

参考锚点：**Vercel Dashboard** + **Linear** 的工程克制感，融合 **Kimi Agent Swarm** 的身份牌质感。

### 性格关键词

- **克制 Restrained**：大量留白，低饱和，一个强调色
- **工程感 Engineered**：等宽字体 tag、数字、状态代号；表格/列表信息密度高
- **专业 Professional**：排版有层级，数据可读性 > 好看
- **安静但有活力 Quiet Kinetic**：静态安静，运行态有克制的脉冲和进度

### 色彩系统

```
/* 中性轴 —— Vercel 风格黑白灰阶 */
canvas         #fafaf9    白天主底
canvas-dark    #0a0a0a    夜间主底（Phase 6）
surface-1      #ffffff    最上层
surface-2      #f5f4f0    次级面板（浅米）
surface-3      #ececea    再下一档
line           #e5e4e0    常规边框
line-strong    #c8c5bd    强边框
ink-1          #141414    主文
ink-2          #4a4a46    次要文
ink-3          #8a877e    辅助文
ink-4          #bcb8ac    占位/最弱

/* 品牌强调色（仅 1 个） */
brand          #8c4f3a    深研褐（主 CTA / 进度 / 选中）
brand-ring     rgba(140,79,58,0.18)

/* 语义色（仅 4 个） */
success        #22c55e    运行中/完成
warning        #d97706    需用户确认
danger         #dc2626    失败/错误
supervisor     #c08a3a    主管专属金（只有 Supervisor 身份牌和 Supervisor 对话气泡用）
```

规则：**任意页面强调色 + 语义色同时出现不超过 2 种**。

### 字体阶梯

```
display   28/34  -0.02em  semibold
h1        22/28  -0.015em semibold
h2        18/24  -0.01em  semibold
h3        15/22            semibold
body      14/22            regular
small     13/20            regular
caption   11/16  +0.02em   medium
mono      13/20            regular  (JetBrains Mono / SF Mono)
```

### 圆角/阴影

- 圆角：`sm 6 / md 10 / lg 14 / xl 20`
- 阴影：`card = 0 1px 2px rgba(0,0,0,0.04), 0 8px 24px -12px rgba(0,0,0,0.1)`

### 动效规范（重要）

系统整体性格是"安静但有活力"，动效必须**克制、统一、可预测**。反例是弹跳/抖动/大位移/多段曲线。

| 场景 | 动效 |
|---|---|
| 默认进场（卡片/面板显现） | `180ms cubic-bezier(0.2, 0, 0, 1)`，位移 4-8px，opacity 0→1 |
| 默认退场 | `120ms cubic-bezier(0.4, 0, 1, 1)`，opacity 1→0，不位移 |
| Hover 抬起 | `translateY(-1px)`，`120ms` |
| 按钮点击反馈 | `scale(0.97)`，`100ms` |
| **Supervisor 消息流入**（核心） | 新消息从下方 8px 进入，`220ms cubic-bezier(0.2, 0, 0, 1)`，伴随**一次**柔和背景闪现（brand-ring 0→0.18→0，总时长 600ms）告知这是新消息 |
| **Supervisor 追问** | 追问气泡进入时，外侧额外有一圈 pulseRing（`2.4s ease-in-out infinite`，最多脉冲 3 次后停）提醒用户需响应 |
| **Team change（员工加入）** | 员工身份牌缩略从左滑入 12px，`260ms`，层叠时每张延迟 60ms |
| **Phase 切换** | phase 指示器当前点填充，`400ms`，同时底部产出区的对应阶段骨架呼吸一次 |
| **进度环** | 进度数字用 `easeOutQuad` 插值过渡 `400ms`，环形填充同步 |
| **章节增量亮起**（右栏预览） | 新章节从骨架态"显影"到实体态，`320ms opacity + 4px translateY` |
| **Chief 思考中** | Chief 头像旁一个 3 点流星（ThinkingDots 复用），不在卡片本体做 loading |
| **加载骨架** | 统一 `shimmer 1.4s linear infinite`，透明度在 0.4-0.7 之间摆动 |

**禁用**：
- 弹簧曲线（spring）除非必须（身份牌选中状态可用），否则一律用 cubic-bezier
- 同时超过 2 个元素在做进场动画（会让页面显得焦虑）
- 任何超过 400ms 的常规动效（进度/骨架等持续性动效除外）

**全局 reduce-motion**：尊重系统 `prefers-reduced-motion: reduce`，自动降级到纯 opacity 过渡、无位移。

---

## 6 · 信息架构

```
┌─ 首页 /
│   "启动一份报告" + 我的报告列表
│
├─ 报告 /reports/:id
│   Supervisor 协作室 + 产出预览（双栏）
│
├─ 档案 /archive
│   历史报告检索
│
├─ 员工厅 /workforce
│   身份牌墙（展示性，用户不能选）
│
├─ 开发者 /developer
│   API Key 管理、API 文档入口、使用示例
│
└─ 管理员 /admin/*
    /admin/workforce  员工配置（模型/工具/开关）
    /admin/system     系统设置
    /admin/monitor    所有任务/所有用户监控
```

**关键决策**
- 员工厅次级导航 + 展示性：解决"不让用户自己选员工"
- `/developer`：API 不是技术文档里躲着的二等公民，它是产品的一级入口
- 报告详情是双栏：左 Supervisor 协作室，右 产出预览

---

## 7 · 首页设计

### 布局（核心）

```
┌────────────────────────────────────────────────────────────────┐
│  左导航极简                                                     │
│                                                                 │
│  ▌ 欢迎行（一句）                                                │
│     晚上好，徐红铎。                                             │
│                                                                 │
│  ▌ Compose Zone（不是聊天框，是"委托 Supervisor 启动一份报告"）  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  把任务交给 Chief 主管                                     │ │
│  │  [Chief 身份牌缩略 + 一句问候: "今天我们做哪份报告？"]      │ │
│  │                                                           │ │
│  │  ┌───────────────────────────────────────────────────┐   │ │
│  │  │ 简述你要的报告（例：基于附件材料做 Q4 经营分析）  │   │ │
│  │  │                                                   │   │ │
│  │  └───────────────────────────────────────────────────┘   │ │
│  │                                                           │ │
│  │  [📎 附件 (0)]  [报告类型 · 自动判断 ⌄]                    │ │
│  │                                                           │ │
│  │                              [ 委托 Chief 启动 → ]         │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ▌ Templates（5 类报告的卡片，点选 = 预填类型 + 显示所需材料）   │
│     [经营分析] [专题研究] [风险评估] [合规报送] [培训材料]       │
│                                                                 │
│  ▌ My Reports（最近 6 份）                                      │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 为什么这不是聊天框

| 聊天框（ChatGPT 类） | 深研 AI Compose Zone |
|---|---|
| 底部固定输入条，历史气泡向上堆 | 页面中央的"委托表单" |
| Placeholder: "Ask anything" | Placeholder: "例：基于附件材料做 Q4 经营分析" |
| 发送即 append 气泡 | 提交即**跳转 `/reports/:id`**，启动一次生产 |
| 无明确结构 | 明确 3 要素：**描述 / 类型 / 材料** |
| 对话是永续的 | 每次委托都是一次独立的"生产项目" |

关键视觉标志：**Chief 的身份牌缩略卡贴在输入框左上角**，配一句问候。让用户第一眼知道"这是委托给一个 Supervisor"，不是"和一个大模型聊天"。

---

## 8 · 报告详情页 `/reports/:id`（核心页）

### 双栏布局

```
┌─────────────────────────────────────────────────────────────────────┐
│ ← 返回   │ Q4 经营分析报告              [状态: 生产中 63%]  [···]   │
├─────────────────────────────────────────────────────────────────────┤
│ ▌ 左 · Supervisor 协作室                ▌ 右 · 产出预览              │
│                                                                     │
│ ┌───────────────────────────────┐      ┌──────────────────────────┐ │
│ │ [Chief 身份牌缩略]             │      │                          │ │
│ │                                │      │   报告预览区             │ │
│ │ Chief · 15:02                  │      │   - 生产态：骨架+已完成  │ │
│ │ 已收到您的 4 份材料。我把这份 │      │     章节滚动更新         │ │
│ │ 拆成 6 个阶段，预计 18 分钟。 │      │   - 交付态：完整 Word    │ │
│ │ 第一步会先把材料解析完。       │      │     预览 + 下载          │ │
│ │ [ 了解 ][ 修改范围 ]           │      │                          │ │
│ │                                │      │   证据 / 讨论 / 历史 tab │ │
│ │ ─── 团队变更 ─────────────     │      │                          │ │
│ │ [Remy 身份牌] 加入：材料解析   │      └──────────────────────────┘ │
│ │ [Quinn 身份牌] 加入：数据整理  │                                   │
│ │                                │                                   │
│ │ Remy · 15:04                   │                                   │
│ │ 材料解析完成。4 份中 1 份为扫 │                                   │
│ │ 描件，已 OCR。                 │                                   │
│ │                                │                                   │
│ │ ─── Chief 追问 ───────────     │                                   │
│ │ Chief · 15:06                  │                                   │
│ │ 扫描件里 "H 分行 Q3 台账" 最后 │                                   │
│ │ 两页模糊，是否以我 OCR 结果继 │                                   │
│ │ 续，还是您现在补传清晰版？     │                                   │
│ │ [ 继续使用 OCR ][ 我补传 ]     │                                   │
│ │                                │                                   │
│ │ ▼ 进度总览                     │                                   │
│ │ ●────●────○────○────○────○   │                                   │
│ │ intake scope produce review... │                                   │
│ └───────────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 左栏"Supervisor 协作室"规范

这是**唯一和聊天最像**的地方，但它不是 ChatGPT 式的气泡流。关键设计：

- **消息类型是结构化的**，不是纯文本（共 7 种）：
  - `supervisor_say`：Chief 的发言（带 Chief 身份牌头像，金色调）
  - `supervisor_ask`：Chief 向用户追问（必须带按钮式选项 + 默认推荐；外侧 pulseRing 提醒）
  - `team_change`：团队增减（展示员工身份牌缩略 + 加入/完成标记，从左滑入）
  - `employee_note`：员工关键汇报（只挑 Supervisor 认为用户该看的）
  - `user_reply`：用户回复（右对齐，简洁）
  - `user_interject`：**用户主动插话**（用户不等追问自己发话，比如"改下方向"、"强调一下 XX"；视觉与 `user_reply` 区分：左侧有一个细细的橙色竖条表示打断）
  - `phase_transition`：phase 切换（横条分隔，当前 phase 名称高亮）
- **员工级别的详细日志折叠**：默认不显示，点 `▼ 详细日志 (47)` 展开
- **所有追问都必须提供默认/推荐选项**：小白用户一路点推荐就能走完
- **用户主动插话入口**：协作室底部常驻一个克制的输入条（非大输入框，是一行），占位文字 "想对 Chief 说点什么？"；只在 `producing / review` 阶段可用

### 右栏"产出预览"

- 生产态：展示**骨架大纲 + 已完成章节**，章节一旦完成就亮起
- 交付态：完整 Word/PDF 原样预览（不是 Markdown 裸渲染）
- 三个 Tab：`预览 / 证据 / 讨论`
  - 证据：按段落列出引用的文件+页码
  - 讨论：用户对任意段落发出的修改请求（进入 refine 循环）

### phase 指示器

底部横贯的 5 点 phase 指示器 `intake → scoping → producing → review → delivered`，当前 phase 高亮、已完成变 filled。

---

## 9 · 员工厅 `/workforce` & 档案 `/archive` & 开发者 `/developer`

### `/workforce`
- 身份牌墙，按 category 分组（需求接待 / 材料处理 / 数据处理 / 写作 / 合规 / 交付…）
- 顶部说明："这是深研 AI 背后的 10 名数字员工。您无需挑选，Chief 主管会根据报告自动组队。"
- 只读，不能选、不能编辑

### `/archive`
- 历史报告表格：标题 / 类型 / 状态 / 创建人 / 交付时间 / 操作
- 搜索：按标题/类型/时间
- 列：点进去 = 回到 `/reports/:id` 的交付态

### `/developer`
- **API Key 管理**：用户**自助申请**——填名字+用途，系统**自动审批通过**（v1 策略），密钥仅在创建时展示一次
- **管理员可见**：管理员在 `/admin/api-keys` 能看到全部 Key、调用量、封禁、强制撤销
- **默认策略**：
  - 每用户最多 5 个活跃 Key
  - 每个 Key 默认配额：1000 calls/day（可由管理员调整）
  - 创建/使用/撤销全部写审计日志
- **API 文档入口**：指向 `/docs`（FastAPI 自带 Swagger）+ 一份我们手写的"快速上手"
- **调用示例**：Python / curl / 行内常用的语言
- **Webhook 配置**（Phase 7，先预留）

---

## 10 · 后端架构：API-first

### 10.1 架构分层

```
┌─────────────────────────────────────────────┐
│ Interfaces                                  │
│   - Web UI (React + Vite)                   │
│   - REST API (FastAPI, 公开)                 │
│   - API Key 鉴权                             │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────┴──────────────────────────┐
│ Application Layer                           │
│   - ReportService  (创建/查询/取消/refine)   │
│   - SupervisorService (协作对话/决策)         │
│   - EmployeeService (派工/汇报)              │
│   - EventBus (SSE/WebSocket 事件广播)        │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────┴──────────────────────────┐
│ Domain                                      │
│   - Report, Clarification, TimelineEvent    │
│   - Employee, Supervisor                    │
│   - Evidence, Message                       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────┴──────────────────────────┐
│ Infra                                       │
│   - SQLite/PG, Files, LLM Gateway           │
└─────────────────────────────────────────────┘
```

关键原则：
- Web UI 的每个动作都对应一个 REST API；没有 UI 专属接口
- Supervisor 和 Employee 不直接调 LLM，经过一个 `LLMGateway`，未来好换模型/加审计
- 所有"事件"写入 `TimelineEvent` 表，是状态真相；SSE/WebSocket 只是推送通道

### 10.2 数据模型（核心）

```python
class Report:
    id: int
    owner_user_id: int
    title: str
    description: str              # 用户原始意图
    report_type: str              # ops_review / internal_research / risk_assessment / regulatory_filing / training_material
    depth: str                    # quick / standard / deep
    phase: ReportPhase            # intake / scoping / producing / review / delivered / cancelled
    progress: float               # 0-1
    eta_seconds: int | None
    assigned_employees: list[str] # 动态
    source: str                   # "web" | "api"
    created_at, updated_at: datetime

class Message:
    id: int
    report_id: int
    type: str          # supervisor_say / supervisor_ask / team_change / employee_note
                       # user_reply / user_interject / phase_transition
    actor_id: str      # "user:123" | "supervisor" | "employee:material_analyst"
    payload: dict      # 结构化内容（见 §8 左栏消息类型）
    created_at: datetime

class Clarification:
    id: int
    report_id: int
    question: str
    options: list[str]        # 可选；无选项则自由文本
    default: str | None       # 推荐默认答案
    answer: str | None
    resolved_at: datetime | None

class TimelineEvent:       # 细粒度操作日志（不一定展示给用户）
    id: int
    report_id: int
    phase: str
    employee_id: str | None
    action: str
    detail: dict
    status: str              # started / completed / failed
    created_at: datetime

class Evidence:
    id: int
    report_id: int
    section_id: str
    source_file_id: int
    locator: dict            # {"page": 3, "box": [...]}
    snippet: str
```

### 10.3 REST API（正式契约）

所有路径前缀 `/api/v1`。鉴权：Web 用 session cookie，API 用 `Authorization: Bearer <api_key>`。

```
# 报告
POST   /reports                         创建报告（body: title?, description, report_type?, depth?, file_ids[]）
GET    /reports                         列表，支持分页+过滤
GET    /reports/{id}                    完整对象
POST   /reports/{id}/cancel             取消
POST   /reports/{id}/refine             body: {section_id?, instruction}
GET    /reports/{id}/events  (SSE)      实时事件流（供 UI 和 API 订阅）

# Supervisor 协作
GET    /reports/{id}/messages           分页消息列表
POST   /reports/{id}/reply              用户回复一条追问
POST   /reports/{id}/interject          用户主动插话（未被追问时主动发话）
POST   /reports/{id}/clarifications/{cid}   回答一个澄清（或 action=use_default）

# 文件
POST   /files                           上传（multipart）
GET    /files/{id}                      下载

# 资源字典（UI 和 API 都用）
GET    /report-types                    5 种报告类型 + 结构骨架
GET    /workforce                       员工列表（展示用）
GET    /workforce/{id}                  单个员工详情

# 管理员
GET    /admin/reports                   所有报告
GET    /admin/users                     用户
POST   /admin/workforce/{id}            更新员工配置
GET    /admin/system                    系统配置
PUT    /admin/system                    更新

# 开发者（用户自助）
GET    /developer/api-keys              我的 key 列表
POST   /developer/api-keys              申请 key（body: name, purpose）→ 自动审批通过，响应中一次性返回明文
DELETE /developer/api-keys/{id}         撤销
GET    /developer/api-keys/{id}/usage   查看使用量/最近调用

# 管理员额外
GET    /admin/api-keys                  所有 key
POST   /admin/api-keys/{id}/suspend     管理员封禁某 key
POST   /admin/api-keys/{id}/quota       调整配额
```

### 10.4 Supervisor 决策逻辑（伪代码）

```python
class SupervisorService:
    async def on_report_created(report):
        # Phase: intake → scoping
        plan = await self.llm.plan(report.description, report.files, report.report_type)
        if plan.needs_clarification:
            for q in plan.clarifications[:3]:   # 每轮最多 3 个
                await self.emit_supervisor_ask(report, q)
            await self.set_phase(report, "scoping")
        else:
            await self.start_producing(report, plan)

    async def on_user_reply(report, reply):
        updated_plan = await self.llm.update_plan(report, reply)
        if updated_plan.needs_more_clarification:
            await self.emit_supervisor_ask(...)
        else:
            await self.start_producing(report, updated_plan)

    async def start_producing(report, plan):
        await self.set_phase(report, "producing")
        for step in plan.steps:
            employees = self.pick_employees(step)           # 从 Roster 按 category + skills 选
            await self.emit_team_change(report, employees, "joined")
            results = await self.run_step(step, employees)
            if results.needs_user_input:
                await self.pause_and_ask(report, results.question)
                return
        await self.assemble_report(report)
        await self.set_phase(report, "review")
```

---

## 11 · 安全与隔离

- **API Key**：哈希存储，只在创建时向用户展示一次
- **文件隔离**：每个 `owner_user_id` 只能访问自己的文件；Supervisor 和 Employee 处理文件时通过 ACL 层
- **LLM 调用审计**：每次 LLM 调用记录 `report_id / employee_id / prompt_hash / tokens / latency`，供管理员查
- **离线强保证**：员工的 `tools` 白名单里不允许出现 `web_search` 之类的外网工具；通过 CI 测试确保

---

## 12 · 分阶段实施计划

### Phase 0 · 基础（0.5 天）

- [x] DESIGN.md 写完
- [ ] 建 `frontend/src/design-system/` : tokens, Button, Input, Select, Dialog, Tabs, Badge, ProgressRing, Skeleton
- [ ] 扩展 Tailwind 色彩映射到 §5 tokens

### Phase 1 · 后端骨架（1.5 天）

- [ ] 数据模型：`Report / Message / Clarification / TimelineEvent / Evidence / ApiKey` 建表与迁移
- [ ] `Employee` 扩展 `first_name_en / role_title_en / tagline_en / portrait_seed / applicable_report_types / inputs / outputs`
- [ ] 员工 seed 脚本：10 名员工 + 1 个 Supervisor（按 §4）
- [ ] REST API 全套 `/api/v1/*`（见 §10.3），先用假数据/Mock 通
- [ ] API Key 鉴权中间件
- [ ] SSE `/reports/{id}/events` 实现

### Phase 2 · Supervisor 服务（1 天）

- [ ] `SupervisorService` 实现 §10.4 决策流
- [ ] `EmployeeRunner` 抽象：按 employee_id 派工、注入材料、收集产出
- [ ] 5 种报告类型的内置结构骨架
- [ ] 消息/澄清/团队变更事件真实发射

### Phase 3 · 首页（0.5 天）

- [ ] 新 HomePage: Compose Zone + Chief 身份牌缩略 + Templates + My Reports
- [ ] 移除旧版首页
- [ ] 路由 `/` 指向新首页

### Phase 4 · 报告详情页（2 天）⭐ 核心

- [ ] 双栏布局 `/reports/:id`
- [ ] 左栏：消息流组件（6 种消息类型各一个 React 组件）+ phase 指示器
- [ ] 左栏：澄清"一键用推荐"
- [ ] 右栏：预览（生产态章节增量亮起 / 交付态完整预览）+ 证据 + 讨论 Tab
- [ ] SSE 订阅消息事件 → 实时渲染
- [ ] 删除旧 TaskPage/WorkflowViewer/ExecutionLog/AgentPanel

### Phase 5 · 员工厅 + 档案 + 开发者（0.5 天）

- [ ] `/workforce` 身份牌墙（展示性）
- [ ] `/archive` 历史报告检索
- [ ] `/developer` API Key + 文档入口 + 示例代码

### Phase 6 · 管理员后台视觉升级（0.5 天）

- [ ] `/admin/workforce / admin/system / admin/monitor` 接入新设计系统

### Phase 7 · 打磨（0.5 天）

- [ ] 空/错/加载状态统一
- [ ] 键盘：`⌘ K` 启动新报告、`⌘ ↵` 在 Compose Zone 提交
- [ ] 暗色模式基线

**总预估：7 天全职工作量**（前后端全面重构，含员工重建）

---

## 13 · 验收标准

### 产品层
- [ ] 用户进首页第一眼知道"这是下单一份报告"，不是聊天
- [ ] 小白用户只输入一句话 + 附件也能走完全流程（类型由 Supervisor 自动判断）
- [ ] 所有 Supervisor 追问都**必带推荐答案**，用户一路点推荐就能完成
- [ ] 用户**永远看不到"选择员工"的界面**，但**看得到** Supervisor 派了谁
- [ ] 同一份报告能通过 API 完整创建、查询、完成

### 工程层
- [ ] UI 所做的每件事都对应一个 `/api/v1/*` 接口
- [ ] 所有员工 `tools` 白名单里没有联网工具
- [ ] 每次 LLM 调用都在 `TimelineEvent` 或独立日志表里有记录
- [ ] API Key 鉴权正确，文件 ACL 不越权

### 视觉层
- [ ] 任意两页截图放一起，视觉语言统一
- [ ] 任意页面强调色+语义色同时出现 ≤ 2 种
- [ ] 身份牌墙和参考图（agent swarm.jpeg / 3 张参考图）风格一致

---

_本文档 v2.0 由设计统筹起草。v1 作废。任何偏离请先 PR 改这份文档。_
