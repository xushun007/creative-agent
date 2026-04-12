---
name: Verify Code Change
description: 验证代码变更是否符合预期
argument-hint: "[target-files|feature|bugfix] [test-scope]"
allowed-tools: bash, read, glob, grep, list
user-invocable: true
---

你正在执行工程级代码验证任务。

你的目标是给出可信的验证结论，而不是机械地“跑几个命令”。
默认不要修改代码；你的职责是验证、记录证据、说明风险。

Base directory for this skill: ${CTV_SKILL_DIR}

## 参考资源

按需读取以下文件，不要一开始全部展开。只有当你需要验证策略或结果结构时才读取：

- `${CTV_SKILL_DIR}/examples/checklist.md`
- `${CTV_SKILL_DIR}/examples/strategies.md`

## 验证步骤

1. 先明确这次改动试图实现、修复或重构什么。
2. 找到最小且最相关的验证入口：
   - 定向单测
   - 目标脚本
   - 最短启动路径
   - 手工复现场景
3. 优先验证：
   - 主成功路径
   - 关键失败路径
   - 边界条件
   - 改动波及的旧行为
4. 记录每个验证动作的结果，不要只给结论。
5. 如果环境或依赖阻塞验证，明确写出阻塞点和未覆盖范围。

## 输出要求

- 先给 `Verification Summary`
- 然后列出 `Checks Run`
- 再列出 `Pass / Fail / Not Run`
- 最后给 `Residual Risks`

结论必须区分：
- 已验证通过
- 未验证但高概率成立
- 未验证且存在风险
- 被环境阻塞

## 用户请求

${ARGUMENTS}

如果仓库里存在明显的测试入口，优先跑最小相关集合，而不是全量测试。
