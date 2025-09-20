# CodeAgent - 通用编程助手

基于ReAct策略的开放性Agent，专门用于解决通用编程问题。

## 🚀 特性

- **ReAct策略**：思考-行动-观察的推理循环
- **模块化设计**：清晰的组件分离和接口设计
- **工具集成**：集成了丰富的编程工具
- **OpenAI兼容**：支持OpenAI兼容的LLM服务
- **自动规划**：根据问题自动选择工具和策略
- **轮数控制**：可配置的推理轮数限制

## 📁 架构设计

```
CodeAgent
├── 消息处理器 (MessageProcessor)
├── ReAct引擎 (ReActEngine)
├── LLM服务 (LLMService)
├── 工具注册表 (ToolRegistry)
└── 结果处理器 (ResultProcessor)
```

### 核心组件

1. **CodeAgent**: 主要的Agent类，协调所有组件
2. **ReActEngine**: 实现推理-行动-观察循环
3. **LLMService**: 与OpenAI兼容的LLM服务交互
4. **ToolRegistry**: 管理和执行各种工具
5. **MessageProcessor**: 处理对话消息和系统提示词
6. **ResultProcessor**: 格式化和处理响应结果

## 🛠️ 可用工具

- **bash**: 执行shell命令（解耦设计，通过绝对路径操作）
- **read**: 读取文件内容（支持绝对/相对路径）
- **write**: 写入文件（支持绝对/相对路径）
- **edit**: 编辑文件（支持绝对/相对路径）
- **multi_edit**: 批量编辑文件（支持绝对/相对路径）
- **glob**: 文件模式匹配搜索（可选path参数）
- **grep**: 基于ripgrep的内容搜索（可选path参数）
- **list**: 目录结构列表（可选path参数）
- **todo_write/todo_read**: 任务管理
- **task**: 任务执行
- **web_fetch/web_search**: Web工具

### 工具设计理念

所有工具都采用**解耦设计**：
- 不依赖隐式的工作目录概念
- 通过显式的绝对路径或相对路径参数操作
- 工具本身保持简洁和独立
- 路径处理由调用方（Agent或用户）负责

## 📦 安装依赖

```bash
pip install openai pytest pytest-asyncio
```

## 🔧 配置

### 环境变量

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选，支持各种兼容服务
export OPENAI_MODEL="deepseek-v3"  # 可选，默认模型
```

### 配置类

```python
from agent.code_agent import AgentConfig

config = AgentConfig(
    max_turns=10,                    # 最大推理轮数
    max_tokens=4000,                 # 最大token数
    temperature=0.1,                 # 温度参数
    model="deepseek-v3",            # 模型名称
    working_directory="./workspace"  # 工作目录（默认为项目下的workspace目录）
)
```

## 💻 使用方法

### 1. 命令行使用

```bash
python main_code_agent.py
```

### 2. 编程使用

```python
import asyncio
from agent.code_agent import CodeAgent, AgentConfig

async def main():
    # 创建Agent
    config = AgentConfig(max_turns=5)
    agent = CodeAgent(config)
    
    # 处理查询
    response = await agent.process_query("列出当前目录的Python文件")
    print(response)

asyncio.run(main())
```

### 3. 流式使用

```python
async def stream_example():
    agent = CodeAgent()
    
    async for chunk in agent.process_query_stream("分析这个项目的结构"):
        print(chunk, end="")
```

## 🔄 ReAct工作流程

1. **思考阶段**: Agent分析用户问题，制定解决策略
2. **行动阶段**: 选择合适的工具执行具体操作
3. **观察阶段**: 分析工具执行结果
4. **循环或结束**: 根据结果决定继续推理或给出最终答案

### 示例对话

```
用户: 查找项目中所有包含"TODO"的文件

Agent思考: 用户想要搜索包含特定文本的文件，我应该使用grep工具

Agent行动: grep(pattern="TODO", path=".", output_mode="files_with_matches")

Agent观察: 找到了3个包含"TODO"的文件：main.py, utils.py, README.md

Agent最终答案: 在项目中找到以下包含"TODO"的文件：
1. main.py
2. utils.py  
3. README.md
```

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/test_code_agent.py -v

# 运行特定测试
python -m pytest tests/test_code_agent.py::TestAgentConfig -v

# 运行演示
python demo_code_agent.py
```

## 📊 监控和调试

### 获取统计信息

```python
stats = agent.get_statistics()
print(f"对话轮数: {stats['conversation_turns']}")
print(f"可用工具: {stats['available_tools']}")
```

### 清空对话历史

```python
agent.clear_history()
```

### 日志配置

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## 🔧 自定义扩展

### 添加新工具

1. 继承`BaseTool`类
2. 实现必要的方法
3. 注册到工具注册表

```python
from tools import BaseTool, ToolResult, ToolContext

class MyTool(BaseTool):
    def __init__(self):
        super().__init__("my_tool", "My custom tool")
    
    async def execute(self, params, context):
        # 实现工具逻辑
        return ToolResult(title="Result", output="Success")

# 注册工具
from tools import get_global_registry
registry = get_global_registry()
registry.register_tool(MyTool)
```

### 自定义提示词

修改`prompt/ctv-claude-code-system-prompt-zh.txt`文件来自定义系统提示词。

## 📈 性能优化

1. **并行工具调用**: 支持同时执行多个独立工具
2. **结果缓存**: 工具实例采用单例模式
3. **轮数限制**: 避免无限循环推理
4. **流式响应**: 支持流式输出减少等待时间

## 🚨 注意事项

1. **API密钥安全**: 确保API密钥安全存储
2. **工具权限**: 某些工具可能需要特定权限
3. **网络依赖**: 需要稳定的网络连接访问LLM服务
4. **资源消耗**: 复杂查询可能消耗较多token

## 🤝 贡献指南

1. Fork项目
2. 创建特性分支
3. 编写测试
4. 提交代码
5. 创建Pull Request

## 📄 许可证

MIT License

## 🔗 相关资源

- [ReAct论文](https://arxiv.org/abs/2210.03629)
- [OpenAI API文档](https://platform.openai.com/docs)
- [项目架构图](./docs/architecture.md)

---

**CodeAgent** - 让编程更智能 🤖✨
