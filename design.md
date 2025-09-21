# Creative Agent 集成设计文档

## 1. 项目概述

本文档描述了将现有项目中的两套架构进行集成的设计方案：
- **新架构**: `src/cli`, `src/core` - 基于事件驱动的Codex引擎
- **原架构**: `src/core`, `src/tools` - 基于CodexEngine的系统

集成目标是保留两套架构的优点，创建一个统一、高效的AI编程助手系统。

## 2. 现状分析

### 2.1 新架构 (src/cli + src/core)

**优点：**
- 事件驱动架构，解耦性好
- 完整的CLI交互界面，用户体验友好
- 支持异步操作和实时事件流
- 内置批准机制和沙箱安全策略
- 完整的会话管理和token统计

**核心组件：**
- `CodexEngine`: 核心引擎，管理会话生命周期
- `Session`: 会话管理，处理ReAct循环
- `CodexCLI`: 命令行界面，事件处理
- `Config`: 配置管理系统

**局限性：**
- 工具系统相对简单，只有4个基础工具
- 工具执行器功能有限
- 缺乏丰富的工具生态

### 2.2 原架构 (src/agent + src/tools)

**优点：**
- 完整的工具注册系统，支持12+种工具
- 强大的工具协作模式
- 灵活的工具执行器和参数验证
- 多轮推理支持
- 丰富的工具生态（bash, edit, file, web等）

**核心组件：**
- `CodexEngine`: 基于事件驱动的智能引擎
- `AgentTurn`: 单次交互封装
- `ToolRegistry`: 工具注册管理
- `ToolExecutor`: 工具执行引擎

**局限性：**
- CLI界面相对简单
- 缺乏完整的事件系统
- 配置管理不够完善

## 3. 集成设计方案

### 3.1 设计原则

1. **原地重构**: 直接修改现有类，不创建新的Enhanced类
2. **保持精简**: 最小化修改，避免过度设计
3. **事件驱动适配**: AgentTurn系统适配现有的event和submission循环
4. **工具系统集成**: 无缝集成原架构的工具注册系统
5. **向后兼容**: 保持现有接口和配置不变

### 3.2 架构设计

```
┌─────────────────┐
│   CLI Main      │  <- 保持不变，主入口
├─────────────────┤
│  CodexEngine    │  <- 保持不变，核心引擎
├─────────────────┤
│    Session      │  <- 原地重构，集成Turn能力
├─────────────────┤
│ ToolRegistry    │  <- 直接使用原有工具系统
└─────────────────┘
```

### 3.3 核心集成点

#### 3.3.1 Session原地重构
在现有`Session`类中直接集成AgentTurn能力：
- 保留现有的事件驱动机制和ReAct循环
- 替换简单工具执行器为完整的ToolRegistry系统
- 适配AgentTurn的工具调用格式到现有的submission处理流程

#### 3.3.2 ModelClient工具Schema集成
修改`ModelClient.get_tools_schema()`方法：
- 从`ToolRegistry.get_tools_dict()`获取动态工具定义
- 保持消息管理职责不变
- 支持所有注册工具的自动发现

#### 3.3.3 消息流程保持不变
- `ModelClient`继续负责对话历史管理
- `Session`继续使用`ModelClient`进行LLM交互
- 工具调用结果仍通过`add_tool_message`添加到对话历史

## 4. 详细实现计划

### 4.1 第一阶段：基础集成

#### 4.1.1 ModelClient工具Schema重构
修改`ModelClient.get_tools_schema()`方法，从工具注册系统获取schema：
```python
def get_tools_schema(self) -> List[Dict[str, Any]]:
    """获取工具模式定义 - 从工具注册系统动态获取"""
    from tools.registry import get_global_registry
    
    registry = get_global_registry()
    tools_dict = registry.get_tools_dict(enabled_only=True)
    
    # 转换为OpenAI工具格式
    openai_tools = []
    for tool in tools_dict:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        }
        openai_tools.append(openai_tool)
    
    return openai_tools
```

#### 4.1.2 Session类原地重构
直接修改现有`Session`类，集成工具注册系统：
```python
class Session:
    def __init__(self, config: Config):
        # 保留现有初始化代码...
        
        # 集成工具注册系统（替换简单工具执行器）
        from tools.registry import get_global_registry
        self.tool_registry = get_global_registry()
        
        # 保留现有的其他属性...
```

