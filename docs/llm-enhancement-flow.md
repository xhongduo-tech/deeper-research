# 平台大模型增强流程设计

## 1. 整体架构

```
用户提问
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 1: 意图路由 (Intent Router)                         │
│ · 大模型判断问题类型: 事实查询 / 数据分析 / 关系探索 / 创作生成 │
│ · 识别涉及领域: 金融 / 政策 / 企业 / 学术 ...              │
│ · 判断深度: 浅层检索 / 深度推理 / 多源融合                 │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: 本体识别 (Ontology Recognition)                    │
│ · 提取问题中的核心实体 (NER)                               │
│ · 识别实体间隐含关系                                       │
│ · 映射到系统本体 + 项目本体的概念网络                       │
│ · 消歧: "苹果" → 公司[科技] 或 水果[农业]                 │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: 数据源路由 (Data Source Routing)                   │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│ │ 系统知识库   │  │ 项目数据库   │  │ 项目本体         │   │
│ │ (L0-L9)     │  │ (CSV/Excel) │  │ (用户构建的图谱)  │   │
│ │ 官方数据源   │  │ DuckDB查询  │  │ 文档抽取的关系    │   │
│ └─────────────┘  └─────────────┘  └─────────────────┘   │
│                                                         │
│ 路由规则由大模型判断:                                      │
│ · "A股行情" → 系统知识库 L1 (事实层)                      │
│ · "我的销量数据" → 项目数据库 (用户上传的CSV)              │
│ · "这家公司的供应链" → 项目本体 + 系统知识库 L2 (关系层)   │
│ · "政策对行业的影响" → 系统本体 L4 (规范层) + L3 (因果层)  │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4: 定向检索 (Targeted Retrieval)                      │
│                                                         │
│ 系统知识库: 向量RAG检索 (已有rag_service)                  │
│ 项目数据库: DuckDB SQL查询 / NL→SQL (已有duckdb_engine)   │
│ 项目本体: 图遍历查询 (ontology_nodes + ontology_edges)     │
│                                                         │
│ 检索策略:                                                  │
│ · 先在本体内定位概念 → 再扩展到关联数据源                   │
│ · 多路召回: 向量相似度 + 关键词匹配 + 图谱邻居              │
│ · 重排序: 按相关性和时效性排序                              │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 5: 融合与推理 (Fusion & Reasoning)                    │
│ · 多源信息去重与冲突检测                                   │
│ · 因果链构建 (L3层能力)                                    │
│ · 逻辑一致性验证                                           │
│ · 不确定性量化 (L9层能力)                                  │
│ · 时效性评估 (L8层能力)                                    │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Step 6: 回答生成 (Response Generation)                     │
│ · 结构化输出 (表格/图表/文本)                              │
│ · 引用溯源 (标明数据来源)                                  │
│ · 置信度标注 (高/中/低)                                    │
│ · 建议延伸问题                                             │
└─────────────────────────────────────────────────────────┘
```

## 2. 核心 Prompt 设计

### 2.1 意图路由 Prompt

```
你是一位专业的研究意图分析专家。请分析用户的问题，输出以下JSON:

{
  "question_type": "fact_query | data_analysis | relation_exploration | creative_generation | comparison",
  "domains": ["finance", "policy", "enterprise", "academic", "technology"],
  "depth": "shallow | medium | deep",
  "requires_data": true/false,
  "requires_ontology": true/false,
  "requires_user_kb": true/false,
  "key_entities": ["实体1", "实体2"],
  "time_scope": "current | historical | forecast | unspecified",
  "confidence": 0.0-1.0
}

用户问题: {user_question}
```

### 2.2 本体识别 Prompt

