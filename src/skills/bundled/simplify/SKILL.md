---
name: Simplify Code
description: 在不改变行为的前提下简化代码结构并降低复杂度
argument-hint: "[target-files|module] [goal]"
allowed-tools: read, grep, glob, list, edit, write, bash
user-invocable: true
---

你正在执行工程级代码简化任务。

你的目标是降低复杂度、去重、改善局部结构，并保持外部行为不变。
不要为了“更优雅”而引入不必要抽象。

Base directory for this skill: ${CTV_SKILL_DIR}

## 参考资源

按需读取以下文件，不要全部展开。只在需要判断重构类型或安全边界时读取：

- `${CTV_SKILL_DIR}/examples/refactor-patterns.md`
- `${CTV_SKILL_DIR}/examples/safety-rules.md`

## 工作方式

- 先定位用户指定的模块、文件或重复模式。
- 优先做局部、可解释、低风险的改动。
- 如果需要跨多个模块重构，先说明理由，再实施。
- 改完后尽量运行最小相关验证命令。

## 优先处理的问题

1. 重复逻辑可以被提取。
2. 分支结构过深、嵌套过多。
3. 中间层、包装层、参数传递明显冗余。
4. 命名掩盖意图，增加理解成本。
5. 过长函数可以拆成更清晰的私有辅助函数。

## 不要做的事

- 不要随意改公共接口。
- 不要顺手做无关重写。
- 不要引入新的框架式抽象。
- 不要在没有理由的情况下扩大改动面。

## 输出要求

- 先简述你要简化的点。
- 然后实施改动。
- 最后给：
  - `What Changed`
  - `Why It Is Simpler`
  - `Validation`
  - `Residual Risk`

## 用户请求

${ARGUMENTS}

如果没有找到明确收益的简化点，就直接说明“不建议为了形式上的简洁而修改”。
