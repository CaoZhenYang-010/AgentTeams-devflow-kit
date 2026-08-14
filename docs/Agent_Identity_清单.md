# DevFlow Kit — Agent Identity 清单

- **架构基座**：AgentTeams（原名 HiClaw）——赛事指定协同设计基点
- **当前形态**：基于 AgentTeams 框架，Manager–Team Leader–Worker **三层完整落地**（8 个职能 Agent）
- **流水线**：design → architect-leader → backend-coding → backend-test → frontend-coding → frontend-build → review → adversarial-test → defect-locate → impact-analysis → e2e → quality-leader → release
- **自动化**：`run-pipeline.py` 一键驱动全流程（发需求 → 13 节点自动跑完 → 发布 → 通知 Manager）

---

## 协同关系总览

```
design ──→ architect-leader ──→ backend-coding ──→ backend-test ──→ frontend-coding ──→ frontend-build
(designer)    (架构 Leader)      (implementer)     (tester)         (implementer)       (tester)
                                        │                │                                  │
                                        └── 失败 ──→ defect-locate ←── 失败 ──┐           │
                                                                  (analyst)   │           │
                                        review ──→ adversarial-test ──失败──┘           │
                                        (reviewer)   (analyst)                           │
                                        │             │                                  │
                                        └── 失败 ─────┘           impact-analysis (analyst)
                                                              │
                                                              ▼
                                                         e2e (tester)
                                                              │
                                                              ▼
                                                       quality-leader（质量 Leader）
                                                              │ 不通过 → 回流 implementer 修复
                                                              ▼
                                                          release（devflow-runner）
                                                              │
                                                              ▼
                                                    通知 Manager（通过节点数）
```

**回流规则**：
- architect-leader 不通过 → 回流 design
- review / test / build / adversarial-test / e2e 任一失败 → defect-locate → implementer 带证据修复 → 重跑
- quality-leader 门禁不通过 → defect-locate → implementer 修复（含配置问题，如 JaCoCo/npm）

---

## 1. devflow-runner（流水线编排 / 发布者）

| 属性 | 说明 |
|---|---|
| **身份属性** | AgentTeams Worker：读 workflow.yaml、驱动流水线、执行发布 |
| **承担节点** | release（git commit [ci pass]）|
| **Skill** | devflow-pipeline、verify-release |
| **是否调用 LLM** | 编排逻辑由 `run-pipeline.py` 程序化驱动；release 不调 LLM（git 提交）|
| **能力边界（能）** | 按流水线派发、收集产物、fail_to 回流、发布准入 |
| **能力边界（不能）** | 不写业务代码；不评审代码；不判定测试结果 |
| **协同关系** | 接收需求 → 向各 Worker 派发任务 → 收集产物 → 发布 → 通知 Manager |

## 2. architect-leader（架构 Leader，Team Leader 层）

| 属性 | 说明 |
|---|---|
| **身份属性** | AgentTeams Team Leader：编码前架构把关 |
| **承担节点** | architect-leader |
| **Skill** | architecture-review |
| **是否调用 LLM** | 是 |
| **能力边界（能）** | 评审 design.md 是否符合需求、是否可编码、技术债；不过则回流 design |
| **能力边界（不能）** | 不写实现代码；不替代 implementer 做实现决策 |
| **协同关系** | 输入 ← design（design.md）；裁决 → 回流 design 或放行编码 |

## 3. quality-leader（质量 Leader，Team Leader 层）

| 属性 | 说明 |
|---|---|
| **身份属性** | AgentTeams Team Leader：发布前质量门禁 |
| **承担节点** | quality-leader |
| **Skill** | quality-gate |
| **是否调用 LLM** | 是 |
| **能力边界（能）** | 复核测试/覆盖率/对抗/E2E/影响面结果，做发布前裁决；不通过 → 回流缺陷定位修复 |
| **能力边界（不能）** | 不改代码；不替代 tester 的客观执行 |
| **协同关系** | 输入 ← test_report / build_report / adversarial_report / e2e_report / impact_report；裁决 → 放行发布或回流 |

## 4. designer（系统设计者）

| 属性 | 说明 |
|---|---|
| **身份属性** | AgentTeams Worker：软件架构师 |
| **承担节点** | design |
| **Skill** | system-design |
| **是否调用 LLM** | 是 |
| **能力边界（能）** | 产出 design.md：模块划分、数据结构、核心流程、边界处理、接口定义 |
| **能力边界（不能）** | 不写实现代码；不得自创业务规则——严格遵循需求验收标准 |
| **协同关系** | 输入 ← 需求；产出 → architect-leader（把关）、implementer（编码依据）|

## 5. implementer（实现工程师）