```
你是一位知识图谱专家。请从用户问题中提取实体和关系，并映射到已知本体。

已知系统本体概念（部分）:
{system_ontology_concepts}

已知项目本体概念（部分）:
{project_ontology_concepts}

用户问题: {user_question}

输出JSON:
{
  "entities": [
    {
      "text": "贵州茅台",
      "type": "company",
      "ontology_match": {
        "system": "企业领域/上市公司",
        "project": "项目A/核心企业"
      },
      "confidence": 0.95
    }
  ],
  "relations": [
    {
      "source": "贵州茅台",
      "relation": "持有",
      "target": "贵州茅台酒",
      "ontology_match": "企业领域/股权关系",
      "confidence": 0.88
    }
  ],
  "disambiguation": [
    {
      "text": "苹果",
      "candidates": ["苹果公司[科技]", "苹果[水果/农业]"],
      "resolved": "苹果公司[科技]",
      "reason": "上下文涉及供应链和股市"
    }
  ]
}
```

### 2.3 数据源路由决策 Prompt

```
基于意图分析和本体识别结果，决定检索哪些数据源。

意图分析: {intent_result}
本体识别: {ontology_result}
可用数据源:
- 系统知识库: {available_system_sources}
- 项目数据库: {available_project_tables}
- 项目本体: {available_project_ontology}

输出JSON:
{
  "sources": [
    {
      "type": "system_kb",
      "layer": "L1",
      "sources": ["A股行情", "宏观经济"],
      "reason": "问题涉及股价数据，需要事实层",
      "priority": 1
    },
    {
      "type": "project_db",
      "table": "sales_2024",
      "query": "SELECT * FROM sales WHERE company LIKE '%茅台%'",
      "reason": "用户上传了销量数据",
      "priority": 2
    },
    {
      "type": "project_ontology",
      "nodes": ["node_123", "node_456"],
      "hop_depth": 2,
      "reason": "需要探索供应链关系",
      "priority": 3
    }
  ]
}
```

### 2.4 实体关系抽取 Prompt (用于本体建模)

```
从以下文本中提取实体和关系，构建知识图谱。

文本: {document_text}

领域: {domain}

输出JSON:
{
  "entities": [
    {
      "name": "宁德时代",
      "type": "company",
      "aliases": ["CATL", "Ningde Times"],
      "properties": {"industry": "动力电池", "location": "福建宁德"}
    }
  ],
  "relations": [
    {
      "source": "宁德时代",
      "relation_type": "supplies_to",
      "target": "特斯拉",
      "evidence": "文本第3段: 宁德时代为特斯拉供应磷酸铁锂电池",
      "confidence": 0.92
    }
  ]
}
```

## 3. 项目维度数据模型

### 3.1 新增表

```sql
-- 项目表
CREATE TABLE projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  owner_id INTEGER REFERENCES users(id),
  status VARCHAR(20) DEFAULT 'active', -- active, archived, deleted
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目与知识库关联 (知识库现在必须属于某个项目)
-- 在 knowledge_bases 表增加 project_id 字段
ALTER TABLE knowledge_bases ADD COLUMN project_id INTEGER REFERENCES projects(id);

-- 项目与数据表关联 (DuckDB 注册的表)
CREATE TABLE project_tables (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  name VARCHAR(200) NOT NULL,
  file_path VARCHAR(500),
  file_type VARCHAR(20), -- csv, xlsx, parquet
  table_name VARCHAR(200), -- DuckDB 中的表名
  row_count INTEGER,
  column_schema JSON, -- [{name, type, sample_values}]
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目本体 (复用 ontology_nodes/edges，增加 project_id)
-- ontology_nodes 已有 kb_id，可以关联到项目的知识库
```

### 3.2 关系图

```
users
  │
  ├──► projects (用户创建的项目)
  │      │
  │      ├──► knowledge_bases (项目的知识库 - Word/PDF 等非结构化文档)
  │      │      │
  │      │      ├──► kb_documents
  │      │      ├──► kb_chunks (向量检索)
  │      │      ├──► ontology_nodes (从文档抽取的实体)
  │      │      └──► ontology_edges (实体关系)
  │      │
  │      └──► project_tables (项目的结构化数据表 - CSV/Excel)
  │             │
  │             └──► DuckDB 内存表 (运行时注册)
  │
  └──► system-level data (全局)
         │
         ├──► official_datasources (官方数据源)
         ├──► domain_schemas (领域本体快照)
         └──► ontology_nodes (系统本体，kb_id = NULL)
```

## 4. 前端界面映射

### 4.1 数据库中心 (KnowledgeBasePage)

