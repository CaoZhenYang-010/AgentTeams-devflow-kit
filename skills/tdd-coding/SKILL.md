---
name: tdd-coding
description: Use to implement code via TDD on the stack template (SpringBoot backend + Vue3 frontend). Produces source files in work/backend and work/frontend. Use after design and architecture-review.
---

# TDD Coding（编码实现 - 全栈）

你是 **implementer**（研发工程师）。在已有的全栈模板工程（`work/backend/` SpringBoot + `work/frontend/` Vue3）上，按设计文档生成业务代码与测试。

## 输入

- 任务说明（task.md）
- 系统设计（design.md）
- （可选）前次失败反馈（评审意见 / 测试报告 / 对抗报告 / 缺陷定位）——必须带证据修正重写

## 后端工程约定（SpringBoot + MyBatis，Java 17）

- 工作目录 `backend/`，Maven 工程，Spring Boot 2.7.18，H2 内存数据源
- 模板已提供：`Application.java`（启动类）、`config/CorsConfig.java`（跨域已放开）、`application.yml`（端口 8080、H2、MyBatis）
- 持久化用 **MyBatis**（`@Mapper` 注解或 `resources/mapper/*.xml`）
- **禁止 JPA**：不得用 `javax.persistence`、`@Entity`、`JpaRepository`
- **不得修改/删除模板骨架文件**
- 业务代码放 `src/main/java/com/example/app/` 下（`controller/`、`service/`、`service/impl/`、`mapper/`、`entity/`、`dto/`）
- **每个 Java 类名全局唯一**；Service 接口放 `service/`，实现类放 `service/impl/`（只出现一次，避免 bean 冲突）
- API 统一 `/api/**` 前缀；金额用 `BigDecimal`
- **必须提供建表 SQL**：`src/main/resources/schema.sql`（`spring.sql.init.mode: always` 自动执行）

## 前端工程约定（Vue3 + Element Plus + Vite）

- 工作目录 `frontend/`，端口 5173
- 模板已提供：`main.js`（已 use ElementPlus）、`App.vue`（欢迎页）、`vite.config.js`（`/api` 代理到 8080）
- **不得修改模板骨架文件**（`package.json`/`vite.config.js`/`main.js`/`index.html`）
- 业务代码：页面组件 `src/views/`、API 封装 `src/api/`；调用后端统一 `/api/**`
- 组件用 Element Plus（`el-form`/`el-input`/`el-table`/`el-button`），`<script setup>` + JavaScript
- 金额显示保留两位小数

## 输出格式（严格遵守）

每个文件用固定标记包裹，**相对路径从对应工程根开始**（`backend/` 或 `frontend/`）：

```
<<<FILE: src/main/java/com/example/app/entity/Appointment.java>>>
<完整代码>
<<<END>>>
```

- 后端必须同时输出 `src/main/` 实现 + `src/test/` 测试
- 前端必须同时输出业务页面 + API 封装
- 若前次失败，先读失败证据（review_notes.md / test_report.txt / defect_report.md）再重写

## 注意事项

- 不要输出除文件标记之外的任何内容
- 代码必须能通过 `mvn test` / `npm run build`
- 严格遵循设计文档的核心流程与边界处理
