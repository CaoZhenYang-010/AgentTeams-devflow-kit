# template-project —— 被流水线开发的全栈示例工程

这是 **DevFlow 流水线要"开发"的目标项目**（层 2：Worker 团队实际操作的对象），
不是流水线本身（层 1）。

## 内容

真实的 SpringBoot 后端 + Vue3 前端骨架：

```
template-project/
├── backend/     # SpringBoot 2.7.18 + MyBatis + H2（Java 17）
│   ├── pom.xml
│   └── src/main/java/com/example/app/
│       ├── Application.java          # 启动类
│       └── config/CorsConfig.java    # 跨域已放开
│   └── src/main/resources/application.yml   # 端口 8080、H2、MyBatis
└── frontend/    # Vue3 + Element Plus + Vite
    ├── package.json / package-lock.json
    ├── vite.config.js                # /api 代理到 8080
    └── src/
        ├── main.js                   # 已 use ElementPlus
        └── App.vue                   # 欢迎页骨架
```

## 使用方式

流水线运行时，devflow-runner 把本模板复制到共享区：

```
shared/runs/{run-id}/work/backend + work/frontend
```

implementer 在此基底上生成业务代码与测试，tester 在此执行测试/构建/E2E。

## 说明

- **不得修改模板骨架文件**（implementer 的 tdd-coding Skill 会遵守此约定）
- 骨架仅含源码，不含 `target/`、`node_modules/` 等构建产物（提交时由 .gitignore 排除）
- 首次运行时需 `mvn` / `npm install` 恢复依赖