#### 4.1.3 工具调用流程适配
修改现有的`_handle_tool_calls`方法，使用ToolRegistry：
```python
async def _handle_tool_calls(self, submission_id: str, tool_calls: List[Dict[str, Any]]):
    """使用工具注册系统处理工具调用"""
    from tools.base_tool import ToolContext
    
    for tool_call in tool_calls:
        tool_name = tool_call["function"]["name"]
        call_id = tool_call["id"]
        arguments = json.loads(tool_call["function"]["arguments"])
        
        # 创建工具执行上下文
        context = ToolContext(
            session_id=self.session_id, 
            message_id=submission_id, 
            agent="Session",
            call_id=call_id
        )
        
        # 使用工具注册系统执行
        result = await self.tool_registry.execute_tool(tool_name, arguments, context)
        
        # 格式化结果并添加到消息历史
        if result:
            result_text = result.output
            self.model_client.add_tool_message(call_id, result_text)
        else:
            self.model_client.add_tool_message(call_id, "工具执行失败")
        
        # 发送工具执行事件（保持现有事件格式）...
```

#### 4.1.4 消息流程集成验证
确保消息管理流程正确集成：
```python
# 在Session的ReAct循环中：
async def _handle_user_input(self, submission: Submission):
    # 1. 添加用户消息到ModelClient
    self.model_client.add_user_message(user_text)
    
    # 2. 获取AI响应（ModelClient自动使用新的工具schema）
    response = await self.model_client.chat_completion()
    
    # 3. 添加assistant消息到ModelClient
    self.model_client.add_assistant_message(response.content, response.tool_calls)
    
    # 4. 处理工具调用（使用新的工具注册系统）
    if response.tool_calls:
        await self._handle_tool_calls(submission.id, response.tool_calls)
    
    # 5. 继续ReAct循环...
```

### 4.2 第二阶段：功能优化

#### 4.2.1 工具执行事件增强
- 为工具执行添加详细的进度事件
- 支持工具执行的实时状态反馈
- 集成现有的批准机制与工具系统

#### 4.2.2 错误处理统一
- 统一工具执行错误的事件格式
- 改进错误恢复机制
- 保持现有的错误处理逻辑

#### 4.2.3 性能优化
- 优化工具调用的性能开销
- 减少不必要的对象创建
- 保持系统响应性

### 4.3 第三阶段：系统完善

#### 4.3.1 系统稳定性
- 完善异常处理和恢复机制
- 添加系统监控和日志
- 确保长时间运行的稳定性

#### 4.3.2 文档和测试
- 更新API文档
- 完善单元测试和集成测试
- 性能基准测试

## 5. 文件结构调整

### 5.1 目录结构
```
src/
├── cli/
│   └── main.py              # 保持不变，主CLI入口
├── core/
│   ├── config.py           # 保持不变或微调
│   ├── codex_engine.py     # 保持不变
│   ├── session.py          # 原地重构，集成工具系统
│   ├── model_client.py     # 保持不变
│   └── protocol.py         # 保持不变
├── agent/
│   ├── turn_based_agent.py # 保留，可选使用
│   └── turn.py             # 适配事件驱动，可选集成
├── tools/
│   ├── registry.py         # 保持不变，直接使用
│   ├── base_tool.py        # 保持不变
│   ├── executor.py         # 可能需要微调以适配Session
│   └── [其他工具文件]      # 完全保持不变
└── utils/
    └── [工具函数]          # 保持不变
```

### 5.2 主要修改文件

1. **src/core/session.py** - 原地集成工具注册系统
2. **src/agent/turn.py** - 可选：适配事件驱动模式
3. **src/tools/executor.py** - 可能需要微调（如果有冲突）

## 6. 兼容性保证

### 6.1 API兼容性
- 保持现有CLI命令接口不变
- 保持配置文件格式兼容
- 工具接口保持向后兼容

### 6.2 功能兼容性
- 支持原有的所有工具
- 保持原有的交互模式
- 保留所有配置选项

## 7. 测试策略

### 7.1 单元测试
- Session功能测试
- 工具集成测试
- 配置系统测试

### 7.2 集成测试
- CLI交互测试
- 多轮对话测试
- 工具执行流程测试

### 7.3 性能测试
- 响应时间测试
- 内存使用测试
- 并发处理测试

## 8. 部署和迁移

### 8.1 渐进式部署
1. 先部署基础集成版本
2. 逐步启用增强功能
3. 最终完全迁移到新架构

### 8.2 数据迁移
- 配置文件自动迁移
- 会话数据格式转换
- 工具配置迁移