```
数据库中心
├── 系统知识库
│   └── 十层架构 (L0-L9) + 官方数据源
│
├── 项目数据库
│   ├── 项目列表 (左侧面板)
│   │   ├── 项目A
│   │   │   ├── [数据表] tab
│   │   │   │   └── CSV/Excel 列表 + DuckDB 查询
│   │   │   └── [知识图谱] tab
│   │   │       └── 从项目文档抽取的实体关系
│   │   └── 项目B
│   └── 新建项目
│
└── 本体建模
    ├── 系统本体 (只读)
    │   └── 领域概念 + 关系网络
    └── 项目本体 (可编辑)
        └── 可视化编辑器 + 大模型自动抽取
```

### 4.2 各子界面 (TemplatePage)

```
Word/PPT/Excel/HTML 界面
├── 顶部项目选择器
│   └── [新能源汽车分析 ▼] 新建项目
│
├── 新建任务时
│   └── 提示: "选择或创建项目，系统将自动加载项目资源"
│
└── 提问时自动注入项目上下文
    └── "基于项目『新能源汽车分析』的知识库和数据表进行回答..."
```

## 5. API 扩展清单

### 5.1 后端新增 API

```
/projects
  GET    /api/projects              列出用户的项目
  POST   /api/projects              创建项目
  GET    /api/projects/{id}         获取项目详情
  PUT    /api/projects/{id}         更新项目
  DELETE /api/projects/{id}         删除项目

/projects/{id}/tables
  GET    /api/projects/{id}/tables              列出项目数据表
  POST   /api/projects/{id}/tables/upload        上传 CSV/Excel
  DELETE /api/projects/{id}/tables/{table_id}    删除数据表
  POST   /api/projects/{id}/tables/{table_id}/query  DuckDB 查询

/ontology (已有，需扩展)
  POST   /api/ontology/extract                    从文本提取KG (已有)
  POST   /api/ontology/nodes                      创建节点 (新增)
  PUT    /api/ontology/nodes/{id}                 更新节点 (新增)
  DELETE /api/ontology/nodes/{id}                 删除节点 (新增)
  POST   /api/ontology/edges                      创建边 (新增)
  DELETE /api/ontology/edges/{id}                 删除边 (新增)
  GET    /api/ontology/visualization              获取可视化数据 (新增)
```

### 5.2 前端新增 API 方法

```typescript
// projects
api.listProjects(): Promise<{ items: Project[] }>
api.createProject(name: string, opts?: { description?: string }): Promise<Project>
api.getProject(id: number): Promise<Project>

// project tables
api.listProjectTables(projectId: number): Promise<{ items: ProjectTable[] }>
api.uploadProjectTable(projectId: number, file: File): Promise<ProjectTable>
api.queryProjectTable(projectId: number, tableId: number, query: string): Promise<{ rows: any[]; columns: string[] }>

// ontology editing
api.createOntologyNode(data: OntologyNodeData): Promise<OntologyNode>
api.updateOntologyNode(id: number, data: Partial<OntologyNodeData>): Promise<OntologyNode>
api.deleteOntologyNode(id: number): Promise<void>
api.createOntologyEdge(data: OntologyEdgeData): Promise<OntologyEdge>
api.deleteOntologyEdge(id: number): Promise<void>
api.getOntologyVisualization(kbId?: number): Promise<{ nodes: any[]; edges: any[] }>
```

## 6. 实施路线图

| 阶段 | 目标 | 主要工作 | 预计工期 |
|------|------|----------|----------|
| Phase 1 | 架构对齐 | 前端改tab、十层架构静态展示、项目列表UI | 1天 |
| Phase 2 | 系统知识库 | 系统本体只读展示、官方数据源对接 | 1-2天 |
| Phase 3 | 项目数据库 | 后端projects表、前端项目维度、DuckDB查询 | 2-3天 |
| Phase 4 | 本体建模 | 可视化画布、增删改API、大模型自动抽取 | 3-5天 |
| Phase 5 | 跨界面打通 | 子界面项目选择器、提问时本体路由 | 2-3天 |

总计: 2周完成全平台重构。
