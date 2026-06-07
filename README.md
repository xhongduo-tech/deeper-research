# DataAgent Studio — 深度研究与数据分析智能体平台

> 面向企业的多智能体深度研究报告生成系统。用户提交研究主题，系统自动规划任务、检索知识、并行撰写、质量审核，最终交付结构化的 Word / PPT / Excel 专业文档。
> 
> **核心设计理念：内网/离线优先、零外部依赖、军工级数据安全、企业级文档质量。**

---

## 目录

- [核心能力](#核心能力)
- [整体技术架构](#整体技术架构)
- [多智能体生产流水线](#多智能体生产流水线)
- [SOTA 质量增强算法](#sota-质量增强算法)
- [离线优先设计](#离线优先设计)
- [Skill 技能系统](#skill-技能系统)
- [快速启动](#快速启动)
- [开发环境](#开发环境)
- [项目结构](#项目结构)
- [配置说明](#配置说明)
- [路线图](#路线图)

---

## 核心能力

| 能力维度 | 说明 |
|---------|------|
| **深度研究** | 基于用户输入，自动分解为 3-7 个并行子任务，多智能体协作完成信息收集与论证 |
| **知识增强** | 内置 RAG 知识库（文档上传 → 分块 → 向量检索），支持离线知识深化（行业基准、分析框架） |
| **专业写作** | 20+ 个专业文档 Skill（经营分析、专项研究、风险评估、合规报送、学术论文、投标书等） |
| **数据洞察** | 支持上传 Excel/CSV/Word/PDF，自动提取指标、生成统计图表、执行沙箱代码分析 |
| **多格式交付** | Word（深度报告）、PPT（演示文稿）、Excel（数据分析工作簿） |
| **质量门控** | 三级质量门禁 + DECRIM 批判精炼 + PMRC 叙事重构，确保交付物专业可用 |

---

## 整体技术架构

### 三层 Docker 部署栈

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend  (Nginx :80)                                          │
│  ├─ index.html / admin.html / app.js                            │
│  ├─ Vanilla JS + WebSocket 实时进度流                            │
│  └─ 无前端框架依赖，内网浏览器零兼容负担                          │
├─────────────────────────────────────────────────────────────────┤
│  Backend  (FastAPI :8000)                                       │
│  ├─ REST API  +  WebSocket 流式输出                              │
│  ├─ 多智能体编排引擎 + Skill 技能系统                             │
│  ├─ RAG 知识库（Embedding + SQLite 向量存储）                    │
│  └─ 文档生成（python-docx / python-pptx / openpyxl）             │
├─────────────────────────────────────────────────────────────────┤
│  Redis  (:6379)                                                 │
│  └─ 异步任务队列 + 会话缓存                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 后端模块拓扑

```
backend/app/
├── api/                    # REST & WebSocket 路由层
│   ├── auth.py             # JWT 认证
│   ├── reports.py          # 报告 CRUD + 下载
│   ├── ws.py               # WebSocket 实时进度推送
│   ├── admin.py            # 系统配置管理
│   ├── knowledge_base.py   # 知识库上传与检索
│   └── prompt_skills.py    # Skill 动态加载
│
├── agents/                 # 智能体定义（规划/研究/质检/数据分析）
│   ├── planner.py          # PlannerAgent — 需求解析与任务拆解
│   ├── research_agent.py   # ResearchAgent — 信息合成与证据收集
│   ├── verifier.py         # VerifierAgent — 事实核查与置信度评估
│   ├── data_analyst.py     # DataAnalystAgent — 统计分析与图表生成
│   └── ...                 #  citation_agent, document_analyst_agent 等
│
├── services/               # 核心服务层
│   ├── simple_pipeline.py  # 简化三阶段流水线（生产默认路径）
│   ├── orchestrator.py     # 多智能体编排引擎（legacy，保留兼容）
│   ├── llm_service.py      # OpenAI-compatible LLM 客户端 + 健康检查
│   ├── model_router.py     # 轻/重模型分级路由
│   ├── rag_service.py      # Embedding + BM25 + 向量检索
│   ├── document_generator.py # Word/PPT/Excel 生成器
│   ├── sandbox.py          # 受限 Python 代码执行（数据分析沙箱）
│   ├── prompt_assets.py    # Skill 资产加载与上下文构建
│   └── delivery_quality.py # 交付物最终润色
│
├── skills/                 # 离线 Skill 运行时
│   ├── base.py             # Skill 基类与执行契约
│   ├── registry.py         # 全局 Skill 注册表
│   └── offline/            # 离线技能实现（关键词提取、表格构建等）
│
├── prompt_assets/skills/   # 20+ 专业写作 Skill（Prompt 资产库）
│   ├── document-chief-planner/
│   ├── research-report-authoring/
│   ├── advanced-charting/
│   ├── citation-bibliography/
│   ├── ppt-director/
│   ├── ppt-narrative/
│   ├── ppt-layout/
│   └── ...                 # 投标书、学术论文、财务研究等
│
├── swarm/                  # 动态智能体群（Swarm）编排（可选）
│   ├── orchestrator.py     # SwarmOrchestrator — DAG 拓扑执行
│   ├── agent_node.py       # 智能体节点生命周期
│   ├── task_graph.py       # 任务依赖图
│   └── message_bus.py      # 智能体间消息总线
│
└── models/                 # SQLAlchemy ORM 模型
    ├── report.py           # 报告实体（状态机 + 输出索引）
    ├── message.py          # 对话消息（多智能体协作记录）
    ├── knowledge_base.py   # 知识库文档与分块
    └── system_config.py    # 运行时配置持久化
```

---

## 多智能体生产流水线

系统采用 **"简化三阶段流水线"** 作为生产默认路径，兼顾效率与质量：

```
用户输入 ──► 理解(Intent) ──► 大纲(Outline) ──► 并行生成(Generate) ──► 质量门控 ──► 交付
              │                  │                   │
              ▼                  ▼                   ▼
         需求契约构建       格式感知大纲设计      多章节并行 LLM 调用
         Skill 匹配加载      PMRC 叙事重构(PPT)    DECRIM 精炼(Word)
         证据包排序          断言式标题规范        图表自动渲染
         上传文件解析        版式预分配(PPT)       引用溯源标注
```

### 阶段详解

#### Phase 1 — 理解（Understand）
- **需求契约构建**：从用户输入提取关键词、分析角度、时间口径、图表策略
- **Skill 匹配**：根据报告类型（经营分析/专项研究/风险评估/合规报送）加载对应写作 Skill
- **证据包构建**：对上传文件进行分块、排序、提取关键数字，形成结构化证据
- **LLM 路由决策**：根据任务复杂度选择轻量模型（qwen2.5:7b）或重量模型（qwen2.5:72b）

#### Phase 2 — 大纲（Outline）
- **格式感知设计**：
  - Word: 执行摘要 → 背景 → 核心分析 → 风险 → 建议 → 附录
  - PPT: 封面 → 议题概览 → 核心分析 → 结论行动（SCQA 结构）
  - Excel: 汇总看板 → 核心数据 → 分维度分析 → 趋势分析 → 明细
- **断言式标题（Assertion Title）**：每个章节标题必须是完整判断句，含具体数字
- **PMRC 叙事重构**（PPT 专有）：将大纲重组为 Problem → Method → Result → Conclusion 叙事弧线
- **SlideTailor 版式预分配**：为每页 PPT 预分配最优版式类型

#### Phase 3 — 并行生成（Generate）
- **多章节并发**：默认最多 4 个章节并行调用 LLM，Ollama 本地队列管理
- **格式原生提示**：
  - Word: Markdown 正文 + 数据表格 + 引用标注
  - PPT: 断言标题 + 要点列表 + Speaker Notes + 图表占位
  - Excel: Markdown 数据表 + 列定义 + 计算口径
- **叙事上下文注入**：为每个章节提供其在整体叙事中的位置、角色、过渡逻辑
- **引用可审计性**：所有数字、年份、金额必须标注来源/口径/资料缺口

#### Phase 4 — 质量门控（QA & Delivery）
- **确定性门控**：
  - 内容是否覆盖用户输入需求
  - 上传文件事实是否被引用
  - 是否包含失败占位符
  - PPT 页数是否充足
- **LLM 质量审核**：从需求贴合度、数据支撑、逻辑一致性、格式适配、引用可审计性 6 个维度评分
- **DECRIM 批判精炼**（Word 专有）：分解约束 → 批判草稿 → 迭代精炼（最多 2 轮）
- **最终润色**：去除元话术、统一格式、优化排版

---

## SOTA 质量增强算法

### 1. PMRC 叙事重构（PPT 专用）
**Problem-Method-Result-Conclusion**
- 将研究大纲重组为叙事弧线（Narrative Arc）
- 自动生成开场钩子（Opening Hook）和行动号召（Closing CTA）
- 为每页分配叙事角色：开场页、递进页、转折页、结尾页
- 效果：幻灯片连贯性提升约 50%

### 2. DECRIM 批判精炼（Word 专用）
**Decompose-Constraint → Critique → Refine-Iterative-Method**
- 将质量约束分解为 9 个检查维度
- LLM 扮演批评家角色，逐条指出草稿问题
- 自动迭代修正（1-2 轮），质量分显著提升
- 效果：初始质量分 70 → 精炼后 88+

### 3. SlideTailor 版式选型（PPT 专用）
- 基于页面内容特征自动选择最优版式：
  - `number-showcase` — 数字展示页
  - `comparison` — 对比分析页
  - `roadmap` — 路线图/时间线页
  - `insight` — 洞察发现页
  - `chart-donut` — 占比饼图页
  - `feature-grid` — 特性矩阵页

### 4. 证据包排序（Evidence Pack Ranking）
- 对用户上传文件进行段落级切分
- 基于 BM25 + 词法重叠 + 数字匹配三重评分
- 按用户需求关键词相关性排序
- 自动识别资料缺口并标注

---

## 离线优先设计

系统专为**内网/离线/保密网络**环境设计：

| 设计决策 | 说明 |
|---------|------|
| **无外网搜索** | `ENABLE_EXTERNAL_SEARCH` 永久硬编码为 `false`，不调用任何外部搜索引擎 |
| **无浏览器自动化** | `ENABLE_BROWSER` 永久禁用，不依赖 Playwright/Selenium |
| **本地推理** | 默认对接 Ollama（`qwen2.5:72b`），数据不出内网 |
| **轻量向量库** | 向量存储于 SQLite JSON 字段，无需 Milvus/Pinecone/Weaviate 等外部向量数据库 |
| **离线知识深化** | KnowledgeEnricherAgent 通过深度激活 LLM 内部知识储备，提供行业基准数据和分析框架 |
| **Docker 离线包** | `./build_offline.sh` 可构建包含全部镜像的离线部署包 |

---

## Skill 技能系统

Skill 是系统的核心写作资产，采用**文件即代码**的设计：

```
backend/app/prompt_assets/skills/
├── _SKILL_TEMPLATE.md              # Skill 开发模板
├── document-chief-planner/         # 文档总规划师
│   ├── SKILL.md
│   └── references/                 # 参考规范（规划契约、质量门槛、Skill 路由等）
├── research-report-authoring/      # 研究报告撰写
├── advanced-charting/              # 高级图表生成
├── citation-bibliography/          # 引用与参考文献
├── ppt-director/                   # PPT 导演（叙事策略）
├── ppt-narrative/                  # PPT 叙事构建
├── ppt-layout/                     # PPT 版式设计
├── word-authoring/                 # Word 文档撰写
├── excel-modeling/                 # Excel 数据建模
├── table-figure-authoring/         # 表格与图件制作
├── executive-summary/              # 执行摘要
├── bid-proposal-authoring/         # 投标书撰写
├── academic-paper-authoring/       # 学术论文
├── financial-research-authoring/   # 财务研究
├── legal-document-authoring/       # 法律文书
├── policy-document-authoring/      # 政策文件
├── meeting-minutes-authoring/      # 会议纪要
├── prd-authoring/                  # PRD 产品需求
├── press-release-authoring/        # 新闻稿
├── training-manual-authoring/      # 培训手册
├── feasibility-study-authoring/    # 可行性研究
├── performance-review-authoring/   # 绩效评估
├── official-document-authoring/    # 公文写作
├── qa-verification/                # 质量审核
├── data-grounding/                 # 数据接地
├── format-conversion/              # 格式转换
├── skill-factory/                  # Skill 自举工厂
├── intake-planner/                 # 需求接收规划
└── reference-style-miner/          # 参考风格挖掘
```

每个 Skill 包含：
- `SKILL.md`：角色定义、写作规范、输出格式要求
- `references/`：细分参考规范（可选），支持多层级知识组织
- **动态加载**：系统启动时自动扫描并注册所有 Skill
- **运行时选择**：根据报告类型、输出格式、用户输入自动匹配最优 Skill 组合

---

## 快速启动

### 前提条件

- Docker + Docker Compose
- （可选）Ollama 本地运行，并拉取模型：
  ```bash
  ollama pull qwen2.5:72b
  ollama pull nomic-embed-text
  ```

### 1. 配置环境

```bash
cp .env.example .env
# 编辑 .env，配置 LLM 地址和模型名
```

### 2. 启动服务

```bash
# macOS 推荐（默认本机开发模式，不依赖 Docker）
./deploy_mac.sh

# 查看状态（dev + docker）
./deploy_mac.sh --status

# Docker 模式（联调/验收）
./deploy_mac.sh --docker

# Docker 重建（仅在镜像/依赖变更时）
./deploy_mac.sh --rebuild

# 生产环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

访问：
- 本机开发前端：`http://127.0.0.1:5173`
- Docker 前端：`http://localhost`
- 后端 API：`http://127.0.0.1:8000/api`
- 管理后台：`http://localhost/admin.html`
- 默认账号：`admin` / `admin123456`

### 3. 构建离线部署包

```bash
./build_offline.sh
# 输出：包含所有 Docker 镜像的离线 tar 包，可在无网络环境部署
```

---

## 开发环境

### 前端

```bash
cd frontend
npm install
npm run build    # esbuild 打包
npm test         # Vitest 单元测试
npm run test:watch
```

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 运行开发服务器
uvicorn app.main:app --reload --port 8000

# 运行测试
pytest
pytest tests/agents/test_planner.py::test_plan
```

---

## 项目结构

```
deep-research/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── agents/           # 智能体实现
│   │   ├── api/              # API 路由
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── services/         # 核心服务
│   │   ├── skills/           # Skill 运行时
│   │   ├── swarm/            # 智能体群编排
│   │   ├── prompt_assets/    # Prompt 资产库
│   │   ├── config.py         # 配置定义
│   │   ├── database.py       # 数据库连接与迁移
│   │   └── main.py           # FastAPI 入口
│   ├── tests/                # Pytest 测试集
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                 # Nginx 静态前端
│   ├── index.html            # 主应用
│   ├── admin.html            # 管理后台
│   ├── app.js                # 主逻辑
│   ├── styles.css            # 样式
│   ├── build.js              # esbuild 脚本
│   ├── tests/                # Vitest 测试
│   ├── package.json
│   └── Dockerfile
│
├── data/                     # 数据持久化（Docker 卷映射）
│   ├── app.db               # SQLite 数据库
│   ├── uploads/             # 用户上传文件
│   ├── templates/           # 文档模板
│   ├── sandbox/             # 沙箱工作区
│   └── redis/               # Redis 持久化
│
├── docker-compose.yml        # 基础编排
├── docker-compose.mac.yml    # macOS 覆盖
├── docker-compose.prod.yml   # 生产覆盖
├── docker-compose.dev.yml    # 开发覆盖
├── build_offline.sh          # 离线打包脚本
├── deploy_mac.sh             # macOS 一键部署
├── .env.example              # 环境变量模板
└── CLAUDE.md                 # Claude Code 项目指引
```

---

## 配置说明

关键环境变量（定义于 `backend/app/config.py` + `.env`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEFAULT_LLM_BASE_URL` | `http://host.docker.internal:11434/v1` | Ollama 或兼容 OpenAI 的推理服务端点 |
| `DEFAULT_LLM_MODEL` | `qwen2.5:72b` | 主推理模型 |
| `LIGHT_LLM_MODEL` | — | 轻量模型（如 qwen2.5:7b），用于快速任务 |
| `HEAVY_LLM_MODEL` | — | 重载模型（如 deepseek-r1:32b），用于深度推理 |
| `RAG_EMBED_MODEL` | `nomic-embed-text` | Embedding 模型（Ollama） |
| `RAG_CHUNK_SIZE` | `400` | 文档分块大小（字符） |
| `RAG_TOP_K` | `8` | 知识库检索返回条数 |
| `SANDBOX_TIMEOUT` | `30` | 数据分析沙箱执行超时（秒） |
| `MAX_WORKERS` | `4` | 并行章节生成最大并发数 |
| `SECRET_KEY` | 自动生成 | JWT 签名密钥 |
| `DEFAULT_ADMIN_USERNAME` | `admin` | 初始管理员账号 |
| `DEFAULT_ADMIN_PASSWORD` | `admin123456` | 初始管理员密码 |

> **注意**：`ENABLE_EXTERNAL_SEARCH` 和 `ENABLE_BROWSER` 在代码中已永久硬编码为 `false`，无法通过配置开启，确保系统始终在内网安全边界内运行。

---

## 技术亮点

### 1. 需求契约驱动的生成范式

系统不盲目遵循通用模板，而是将用户输入转化为**结构化需求契约**：
- 提取用户关键词、分析角度、时间口径、图表策略
- 所有生成环节以契约为准绳，防止"套用通用结构"、"机械摘要附件"
- 生成内容必须通过"需求贴合度"门禁检验

### 2. 多级韧性设计

```
LLM 调用失败 ──► 自动重试（指数退避）
     │
     ▼ 仍失败
大纲质量不足 ──► 自动重新生成 ──► 降级为启发式大纲
     │
     ▼ 仍失败
章节生成失败 ──► 占位符 + 用户提示补充
     │
     ▼ 全文不合格
源文件兜底 ──► 基于上传材料构建确定性草稿
```

### 3. 引用可审计性

所有事实、数字、年份、金额、比例、排名、机构名称、表格数据必须标注：
- **来源**：上传文件 A / 知识库条目 / 研究发现
- **口径**：计算方式、统计周期
- **资料缺口**：无法核验时明确标注，不得编造

### 4. 动态模型路由

```
简单任务（大纲生成、质量审核）──► 轻量模型（qwen2.5:7b）
复杂任务（深度写作、叙事重构）──► 重量模型（qwen2.5:72b）
推理任务（数据分析、代码生成）──► 推理模型（deepseek-r1:32b）
```

---

## 路线图

- [x] 简化三阶段流水线（Simple Pipeline）
- [x] PMRC 叙事重构 + SlideTailor 版式选型
- [x] DECRIM 批判精炼
- [x] 20+ 专业写作 Skill
- [x] RAG 知识库（SQLite 向量存储）
- [x] 离线知识深化（KnowledgeEnricher）
- [x] 数据分析沙箱
- [ ] 多模态输入（图片、表格 OCR）
- [ ] 协作编辑与版本管理
- [ ] 企业 SSO / LDAP 集成
- [ ] 报告模板可视化编辑器

---

## License

[LICENSE](LICENSE)

---

> **DataAgent Studio** — 让深度研究像提交工单一样简单。
