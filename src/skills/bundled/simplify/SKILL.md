---
name: Simplify Code
description: 审查代码以发现可复用模式和改进机会
argument-hint: "[file] [focus]"
allowed-tools: read, grep, glob, edit, write
user-invocable: true
---

你正在执行代码简化任务。

## 任务目标

审查已修改的代码，识别可重用的模式，改进代码质量。

## 检查清单

1. **提取重复代码**
   - 寻找模式相似的代码块
   - 提取为共享函数或工具

2. **简化逻辑**
   - 简化复杂的条件判断
   - 移除冗余代码

3. **改进命名**
   - 变量/函数名是否清晰表达意图

4. **添加文档**
   - 复杂逻辑添加注释
   - 公共 API 添加文档字符串

5. **测试覆盖**
   - 新增代码是否有测试
   - 边界条件是否覆盖

## 用户请求

${ARGUMENTS}

请执行简化并报告改动。
