---
name: Review Code Change
description: 审查代码变更，提出改进建议
argument-hint: "[file] [focus-area]"
allowed-tools: read, grep, glob
user-invocable: true
---

你正在执行代码审查任务。

## 审查要点

请从以下角度审查代码：

1. **代码质量**
   - 代码风格是否一致
   - 命名是否清晰
   - 是否有重复代码

2. **正确性**
   - 逻辑是否正确
   - 边界条件是否处理
   - 是否有潜在 bug

3. **安全性**
   - 是否有安全漏洞
   - 是否有敏感信息泄露
   - 输入验证是否充分

4. **性能**
   - 是否有性能问题
   - 是否有不必要的重复计算

5. **可维护性**
   - 模块划分是否合理
   - 依赖是否清晰

## 用户请求

${ARGUMENTS}

请提供具体的改进建议。
