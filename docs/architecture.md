# AgentTeams DevFlow Kit 架构说明

## 一、整体架构

基于 AgentTeams 的 Manager – Team Leader – Worker 分层架构：

```
用户（Human）
  │ 通过 Element Web 提交需求、全程可介入
  ▼
Manager（AgentTeams 框架）
  │ 接收需求、创建/调度 Agent、汇总交付
  ▼
devflow-runner（Worker · 编排）
  │ 读 workflow.yaml → 按序派发 → 维护 state.json / trace.log → fail_to 回流
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

## 二、流水线（workflow.yaml）

14 个节点，见 `workflow/workflow.yaml`。核心回流逻辑：

```
需求 → 设计 → [架构评审] → 后端编码 → [后端测试] ──失败──→ ┐
         │ 不通过→回流设计                ↓              │
         └─────────────── 前端编码 → [前端构建] ─失败─→ 缺陷定位 ←──┐
                                    ↓                      │        │
                               [评审] ─不通过─────────────→┘        │
                                    ↓                               │
                              [对抗测试] ─失败──────────────────→    │
                                    ↓                               │
                              [影响面分析]                           │
                                    ↓                               │
                                  [E2E] ─失败──────────────────→     │
                                    ↓                               │
                              [质量门禁] ─不通过─────────────────→   │
                                    ↓                               │
                                发布（git commit [ci pass]）         │
                                                        ↓ 带 defect_report 回流编码节点
```

## 三、验证机制（差异化核心）

| 机制 | 实现 | 保证 |
|------|------|------|
| 真实测试 | tester 运行 mvn test / pytest | ✅ 确定性 |
| 覆盖率 | JaCoCo / coverage 工具 | ✅ 确定性 |
| 对抗性测试 | analyst 独立生成攻击用例 | ✅ 机制隔离 |
| 缺陷定位 | analyst 基于证据 + 源码 | ⚠️ LLM + 证据 |
| 影响面分析 | 程序化结构扫描 | ✅ 可复现可审计 |

## 四、状态与记忆

- **跨节点记忆**：`shared/runs/{run-id}/` 文件（task.md / design.md / 各报告）即跨节点工作记忆
- **执行证据**：trace.log（每节点 enter/exit/rollback 带序号）+ 各节点产物留档
- **可回滚**：每节点产物可查，回流带失败证据重放

## 五、五维能力 → AgentTeams 映射

| 维度 | 本设计 | → AgentTeams |
|------|--------|-------------|
| 角色编排 | workflow.yaml 声明节点与角色 | Team/Worker/Team Leader 原语 |
| 任务拆解 | requirement 节点拆解为 task.md | Manager 任务拆解与调度 |
| 上下文传递 | shared/runs 文件传递 | Matrix 房间 + 结构化产物 |
| 协同执行 | 状态机 + fail_to 回流 | devflow-runner 调度与回流 |
| 状态追踪 | trace.log + 产物留档 | AgentTeams 可观测 + Matrix 房间 |
