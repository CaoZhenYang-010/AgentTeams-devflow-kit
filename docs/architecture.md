# AgentTeams DevFlow Kit 架构说明

> 版本：v2.0（2026-08-14）
> 新增：全自动流水线驱动（run-pipeline.py），实现"发一个需求 → 13 节点全自动跑完 → 发布 → 通知 Manager"。

---

## 一、整体架构

基于 AgentTeams 的 Manager – Team Leader – Worker 分层架构，支持**手动驱动**与**全自动驱动**两条路径：

```
用户（Human）
  ├── 方式一（手动）：Element Web 逐节点发消息，全程可介入
  └── 方式二（自动）：run-pipeline.py 一键驱动（见第五节）
  ▼
Manager（AgentTeams 框架）
  │ 接收需求、创建/调度 Agent、汇总交付
  ▼
devflow-runner（Worker · 编排）
  │ 读 workflow.yaml → 按序派发 → 维护状态 → fail_to 回流
  ▼
┌─────────────── 研发团队（2 个 Team）────────────────┐
│  architecture-team                                 │
│    ├── architect-leader (Team Leader)  架构评审门禁  │
│    └── designer                       系统设计       │
│  quality-team                                       │
│    ├── quality-leader (Team Leader)   质量门禁       │
│    ├── implementer                    TDD 编码       │
│    ├── tester                         测试/构建/E2E   │
│    ├── reviewer                       代码评审        │
│    └── analyst                        对抗/定位/影响面 │
└────────────────────────────────────────────────────┘
               │
         工具层（确定性验证）
  tools/：test_runner / coverage / impact_analyzer / git_helper
```

**关键点**：
- **角色**：8 个 Worker + 2 个 Team（架构团队/质量团队）
- **运行环境**：自定义 Worker 镜像（Java 17 + Maven + MySQL + Playwright，见 `docker/`）
- **驱动**：手动（Element Web）或自动（run-pipeline.py）

---

## 二、流水线（workflow.yaml + pipeline.json）

13 个节点（workflow.yaml 定义，pipeline.json 驱动），核心回流逻辑：

```
设计 → [架构评审] → 后端编码 → [后端测试+覆盖率] ──失败──→ 缺陷定位 ←──┐
         │ 不通过→回流设计                ↓                         │
         └──────── 前端编码 → [前端构建] ─失败──────────────→        │
                                     ↓                             │
                                [代码评审] ─不通过────────────────→   │
                                     ↓                             │
                              [对抗性测试] ─失败─────────────────→    │
                                     ↓                             │
                              [影响面分析]                           │
                                     ↓                             │
                                  [E2E] ─失败──────────────────→     │
                                     ↓                             │
                              [质量门禁] ─不通过────────────────→    │
                                     ↓                             │
                                发布（git commit [ci pass]）         │
                                     ↓                              │
                              通知 Manager（通过节点数）              │
                                                        ↓ 带证据回流 implementer 修复
```

> `workflow.yaml` 定义节点/角色/回流规则（文档）；`pipeline.json` 定义驱动参数（worker/产物/success 关键词/提示语）。

---

## 三、全自动流水线驱动（run-pipeline.py）

### 3.1 运行机制

```
读 pipeline.json
  → 获取 admin token + 各 Worker 房间 + matrixUserID
  → 重置所有 Worker 会话（/new，清除跨需求上下文污染）
  → 对每个节点：
      给 Worker 房间发提示语（真提及格式）
      → 轮询 MinIO 等产物（mc stat）
      → 内容关键词校验（BUILD SUCCESS / approved / Failures:0）
      → 通过则推进 / 超时重试 / 失败按 fail_to 回流
  → 全部完成 → 通知 Manager（通过节点数）
```

### 3.2 关键技术点

| 技术点 | 说明 |
|--------|------|
| **Matrix 真提及** | 消息带 `format` + `formatted_body`(permalink) + `m.mentions.user_ids`，否则 Worker 不响应 |
| **产物检测** | `mc stat` 轮询 MinIO，Worker 须用 file-sync 同步到 MinIO |
| **内容校验** | `nodes[].success` 关键词判定通过/失败（匹配实际报告措辞）|
| **fail_to 回流** | 门禁拒绝 → defect-locate → implementer 精准修复 → 重跑 |
| **重试机制** | 节点超时自动重发（最多 2 次）|
| **会话重置** | 运行前对所有 Worker 发 `/new`，避免跨需求上下文污染 |
| **Manager 通知** | 完成后发 DM 给 Manager，报告通过节点数 |

### 3.3 使用方式

```bash
# 运行在 controller 容器内
docker exec agentteams-controller bash -c \
  'cd /root/agentteams-fs/agents/manager && \
   PYTHONIOENCODING=utf-8 python3 -u run-pipeline.py "需求" \
   --rules "业务规则" [--max-nodes N] [--dry-run]'
```

---

## 四、验证机制（差异化核心）

| 机制 | 实现 | 保证 |
|------|------|------|
| 真实测试 | tester 运行 mvn test（80 用例）| ✅ 确定性 |
| **覆盖率** | **JaCoCo 预置模板**，每次 `mvn test` 生成 | ✅ 确定性，始终可验证 |
| 对抗性测试 | analyst 独立生成攻击用例 | ✅ 机制隔离 |
| 缺陷定位 | analyst 基于证据 + 源码 | ⚠️ LLM + 证据 |
| 影响面分析 | 程序化结构扫描 | ✅ 可复现可审计 |
| **质量门禁** | quality-leader 复核全部报告，拒绝则回流 | ✅ 机制把关 |

> JaCoCo 已预置在模板 `pom.xml`（jacoco-maven-plugin），保证每次流水线都有覆盖率报告，门禁口径统一。

---

## 五、状态与记忆

- **跨节点记忆**：`shared/projects/{project}/` 文件（design.md / 各报告 / 代码）即跨节点工作记忆
- **执行证据**：各节点产物留档（测试报告、评审、对抗报告、影响面、E2E）+ git commit [ci pass]
- **可回滚**：每节点产物可查，回流带证据重放

---

## 六、实测结果（全自动）

| 需求 | 范围 | 结果 |
|------|------|------|
| 运费计算（freight）| 1-5 节点 | ✅ 全过（57 测试）|
| 增值税计算（VAT）| 1-5 节点 | ✅ 全过（74 测试）|
| **BMI 计算** | **1-13 完整流水线** | ✅ **全过（含 JaCoCo 覆盖率、E2E、质量门禁、发布、通知 Manager 13/13）** |

---

## 七、五维能力 → AgentTeams 映射

| 维度 | 本设计 | → AgentTeams |
|------|--------|-------------|
| 角色编排 | workflow.yaml 声明节点与角色 | Team/Worker/Team Leader 原语 |
| 任务拆解 | requirement 拆解为任务 | Manager 任务拆解与调度 |
| 上下文传递 | shared/projects 文件传递 | Matrix 房间 + 结构化产物 |
| 协同执行 | 状态机 + fail_to 回流（自动驱动）| run-pipeline.py 派发 + Worker 执行 |
| 状态追踪 | 产物留档 + 通知 Manager | AgentTeams 可观测 + Matrix 房间 |
