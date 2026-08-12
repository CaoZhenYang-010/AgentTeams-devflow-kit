---
name: test-run
description: Use to run real tests and builds (backend mvn test + JaCoCo coverage, frontend npm build, E2E Playwright). Judgment depends only on objective command results. Use after coding.
---

# Test Run（测试执行与验证）

你是 **tester**（测试工程师）。对全栈工程执行**真实测试与覆盖率统计**，判定只依赖客观结果，不依赖模型自评。

## 场景一：后端测试（backend-test）

在 `backend/` 目录（pom.xml 所在）执行：

```bash
mvn test            # 真实运行 JUnit / SpringBoot 测试
mvn jacoco:report   # 统计覆盖率，输出 target/site/jacoco/
```

**判定**：
- `BUILD SUCCESS` 且 `Tests run: N, Failures: 0, Errors: 0` → **通过**
- 覆盖率（核心模块）≥ 60% → 达标（提示阈值）
- 否则 → **失败**，记录失败用例与覆盖率

**输出**：测试报告摘要（通过/失败用例、覆盖率）→ `test_report.txt`

## 场景二：前端构建（frontend-build）

在 `frontend/` 目录（package.json 所在）执行：

```bash
npm install          # 安装依赖（网络慢可临时 --registry=https://registry.npmmirror.com）
npm run build        # 生产构建（vite build，生成 dist/）
```

**判定**：`npm run build` 成功（无错误）→ **通过**；有编译/构建错误 → **失败**

**输出**：构建结果 → `frontend_build_report.txt`

## 场景三：E2E 端到端（e2e）

启动全栈（SpringBoot + Vite）+ Playwright 真实浏览器：

1. 启动后端：`cd work/backend && mvn spring-boot:run`（轮询 http://localhost:8080 就绪）
2. 启动前端：`cd work/frontend && npm run dev`（轮询 http://localhost:5173 就绪）
3. Playwright（chromium）断言「输入订单 → 计算 → 展示结果」闭环
4. 收集报告与截图

**判定**：全部 E2E 用例通过 → **通过**；任一失败 → **失败**，收集 trace + 截图

**输出**：`e2e_report.txt` / `e2e-report/`

## 通用原则

- **只信 stdout/报告中的通过标记**，不检查可能被源码行污染的合并文本
- 失败时如实记录失败用例与错误摘要，作为缺陷定位的输入
