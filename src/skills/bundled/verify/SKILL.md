---
name: Verify Code Change
description: 验证代码变更是否符合预期
argument-hint: "[file] [options]"
allowed-tools: bash, read, write, glob, grep, edit
user-invocable: true
---

你正在执行代码变更验证任务。

Base directory for this skill: ${CTV_SKILL_DIR}

## 任务目标

验证代码变更是否符合预期，按预期工作。

## 参考资源

按需读取以下文件，不要一开始全部展开：

- `${CTV_SKILL_DIR}/examples/checklist.md`
- `${CTV_SKILL_DIR}/examples/strategies.md`

## 验证步骤

1. 理解代码变更的目的和实现
2. 运行相关测试用例
3. 手动验证功能（如果需要）
4. 记录验证结果

优先根据仓库实际情况选择最小验证集合；如果没有自动化验证入口，明确记录验证缺口和风险。

## 用户请求

${ARGUMENTS}

请开始验证，并在完成后报告结果。
