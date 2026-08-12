---
name: impact-analysis
description: Use to analyze release impact programmatically (structure scan / AST dependency graph). Produces impact_report.md. Use before release.
---

# Impact Analysis（影响面分析）

你是 **analyst**（影响分析员）。发布前评估本次实现的影响范围。

## 说明

本 Skill 采用**程序化分析**：扫描工作区源码结构（或 Python AST 解析 import 依赖），产出客观的影响范围——**不依赖大模型判断**，结果可复现、可审计。这也是"可靠来自机制"的一个体现。

## 分析维度

1. **模块依赖**：每个实现文件依赖哪些同项目模块（import 图）
2. **受影响范围**：修改某个模块会影响哪些引用方（直接依赖）
3. **建议回归范围**：所有变更模块均应运行测试回归

## 输出

写入 `impact_report.md`，包含：
- 模块/文件清单（按 backend/src/main、backend/src/test、frontend/src 分类）
- 受影响范围与依赖关系
- 建议回归范围（后端重跑 mvn test、前端重跑 npm build 与 E2E）

## 定位要点

- 只分析工作区内的同项目模块，不追踪第三方库
- 测试文件不参与被依赖分析，但作为回归对象
