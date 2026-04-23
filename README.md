# 深研 AI · DataAgent

> **银行内网离线环境下的 Supervisor 协作式报告生产系统**
> 
> 用户提交委托 + 材料，Chief 主管与用户协作对话、动态组建数字员工团队、基于上传材料生产可交付的专业报告。

![深研 AI](深度研究数据分析智能体%20·%20dataagent.png)

---

## 目录

1. [产品定位](#1-产品定位)
2. [核心架构：异步状态机 + Fire-and-Steer](#2-核心架构异步状态机--fire-and-steer)
3. [10 名数字员工（Roster v3）](#3-10-名数字员工roster-v3)
4. [4 阶段生产流水线](#4-4-阶段生产流水线)
5. [技术栈](#5-技术栈)
6. [项目结构](#6-项目结构)
7. [快速启动](#7-快速启动)
8. [REST API 概览](#8-rest-api-概览)
9. [部署说明（内网离线）](#9-部署说明内网离线)
10. [架构演进说明](#10-架构演进说明)

---

## 1. 产品定位

### 三个"是"

| 是 | 说明 |
|---|---|
| **Supervisor-led 报告工厂** | Chief 主管全程负责，用户和 Chief 对话，Chief 和员工干活 |
| **基于材料的结构化生产** | 一切从用户上传的材料出发，严格以材料为证据，不联网不编造 |
| **API 和 UI 等价** | UI 能触发的任何动作都有对应的 REST API；API 返回结构化报告对象 |

### 三个"不是"

- **不是问答系统**：不是聊天气泡流，每次交互都围绕一份具体报告推进
- **不是联网研究系统**：不依赖外部知识库，所有信息源 = 用户上传材料  
- **不是画布式工作流**：用户不画 DAG，Supervisor 决定工作流

### 支持的报告类型

| 类型 | 代号 | 典型输入 | 典型交付 |
|---|---|---|---|
| 经营分析报告 | `ops_review` | 经营数据 Excel、历史报告 | 月/季度经营分析 Word |
| 内部专题研究 | `internal_research` | 专题材料、政策文件 | 研究报告 Word/PPT |
| 风险评估报告 | `risk_assessment` | 客户材料、风险数据 | 风险评估 Word |
| 合规监管报送 | `regulatory_filing` | 监管模板、原始数据 | 按模板填充文档 |
| 内部培训材料 | `training_material` | 制度文件、操作手册 | 培训 Word/PPT |

---

## 2. 核心架构：异步状态机 + Fire-and-Steer

### 传统 Supervisor 架构的两个致命弱点

传统 Supervisor 模式中，每个 Subagent 调用本质上是主 Agent 的一次**同步 Tool Call**：

```
Supervisor ──await──► Employee1  (阻塞)
Supervisor ──await──► Employee2  (阻塞)
Supervisor ──await──► Employee3  (阻塞)
```

问题：
- **同步阻塞（Deadlock）**：6 个章节每章 30s → 串行等待 180s
- **协调损耗（Coordination Tax）**：方向偏了只能等完成后重来

### 本系统解法：异步状态机 + SubagentManager

```
                  ┌──────────────────────────────────────────┐
                  │           SubagentManager                │
                  │  task_id_1 → asyncio.Task (Employee1)    │
Supervisor ──────►│  task_id_2 → asyncio.Task (Employee2)    │
Fire-and-Steer    │  task_id_3 → asyncio.Task (Employee3)    │
                  │            (全部并行运行)                  │
                  └──────────────┬───────────────────────────┘
                                 │
                  Supervisor 在此期间可以：
                  ① steer(task_id_1, "请强调风险敞口部分")
                  ② cancel(task_id_2) 并重新派遣
                  ③ 继续处理其他逻辑
                                 │
                  ◄──────────────┘
                  collect(all_task_ids) → 汇总结果
```

**性能对比（以 6 个章节，每章 LLM 调用 30s 为例）：**

| 模式 | 耗时 |
|---|---|
| 传统串行 | 6 × 30s = **180s** |
| 依赖感知并行（无依赖） | 1 批 × 30s = **~33s** |

### 关键组件

```
app/services/subagent_manager.py   # SubagentManager 单例
  .launch(coro) → task_id          # 发射，立即返回（Fire-and-Steer）
  .steer(task_id, instruction)     # mid-flight 指令注入
  .cancel(task_id)                 # 取消任务
  .collect([task_ids])             # await 一批完成

app/services/execution_state.py    # 生产流水线共享状态
  .steering_instructions           # section_id → mid-flight 指令
  .task_id_map                     # step_id → SubagentManager task_id
  .inject_steering(sid, instr)     # Supervisor 注入指令
  .pop_steering(sid)               # Employee 消费指令

app/api/v1/subagents.py            # 控制平面 API
  GET  /subagents/reports/{id}     # 查看所有 subagent 状态
  POST /subagents/{task_id}/steer  # 注入 mid-flight 指令
  DEL  /subagents/{task_id}        # 取消任务

app/api/v1/reports.py              # 用户友好的 steer 入口
  POST /reports/{id}/steer         # 通过 section_id 直接 steer

app/services/escalation_service.py # 专家升级决策引擎
app/agents/employees/registry.py   # EXPERT_AGENTS（10 位 expert_*，is_hidden）
```

### 专家自动升级（Expert Escalation）

每位普通员工在注册表中都有对应的 **Expert Agent**（`expert_*` ID，默认更强模型与 Think-Plan-Execute-Verify 提示）。升级由 `EscalationService.decide()` 统一裁决：

| 触发条件 | 优先级 | 行为 |
|---|---|---|
| Steering / API 含 `[EXPERT_ESCALATE]` | 最高 | `manual_override`，强制专家 |
| QA 重写次数 `qa_retry_count >= 2` | 高 | 第二次质检退回重写时走专家 |
| 数据步骤首轮无指标或沙箱失败 | 中 | Supervisor 以 `error_count=1` 自动再跑一轮 Quinn+ |
| 任务复杂度评分 `>= 0.60` | 常 | 长 brief、多证据、复杂章节类型等加权得分 |

合成与质检阶段：`EmployeeRunner.run_synthesis` 将 `employee.default_model` 传给 LLM（专家卡多为 `gpt-4o`），并提升 `max_tokens` / `timeout`。`RunResult.resolved_employee_id` 与 `SubagentTask.employee_id` 在升级后指向实际执行的专家，便于控制平面展示。

---

## 3. 10 名数字员工（Roster v3）

所有员工工作在**离线内网**环境，工具白名单中永不包含 `browser_tool` / `search_tool`。

| # | ID | 英文名 | 职位 | 核心能力升级（v3） |
|---|---|---|---|---|
| 01 | `intake_officer` | **Elin** | Intake Officer | 信息缺口主动检测、执行计划生成 |
| 02 | `material_analyst` | **Remy** | Material Analyst | **pdfplumber 精确表格提取**、实体识别、置信度标注 |
| 03 | `data_wrangler` | **Quinn** | Data Wrangler | **PandasAI 级分析**：多表 JOIN、ARIMA 时序、IQR 异常检测、OLS 回归、自愈代码 |
| 04 | `chart_maker` | **Iris** | Chart Maker | **8 种图表**（含瀑布图/热力图/双轴图）、自动图表类型选择、品牌配色 |
| 05 | `risk_auditor` | **Adler** | Risk Auditor | **量化风险**：PD/LGD/VaR 计算、情景分析、5×5 风险矩阵 |
| 06 | `structured_writer` | **Li Bai** | Structured Writer | 证据 ID 内联引用、逻辑链控制、银行报告文风 |
| 07 | `template_filler` | **Nash** | Template Filler | 字段映射、单位换算、必填项核查 |
| 08 | `compliance_checker` | **Orin** | Compliance Checker | 正则敏感词扫描、数值一致性、监管必答项检查 |
| 09 | `qa_reviewer` | **Sage** | QA Reviewer | **幻觉检测**：data_context 精确比对、引用追溯、anti-hallucination 重写循环 |
| 10 | `layout_designer` | **Milo** | Layout Designer | 封面/目录/样式/图表嵌入、企业模板 .dotx 覆盖 |

**特别角色：**

| ID | 英文名 | 职位 | 特殊能力 |
|---|---|---|---|
| `supervisor` | **Chief** | Production Supervisor | 异步调度、mid-flight steering、5阶段生命周期管理 |

---

## 4. 4 阶段生产流水线

```
用户提交委托
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1 · 规划（Elin）                              ~5s          │
│                                                                  │
│ brief + 材料摘要 → 结构化执行计划（data步骤 + synthesis步骤）     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 2 · 数据采集（Quinn · 依赖感知并行）           ~20-40s      │
│                                                                  │
│ 多个数据步骤按依赖关系分批并行执行                                 │
│ 每步：LLM生成Pandas代码 → 安全沙箱执行 → 安全扫描 → 存入           │
│ data_context（已验证指标库）                                      │
│                                                                  │
│ 可用库：pandas / numpy / scipy / sklearn / statsmodels           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 3 · 并行合成（SubagentManager）               ~30-60s      │
│                                                                  │
│ 所有章节同时发射 → SubagentManager 管理生命周期                    │
│ 每个 Employee 收到：上下文 + data_context + 证据片段 + steering    │
│ Supervisor 可在任意时刻 steer 修正某章节方向                       │
│ 章节完成即时更新 UI 预览（实时显影效果）                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Phase 4 · QA + 交付（Sage + Milo）                  ~15-30s      │
│                                                                  │
│ Sage：幻觉检测（data_context 精确比对）→ 不通过触发重写循环         │
│ Milo：Word 排版生成（封面/目录/样式/图表嵌入）                      │
│ 交付：final_file_path 写入 DB，SSE 推送 delivered 事件             │
└─────────────────────────────────────────────────────────────────┘
```

### 报告生命周期状态机

```
draft → intake → scoping → producing → reviewing → delivered
                                │
                          cancelled (任意阶段可取消)
```

---

## 5. 技术栈

### 后端

| 层次 | 技术 |
|---|---|
| Web 框架 | FastAPI + uvicorn |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |
| 异步 ORM | SQLAlchemy 2.0 async + aiosqlite |
| LLM 接入 | OpenAI-compatible API（离线内网自部署模型） |
| 数据科学 | pandas + numpy + **scipy** + **scikit-learn** + **statsmodels** |
| 文档解析 | **pdfplumber**（精确表格）+ PyPDF2 + python-docx + python-pptx + openpyxl |
| 可视化 | matplotlib + seaborn（8种图表类型） |
| 安全沙箱 | 内置 AST 安全检查 + 受限命名空间执行 |
| 实时推送 | SSE（Server-Sent Events）|
| 模板引擎 | Jinja2 |

### 前端

| 层次 | 技术 |
|---|---|
| 框架 | React 18 + TypeScript |
| 构建 | Vite |
| 样式 | Tailwind CSS + 自定义设计系统（tokens.ts） |
| 状态管理 | Zustand |
| HTTP | TanStack Query + axios |

### 部署

```
Nginx (反向代理)
  ├── /api/* → FastAPI (uvicorn)
  └── /* → React SPA (静态文件)

Docker Compose (3 服务)
  ├── backend   (Python 3.12)
  ├── frontend  (Node 18 builder → Nginx 静态)
  └── nginx     (反向代理)
```

---

## 6. 项目结构

```
deep-research/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── base_agent.py              # 数字员工基础类
│   │   │   └── employees/
│   │   │       ├── registry.py            # Roster v3：10名员工定义
│   │   │       └── runner.py              # EmployeeRunner：LLM调用分发
│   │   │
│   │   ├── api/v1/
│   │   │   ├── reports.py                 # 报告生命周期 API + steer 端点
│   │   │   ├── subagents.py              # SubagentManager 控制平面 API
│   │   │   ├── files.py                   # 文件上传/下载
│   │   │   ├── workforce.py               # 员工信息 API
│   │   │   ├── developer.py               # API Key 自助管理
│   │   │   └── admin.py                   # 管理员后台
│   │   │
│   │   ├── generators/
│   │   │   ├── chart_generator.py         # 8种图表生成（含瀑布图）
│   │   │   ├── word_generator.py          # Word 报告生成
│   │   │   └── ppt_generator.py           # PPT 生成
│   │   │
│   │   ├── services/
│   │   │   ├── supervisor_service.py      # Chief 决策逻辑 + 4阶段流水线
│   │   │   ├── subagent_manager.py        # 异步任务注册 + Fire-and-Steer
│   │   │   ├── execution_state.py         # 生产流水线共享状态机
│   │   │   ├── sandbox_service.py         # 安全沙箱（含scipy/sklearn）
│   │   │   ├── llm_service.py             # LLM 网关
│   │   │   ├── knowledge_base_service.py  # 证据检索
│   │   │   ├── qa_validation_service.py   # 幻觉检测
│   │   │   └── event_bus.py               # SSE 事件广播
│   │   │
│   │   └── tools/
│   │       ├── file_reader.py             # 文件解析（pdfplumber优先）
│   │       ├── excel_analyzer.py          # Excel 数据画像
│   │       └── pil_charts.py              # PIL 轻量图表
│   │
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── HomePage.tsx               # 委托入口（Compose Zone）
│   │   │   ├── ReportPage.tsx             # 报告详情（双栏布局）
│   │   │   ├── WorkforcePage.tsx          # 员工身份牌墙
│   │   │   ├── ArchivePage.tsx            # 历史报告检索
│   │   │   └── DeveloperPage.tsx          # API Key 管理
│   │   │
│   │   ├── design-system/
│   │   │   ├── tokens.ts                  # 设计 Token（色彩/字体/圆角）
│   │   │   └── primitives/                # Button/Input/Badge/Dialog...
│   │   │
│   │   └── stores/
│   │       ├── reportStore.ts             # 报告状态管理
│   │       └── authStore.ts               # 认证状态
│   │
│   └── Dockerfile
│
├── nginx/nginx.conf
├── docker-compose.yml                     # 生产环境（Linux）
├── docker-compose.mac.yml                 # Mac 本地开发
├── docker-compose.prod.yml                # 带 PostgreSQL 的生产配置
├── DESIGN.md                              # 产品与工程设计总纲（v2.0）
└── README.md                              # 本文件
```

---

## 7. 快速启动

### 前置要求

- Docker + Docker Compose
- 内网大模型接入点（OpenAI-compatible API）

### Mac 本地开发

```bash
# 1. 复制环境变量
cp .env.example .env
# 编辑 .env，填写 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

# 2. 启动
docker-compose -f docker-compose.mac.yml up --build

# 访问：http://localhost:3000
# API 文档：http://localhost:8000/api/docs
```

### 内网生产部署

```bash
# 1. 配置环境变量
cp .env.example .env
vim .env  # 填写内网 LLM 接入点

# 2. 构建并启动
docker-compose -f docker-compose.prod.yml up -d --build

# 3. 健康检查
curl http://localhost/api/health
```

### 环境变量说明

```bash
# LLM 接入（必填）
DEFAULT_LLM_BASE_URL=http://your-intranet-llm/v1
DEFAULT_LLM_MODEL=your-model-name
DEFAULT_LLM_API_KEY=your-api-key

# 系统配置
APP_NAME=深研AI
SECRET_KEY=your-secret-key-change-this
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123

# 禁用外网（内网部署必须为 false）
ENABLE_EXTERNAL_SEARCH=false
ENABLE_BROWSER=false
```

---

## 8. REST API 概览

所有路径前缀 `/api/v1`。鉴权：Web 用 session cookie，API 用 `Authorization: Bearer <api_key>`。

### 报告生命周期

```
POST   /reports                         # 创建报告（含文件 IDs）
GET    /reports                         # 报告列表（分页+过滤）
GET    /reports/{id}                    # 报告详情
POST   /reports/{id}/start              # 触发生产
POST   /reports/{id}/cancel             # 取消
POST   /reports/{id}/steer              # 向章节注入 mid-flight 指令 ★新
POST   /reports/{id}/reply              # 用户回复 Supervisor 追问
POST   /reports/{id}/interject          # 用户主动插话
GET    /reports/{id}/events  (SSE)      # 实时事件流
```

### SubagentManager 控制平面（新增）

```
GET    /subagents/reports/{id}          # 查看 report 下所有 subagent 状态
GET    /subagents/{task_id}             # 单个任务详情
POST   /subagents/{task_id}/steer       # 注入 mid-flight 指令
DELETE /subagents/{task_id}             # 取消任务
```

### Expert Escalation 控制平面

```
POST   /escalation/reports/{id}/sections/{section_id}  # 手动专家升级（或排队 steering）
GET    /escalation/reports/{id}                       # 本报告已升级任务列表
POST   /escalation/preview                            # 复杂度评分预览（UI 提示用）
```

### 文件与资源

```
POST   /files                           # 上传文件（multipart）
GET    /files/{id}                      # 下载文件
GET    /report-types                    # 报告类型 + 结构骨架
GET    /workforce                       # 员工列表
```

### 开发者

```
GET    /developer/api-keys              # 我的 API Key 列表
POST   /developer/api-keys              # 申请 Key（自动审批）
DELETE /developer/api-keys/{id}         # 撤销
```

**完整 API 文档：** `http://your-host/api/docs`（FastAPI Swagger）

---

## 9. 部署说明（内网离线）

### 离线约束

本系统设计运行在**银行内网完全隔离环境**：

| 约束 | 实现方式 |
|---|---|
| 无互联网 | `browser_tool` / `search_tool` 已从代码库永久删除 |
| 无外部知识库 | 报告结构骨架内置在代码中（`report_types.py`）|
| 材料是唯一信息源 | 员工 `tools` 白名单：只含 `file_reader / sandbox / office_converter` 等离线工具 |
| LLM 离线部署 | 仅通过 `DEFAULT_LLM_BASE_URL` 访问内网模型 |
| 文件存储本地 | `./uploads / ./data`，不连对象存储 |

### Docker 镜像离线构建

```bash
# 在有网环境预先拉取镜像
docker pull python:3.12-slim
docker pull node:18-alpine
docker pull nginx:alpine

# 导出
docker save python:3.12-slim | gzip > python312.tar.gz

# 内网导入
docker load < python312.tar.gz

# 构建（离线 pip 需预先准备 wheels）
pip download -r backend/requirements.txt -d ./wheels
docker-compose build --build-arg PIP_NO_INDEX=1
```

---

## 10. 架构演进说明

### v1 → v2：传统 Supervisor → 协作式生产

v1 是简单的 Task → Sub-task 串行模式。  
v2 引入 Supervisor 协作模型：用户与 Chief 持续对话，Chief 动态组队。

### v2 → v3：同步阻塞 → 异步状态机（当前版本）

**核心升级：**

1. **框架层编排演进**  
   引入 `SubagentManager`：子智能体启动后立即返回 `task_id` 并后台运行。  
   Supervisor 从"发射后不管"变为"发射并控制（Fire-and-Steer）"。

2. **并行执行引擎**  
   Phase 2（数据采集）：依赖感知拓扑分批并行  
   Phase 3（章节合成）：所有无依赖章节同时发射，`asyncio.gather` 汇总

3. **Subagent 能力升级**  
   Quinn 获得 PandasAI 级分析能力（scipy + sklearn + statsmodels）  
   Remy 获得 pdfplumber 精确表格提取  
   Iris 获得 8 种图表类型 + 品牌配色  
   Adler 获得量化风险指标计算

4. **MCP-compatible 工具白名单**  
   所有员工工具调用统一通过 `BaseAgent.ALLOWED_TOOLS` 白名单管理，  
   架构兼容 MCP 协议扩展（未来可通过配置挂载外部 MCP Server）。

5. **代码库整理**  
   删除：`browser_tool.py` / `search_tool.py` / `tools/sandbox.py`（重复）  
   升级：`requirements.txt` 增加 pdfplumber / statsmodels / tabulate / xlsxwriter / jinja2

6. **专家自动升级（Expert Escalation）**  
   每位员工映射 `expert_*` 专家卡；`EscalationService` 按复杂度 / QA 失败 / 执行错误 / 手动指令自动或强制切换；`LLMService.chat(model=employee.default_model)` 区分普通与专家模型；数据阶段失败自动 Quinn+ 重试一轮。

---

## License

内部项目，仅供行内使用。
