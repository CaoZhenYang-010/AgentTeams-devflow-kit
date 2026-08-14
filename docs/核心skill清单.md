# DevFlow Kit 核心 Skill 清单

> 11 个业务 Skill + 1 个编排 Skill，按流水线顺序组织。
> 运行载体：AgentTeams Worker（implementer/tester/reviewer/analyst/designer 等）+ run-pipeline.py 自动驱动。

---

## 编排 Skill

### devflow-pipeline（流水线编排）

| 字段 | 内容 |
|------|------|
| **名称** | devflow-pipeline |
| **用途** | devflow-runner 读取 workflow.yaml，按序派发各节点、收集产物、fail_to 回流、推进到发布 |
| **输入/输出** | 输入：需求 + workflow.yaml；输出：各节点产物（design.md/测试报告/评审/代码/发布）|
| **调用条件** | 发起流水线运行（run-pipeline.py 或人工触发）|
| **依赖工具** | Matrix API（真提及派发）、mc（MinIO 轮询）、agt（取 Worker 房间）|
| **失败机制处理** | 节点超时重试（2 次）；失败按 fail_to 分流回流——评审类→上游产物节点（如 design）带意见重做，缺陷类→defect-locate→implementer 修复→重跑；无 fail_to 则终止并报告 |
| **安全边界** | 验证节点必须真实工具判定，不跳过任一验证；会话重置防上下文污染 |
| **复用价值** | 声明式流水线，换需求/换项目即复用（改 pipeline.json）|
| **协同流程关系** | 全局编排者，调度全部 8 个 Agent |

---

## 业务 Skill（按流水线顺序）

### 1. requirement-clarify（需求澄清）

| 字段 | 内容 |
|------|------|
| **名称** | requirement-clarify |
| **用途** | 把一句话需求拆解为可执行任务说明（目标/验收标准/技术约束）→ task.md |
| **输入/输出** | 输入：原始需求；输出：task.md（验收标准可自动断言）|
| **调用条件** | 流水线起点，收到新需求 |
| **依赖工具** | LLM（DeepSeek）|
| **失败机制处理** | 验收标准不明确 → 驱动/人工补充需求 |
| **安全边界** | 不写代码；验收标准必须可被测试脚本断言 |
| **复用价值** | 任意软件开发项目需求澄清通用 |
| **协同流程关系** | 产出喂给 designer（系统设计）|

### 2. system-design（系统设计）

| 字段 | 内容 |
|------|------|
| **名称** | system-design |
| **用途** | 产出全栈设计文档 design.md（模块划分/数据结构/核心流程/接口契约/边界处理）|
| **输入/输出** | 输入：task.md；输出：design.md |
| **调用条件** | 需求澄清后，编码前 |
| **依赖工具** | LLM |
| **失败机制处理** | 架构评审不通过 → 回流 design 修正 |
| **安全边界** | 严格遵循验收标准，不自创规则；前后端接口契约一致 |
| **复用价值** | 全栈设计模板跨项目复用 |
| **协同流程关系** | 产出喂给 architect-leader（评审）+ implementer（编码依据）|

### 3. architecture-review（架构评审）

| 字段 | 内容 |
|------|------|
| **名称** | architecture-review |
| **用途** | 编码前架构把关：评审设计是否可编码、技术债、边界 → JSON 裁决 |
| **输入/输出** | 输入：task.md + design.md；输出：arch_review.md（approved true/false）|
| **调用条件** | 系统设计后、编码前 |
| **依赖工具** | LLM（低温采样）|
| **失败机制处理** | approved:false → 回流 design 修正 |
| **安全边界** | 不写实现代码；不替代 implementer 做实现决策 |
| **复用价值** | 架构评审标准跨项目复用 |
| **协同流程关系** | 门禁角色（Team Leader），决定是否放行编码 |

### 4. tdd-coding（TDD 编码）

| 字段 | 内容 |
|------|------|
| **名称** | tdd-coding |
| **用途** | 基于设计实现后端 SpringBoot + 前端 Vue3，先写测试再写实现 |
| **输入/输出** | 输入：task.md + design.md + 失败证据；输出：业务代码 + JUnit/Vue 组件 |
| **调用条件** | 设计评审通过后（backend/frontend 两个节点）|
| **依赖工具** | LLM + 自定义镜像（Java/Maven/Node）|
| **失败机制处理** | 回流时按 defect_report/quality_notes 带证据精准修复（含配置问题）|
| **安全边界** | 不判定自己测试是否通过（tester 客观判定）；不评审自己 |
| **复用价值** | SpringBoot/Vue 编码模式跨项目复用 |
| **协同流程关系** | 产出喂给 tester（验证）+ reviewer（评审）|

### 5. test-run（测试/构建/E2E 执行）

| 字段 | 内容 |
|------|------|
| **名称** | test-run |
| **用途** | 真实运行 mvn test（+JaCoCo 覆盖率）、npm build、Playwright E2E |
| **输入/输出** | 输入：implementer 产物；输出：test_report.txt / frontend_build_report.txt / e2e_report.txt |
| **调用条件** | 后端编码后、前端编码后、发布前（E2E）|
| **依赖工具** | Maven/JaCoCo、npm、Playwright（chromium）——全确定性工具 |
| **失败机制处理** | 判定只看真实结果（BUILD SUCCESS/Failures:0）；失败 → defect-locate |
| **安全边界** | 不判断代码逻辑好坏；判定权交给真实断言与覆盖率 |
| **复用价值** | 测试执行器跨项目复用 |
| **协同流程关系** | 产出喂给 quality-leader（门禁）+ defect-locate（失败时）|