## 9. 风险评估

### 9.1 技术风险
- **中等**: 两套架构集成复杂度
- **低**: 工具接口兼容性问题
- **低**: 性能影响

### 9.2 缓解措施
- 分阶段实施，降低集成风险
- 完整的测试覆盖
- 保留原架构作为备选方案

## 10. 时间计划

- **第一阶段** (3-5天): Session原地重构，集成工具注册系统
- **第二阶段** (2-3天): 事件系统优化，错误处理完善
- **第三阶段** (2-3天): 系统测试，性能优化，文档更新

## 11. 成功标准

1. **功能完整性**: 支持所有原有功能
2. **性能指标**: 响应时间不超过原系统的120%
3. **用户体验**: CLI交互更加友好和直观
4. **稳定性**: 错误率低于1%
5. **扩展性**: 新工具集成成本降低50%

## 12. 具体实现细节

### 12.1 消息管理架构

#### 12.1.1 职责分离
- **ModelClient**: 负责消息历史管理、LLM交互、工具schema提供
- **Session**: 负责事件驱动、工具执行、批准流程
- **ToolRegistry**: 负责工具注册、发现、执行

#### 12.1.2 工具Schema动态获取
```python
# ModelClient.get_tools_schema() 修改后的实现
def get_tools_schema(self) -> List[Dict[str, Any]]:
    """从工具注册系统动态获取工具schema"""
    from tools.registry import get_global_registry
    
    registry = get_global_registry()
    tools_dict = registry.get_tools_dict(enabled_only=True)
    
    # 转换为OpenAI API需要的格式
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        }
        for tool in tools_dict
    ]
```

#### 12.1.3 消息流程保持不变
现有的消息管理流程完全保持不变：
1. `Session`通过`ModelClient.add_user_message()`添加用户消息
2. `Session`通过`ModelClient.chat_completion()`获取AI响应
3. `ModelClient`自动在请求中包含动态工具schema
4. `Session`处理工具调用后通过`ModelClient.add_tool_message()`添加结果
5. 对话历史由`ModelClient`统一管理

### 12.2 Session类核心修改点

#### 12.2.1 导入和初始化
```python
# 在Session.__init__中添加：
from tools.registry import get_global_registry
from tools.base_tool import ToolContext

# 替换现有的简单工具执行器
self.tool_registry = get_global_registry()
```

#### 12.2.2 工具调用处理重构
当前的`_handle_tool_calls`方法需要修改：
- 移除对`tools.ToolExecutor`的依赖
- 直接使用`self.tool_registry.execute_tool`
- 保持现有的事件发送逻辑

#### 12.2.3 批准机制集成
现有的批准机制与工具系统的集成：
- `_needs_approval`方法适配新的工具名称
- 批准后的工具执行使用新的工具系统
- 保持事件格式不变

#### 12.2.4 关键修改点总结
1. **ModelClient.get_tools_schema()**: 从硬编码改为动态获取
2. **Session.__init__()**: 添加工具注册系统初始化
3. **Session._handle_tool_calls()**: 使用工具注册系统执行工具
4. **消息流程**: 完全保持不变，只是工具执行后端改变

### 12.3 最小化修改策略

#### 12.3.1 保持现有接口
- `Session`类的公共方法签名不变
- 事件类型和格式保持兼容
- 配置参数保持向后兼容

#### 12.3.2 渐进式替换
1. 先替换工具执行器，保持其他逻辑不变
2. 测试基本功能正常后，再优化细节
3. 最后添加新工具的支持

### 12.4 AgentTurn类集成

在Session中使用AgentTurn的多轮推理能力：
```python
# 在Session中已集成：
from core.agent_turn import AgentTurn

# 在复杂任务处理中使用AgentTurn
async def _handle_complex_reasoning(self, submission: Submission):
    # 使用Turn进行多轮推理
    # 结果通过现有事件系统反馈
```

### 12.5 工具系统兼容性检查

#### 12.4.1 工具名称映射
检查现有Session中硬编码的工具名称：
- `execute_command` -> `bash`
- `read_file` -> `read`  
- `write_file` -> `write`
- `apply_patch` -> 可能需要适配

#### 12.4.2 参数格式适配
确保工具参数格式兼容：
- 检查现有工具调用的参数名称
- 必要时添加参数转换逻辑

---

此设计文档提供了精简的原地重构方案，最小化修改范围，确保系统稳定性和向后兼容性。重点是直接集成现有工具系统，而不是创建新的抽象层。