| 属性 | 说明 |
|---|---|
| **身份属性** | AgentTeams Worker：研发工程师，TDD 编码（后端 SpringBoot + 前端 Vue3）|
| **承担节点** | backend-coding、frontend-coding、回流修复 |
| **Skill** | tdd-coding |
| **是否调用 LLM** | 是 |
| **能力边界（能）** | 产出多文件实现 + 测试；按失败证据/门禁意见精准修复（含配置问题）|
| **能力边界（不能）** | 不判定自己测试是否通过（tester 客观判定）；不评审自己（reviewer 独立把关）|
| **协同关系** | 输入 ← design.md / 失败证据；产出 → tester、reviewer |

## 6. reviewer（独立评审者）

| 属性 | 说明 |
|---|---|
| **身份属性** | AgentTeams Worker：资深代码评审，独立于 implementer |
| **承担节点** | review |
| **Skill** | code-review |
| **是否调用 LLM** | 是（低温采样）|
| **能力边界（能）** | 审查设计落地、业务规则、代码正确性、测试充分性；输出 JSON 裁决 |
| **能力边界（不能）** | 不修改代码；不自行通过；不通过时由缺陷定位接手 |
| **协同关系** | 输入 ← design/源码/测试；裁决 → 回流或放行 |

## 7. tester（验证执行者）

| 属性 | 说明 |
|---|---|
| **身份属性** | AgentTeams Worker：验证执行（后端测试/前端构建/E2E）|
| **承担节点** | backend-test、frontend-build、e2e |
| **Skill** | test-run |
| **是否调用 LLM** | 是（作为 OpenClaw Agent 编排），但**判定只依赖真实工具**（mvn test、npm build、Playwright）|
| **能力边界（能）** | 真实运行测试 + **JaCoCo 覆盖率**、前端构建、Playwright E2E；产出报告 |
| **能力边界（不能）** | 不判断代码逻辑好坏；判定只看真实结果 |
| **协同关系** | 输入 ← implementer 产物；产出 → quality-leader、defect-locate |

## 8. analyst（分析专家，一职三角）

| 属性 | 说明 |
|---|---|
| **身份属性** | AgentTeams Worker：对抗测试员 / 缺陷分析员 / 影响分析员 |
| **承担节点** | adversarial-test、defect-locate、impact-analysis |
| **Skill** | adversarial-test、defect-locate、impact-analysis |
| **是否调用 LLM** | 对抗测试、缺陷定位调；影响面分析**不调**（程序化结构扫描）|
| **能力边界（能）** | ① 独立生成攻击性用例（对抗自洽盲区）；② 基于失败证据定位到文件/行/函数；③ 影响范围分析 |
| **能力边界（不能）** | 不写业务实现；定位报告是"建议"（正确性由 tester/reviewer 兜底）|
| **协同关系** | 对抗输入 ← 源码/验收标准；缺陷定位输入 ← 失败证据，产出 → implementer（回流）；影响面产出 → quality-leader |

---

## 全自动流水线驱动（run-pipeline.py）

```
读 pipeline.json
  → 重置所有 Worker 会话（/new，清除跨需求污染）
  → 逐节点：Matrix 真提及派发 → MinIO 轮询产物 → 内容关键词校验
  → 通过推进 / 超时重试 / 失败按 fail_to 分流回流（评审类 → 上游产物节点带意见重做；缺陷类 → defect-locate → implementer 修复 → 重跑）
  → 全部完成 → 通知 Manager（通过节点数）
```

**关键技术**：Matrix `m.mentions` 真提及、file-sync 同步到 MinIO、success 关键词判定、JaCoCo 覆盖率预置、会话重置。

## 五维能力 → AgentTeams 框架映射（手册要求）

| 维度 | 本设计 | AgentTeams 落地 |
|---|---|---|
| 角色编排 | 8 个 Agent 角色 | Team + Team Leader + Worker 定义 |
| 任务拆解 | 需求 → 各节点任务 | run-pipeline.py 自动派发 + Worker 执行 |
| 上下文传递 | shared/projects 文件 + 失败证据 | Matrix 房间 + 结构化产物 |
| 协同执行 | 状态机 + fail_to 回流（自动驱动）| run-pipeline.py 派发 + Worker 执行 |
| 状态追踪 | 产物留档 + 通知 Manager | Matrix 房间状态 + AgentTeams 可观测 |

## 划分原则

1. **实现与验证分离**：implementer 不自评、不自审——测试与评审由独立角色承担
2. **验证环节程序化**：mvn test、覆盖率、npm build、E2E、影响面由真实工具/程序判定
3. **对抗审查**：analyst 独立生成攻击性测试，对抗自写测试的自洽盲区
4. **流程硬约束**：节点顺序、回流、跳转由 `run-pipeline.py` 程序化强制，LLM 无权跳过验证
5. **质量门禁把关**：quality-leader 基于真实证据裁决，不通过则回流修复，阻断带问题发布