### 6. code-review（代码评审）

| 字段 | 内容 |
|------|------|
| **名称** | code-review |
| **用途** | 独立评审全栈实现是否满足需求/落地设计 → JSON 裁决 |
| **输入/输出** | 输入：task/design/源码/测试；输出：review_notes.md（approved true/false）|
| **调用条件** | 编码+测试完成后 |
| **依赖工具** | LLM（低温采样）|
| **失败机制处理** | approved:false → defect-locate |
| **安全边界** | 不修改代码；不自行通过；独立于 implementer |
| **复用价值** | 代码评审标准跨项目复用 |
| **协同流程关系** | 独立把关角色，裁决喂给回流/门禁 |

### 7. adversarial-test（对抗性测试）

| 字段 | 内容 |
|------|------|
| **名称** | adversarial-test |
| **用途** | 不信任实现者自写测试，独立构造攻击性用例（边界/非法/组合/精度）|
| **输入/输出** | 输入：验收标准 + 源码；输出：adversarial_test_report.txt |
| **调用条件** | 代码评审后，独立验证 |
| **依赖工具** | LLM + Maven（真实运行对抗用例）|
| **失败机制处理** | 暴露缺陷 → defect-locate |
| **安全边界** | 不参考/复制实现者自写测试（对抗自洽盲区）|
| **复用价值** | 对抗测试方法论跨项目复用 |
| **协同流程关系** | 独立验证，暴露实现者盲区 → 回流缺陷定位 |

### 8. defect-locate（缺陷定位）

| 字段 | 内容 |
|------|------|
| **名称** | defect-locate |
| **用途** | 基于失败证据（测试/评审/门禁意见）+ 源码，定位到文件/行/函数 |
| **输入/输出** | 输入：失败证据 + 源码；输出：defect_report.md（root_cause/evidence/fix_suggestion）|
| **调用条件** | 任一验证节点失败时 |
| **依赖工具** | LLM + 失败证据 |
| **失败机制处理** | 产出报告 → implementer 带证据修复 → 重跑 |
| **安全边界** | 定位是"建议"；正确性由 tester/reviewer 兜底 |
| **复用价值** | 缺陷定位方法论跨项目复用 |
| **协同流程关系** | 回流中枢，连接失败节点与 implementer 修复 |

### 9. impact-analysis（影响面分析）

| 字段 | 内容 |
|------|------|
| **名称** | impact-analysis |
| **用途** | 发布前分析改动影响范围（模块依赖/受影响模块/回归建议）|
| **输入/输出** | 输入：源码结构；输出：impact_report.md（程序化）|
| **调用条件** | 发布前 |
| **依赖工具** | 程序化结构扫描（**不调 LLM**）|
| **失败机制处理** | 程序化产出，可复现可审计；无失败概念 |
| **安全边界** | 只分析项目内模块，不追踪第三方库 |
| **复用价值** | 影响面工具跨项目复用 |
| **协同流程关系** | 产出喂给 quality-leader（门禁）|

### 10. quality-gate（质量门禁）

| 字段 | 内容 |
|------|------|
| **名称** | quality-gate |
| **用途** | 发布前复核全部报告（测试/覆盖率/对抗/E2E/影响面）→ JSON 裁决 |
| **输入/输出** | 输入：全部验证报告；输出：quality_notes.md（approved true/false）|
| **调用条件** | 全部验证通过后、发布前 |
| **依赖工具** | LLM + 全部真实报告 |
| **失败机制处理** | approved:false → 回流 defect-locate → implementer 修复 → 重跑门禁 |
| **安全边界** | 基于真实证据裁决；不通过不放行发布 |
| **复用价值** | 质量门禁标准跨项目复用 |
| **协同流程关系** | 最后把关（Team Leader），决定是否发布 |

### 11. verify-release（验证发布）

| 字段 | 内容 |
|------|------|
| **名称** | verify-release |
| **用途** | 全部通过后 git 提交发布（commit [ci pass]）|
| **输入/输出** | 输入：全部产物；输出：git commit |
| **调用条件** | 质量门禁通过后 |
| **依赖工具** | git（**不调 LLM**）|
| **失败机制处理** | git 身份未配置自动补；nothing to commit 视为成功 |
| **安全边界** | 提交信息带 [ci pass] 标记测试通过；不绕过门禁 |
| **复用价值** | 发布流程通用 |
| **协同流程关系** | 流水线终点，之后通知 Manager |

---

## Skill 协同关系总览

```
requirement-clarify → system-design → architecture-review → tdd-coding → test-run
      (需求)           (设计)          (架构门禁)          (编码)      (验证)
                                                              ↓
                       quality-gate ← impact-analysis ← defect-locate ← code-review/adversarial-test
                       (发布门禁)     (影响面)        (缺陷中枢)    (独立评审/对抗)
                                                              ↓
                                                         verify-release（发布）
```
