# CLAUDE.md — iko 知识研究系统

## 项目身份

iko（爱祝/ai祝）是创业方法研究和知识系统。
核心哲学：长编→定本，搜→写→劈，以乐为终。
研究方向：①AI边缘产业扫描（AI与传统产业的结合点） ②创业方法论+创业人物谱系研究（成功者与'意难平'对照）

## 技术栈概要

- **前端**：Next.js 14 (App Router) + Tailwind CSS + shadcn/ui
- **后端**：Python FastAPI + Pydantic v2（过渡期为纯Next.js Server Actions，后续拆出）
- **数据库**：PostgreSQL + pgvector（Supabase托管）
- **ORM**：Drizzle ORM (TS) / SQLAlchemy (Python)
- **AI**：Claude-3-opus (主力长文) + GPT-4o (快速推理) + Groq (低延迟)
- **部署**：Vercel (前端+Edge) + Railway (后端API)
- **监控**：Sentry + OpenTelemetry + Axiom
- **搜索**：Meilisearch（知识库全文搜索）

## 架构原则

1. **上下文连续性优先**：所有设计确保LLM能看到完整对话历史+记忆胶囊
2. **可演进架构**：MVP用单体+Server Actions，不引入Kafka/微服务/独立向量库
3. **LLM原生接口**：优先让LLM读OpenAPI文档调用，而非手写SDK胶水
4. **记忆即产品**：Memory Layer是iko的核心差异，不允许被外部服务控制
5. **以乐为终**：用户体验优先于技术完美。宁可返工不要过度工程

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 向量库 | pgvector（不独立部署） | 一人团队不要维护两个数据库 |
| 部署 | Vercel + Railway | 零运维，免费额度够MVP |
| 前端状态 | React Server Components + URL params | 不需要Redux/Zustand |
| AI编排 | 自写编排函数 | LangChain抽象层太高，一人可控 |
| 认证 | Supabase Auth | 和数据库安全策略原生整合 |
| 任务队列 | Vercel Cron + Inngest | Celery太重，SQLite不够 |

## 一人团队工程纪律

### 代码规范
- 所有AI生成的代码必须包含架构注释（/* 为何这样设计 */）
- 禁止"一次性代码"：每个函数/组件必须有明确的职责声明
- 数据库schema变更必须附带down migration
- API响应必须有统一格式：`{ok, data?, error?, meta?}`

### 记忆层规范
- 对话摘要每5轮写一次pgvector嵌入
- 记忆胶囊每周自动刷新新鲜度（fresh→warm→grey→cold）
- 前提变化（premise change）自动触发推送提醒
- 胶囊去重：同一天同一用户同话题不重复推送

### MVP阶段演进路径
- **Phase 0**（当前）：纯Next.js + AI SDK + 本地PostgreSQL
- **Phase 1**（用户<100）：接入Supabase + FastAPI后端拆出 + pgvector
- **Phase 2**（用户<1000）：Meilisearch + Sentry + Cron记忆刷新
- **Phase 3**（用户>1000）：评估是否需要独立向量库/缓存层/CDN

### 命名约定
- 前端组件：`PascalCase`，目录 `feature-name/`
- 后端路由：`/api/v1/{resource}`
- 数据库表：`snake_case`，`t_`前缀（如 `t_capsules`）
- 环境变量：`NEXT_PUBLIC_*`（前端），`IKO_*`（后端）

### 关键命令
```bash
# 本地开发
npm run dev              # Next.js前端
uvicorn api.main:app --reload  # FastAPI后端

# 数据库
npm run db:generate      # 生成migration
npm run db:migrate       # 执行migration
npm run db:push          # 推送到Supabase

# 部署
npm run build            # 构建
git push main            # Vercel自动部署

# 测试
npm run test             # 单元测试
npm run test:e2e         # E2E测试
```

### 问答

**Q: MVP阶段能用Tailwind吗？**
A: 可以，shadcn/ui无依赖，但自定义组件尽量用Tailwind utility classes，减少CSS文件。

**Q: 后端用FastAPI还是Next.js API Routes？**
A: Phase 0用Server Actions + API Routes（一人不需要两个服务）。当需要WebSocket/SSE/长任务时，拆出FastAPI。

**Q: 需要Kubernetes吗？**
A: 不需要。MVP阶段1000用户以内，Vercel + Railway扛得住。

**Q: 何时引入AI缓存？**
A: 当相同prompt+上下文组合出现频率>10次/天时，考虑用PostgreSQL做结果缓存（TTL按场景设定）。
