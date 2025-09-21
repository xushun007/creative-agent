# Creative Agent

最小可用、聚焦工具协作的 AI 编程助手。Creative Agent 将事件驱动的会话引擎与一套丰富的自动化工具结合，帮助开发者在安全、可控的环境中构建和迭代代码。

## ✨ 核心特性

- **事件驱动的会话管理**：`CodexEngine` 与 `Session` 通过异步事件流连接 CLI 与模型推理，实现实时状态反馈与可插拔的 UI。
- **ReAct 推理循环**：`AgentTurn` 统筹 LLM 对话、工具调用与批准机制，避免长时间阻塞并跟踪 token 使用。
- **丰富的工具生态**：开箱即用的 12+ 种工具涵盖命令执行、代码编辑、文件操作、任务拆解与联网搜索等场景，可按需扩展或禁用。
- **安全沙箱与审批策略**：通过审批策略、超时控制和沙箱写权限，确保自动化操作在受限环境中进行。
- **高度可配置**：支持通过 `.env`、JSON 或 TOML 文件注入模型、API Endpoint、工作目录、提示词等配置项。

## 🏗️ 架构概览

```
┌────────────┐       ┌───────────────────┐
│  CLI (Typer)│◄────►│   CodexEngine     │
└────────────┘       └──────┬────────────┘
                             │
                      ┌──────▼────────┐
                      │    Session    │
                      ├──────┬────────┤
                      │EventHandler   │
                      │ModelClient    │
                      │ToolRegistry   │
                      └──────┴────────┘
                             │
                 ┌───────────▼───────────┐
                 │     Tools & Prompts   │
                 └───────────────────────┘
```

- **CLI (`src/cli`)**：基于 [Typer](https://typer.tiangolo.com/) 的终端界面，负责渲染事件、采集输入及审批指令。
- **Core (`src/core`)**：包含配置管理、事件协议、模型客户端、会话调度以及 `AgentTurn` 推理循环。
- **Tools (`src/tools`)**：通过 `ToolRegistry` 动态发现与调度工具；工具以单文件形式实现，便于扩展与测试。
- **Workspace (`workspace/`)**：默认工作目录，可在配置中修改；所有读写操作均在沙箱中完成。

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/creative-agent.git
cd creative-agent
```

### 2. 安装依赖

建议使用 Python 3.10+ 与虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

如需开发工具与测试能力：

```bash
pip install -r requirements-dev.txt
```

### 3. 配置环境变量

在仓库根目录创建 `.env`，至少包含：

```
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 可选
```

更多配置可参考下方“配置项”章节。

### 4. 启动 CLI

```bash
python -m cli.main
```

首启动时会在终端输出当前模型、工作目录与沙箱策略，然后等待用户输入。直接输入自然语言需求即可触发 ReAct 循环。

## 🧰 工具生态

Creative Agent 通过 `ToolRegistry` 管理工具实例，并自动生成 OpenAI function-call schema。

| 工具 ID | 作用简介 |
| --- | --- |
| `bash` | 在受限 shell 中执行命令，支持超时与输出截断。 |
| `edit` / `multi_edit` | 对单个或多个文件应用结构化代码修改。 |
| `read` / `write` | 读取、写入工作区文件，带有编码与路径校验。 |
| `glob` | 使用通配符列出匹配的文件路径。 |
| `grep` | 通过正则或字符串在文件中检索内容。 |
| `list` | 枚举目录内容，帮助了解项目结构。 |
| `todo_read` / `todo_write` | 管理 Agent 任务清单与进度。 |
| `task` | 对复杂需求进行任务拆解并生成执行计划。 |
| `web_search` / `web_fetch` | 调用 DuckDuckGo 与网页抓取获取最新资料。 |

所有工具都实现自 `BaseTool`，具备统一的上下文 (`ToolContext`) 与返回结构 (`ToolResult`)，便于扩展与审计。

## ⚙️ 配置项

`Config` 支持通过代码构造、`.env`、JSON 或 TOML 文件加载。常用字段如下：

| 字段 | 说明 | 默认值 |
| --- | --- | --- |
| `model_provider` | 模型服务商标识（如 `deepseek`）。 | `deepseek` |
| `model` | 模型名称。 | `deepseek-chat` |
| `api_key` / `api_base` | OpenAI 兼容接口凭据。 | `.env` 中读取 |
| `cwd` | 工作目录，所有文件操作均在此沙箱内。 | `workspace/` |
| `approval_policy` | 工具执行审批策略，`on_request` 时遇敏感命令需人工确认。 | `on_request` |
| `sandbox_policy` | 写权限策略，如 `workspace_write`。 | `workspace_write` |
| `base_instructions` / `user_instructions` | 系统与用户级提示词。 | 内置默认值 |
| `max_turns` | 单次任务的最大轮数，防止无限循环。 | `20` |
| `temperature` / `max_tokens` | 模型采样与输出控制。 | `0.1` / `4096` |

## 🖥️ CLI 使用指南

1. **输入需求**：直接描述任务，例如“在 README 中补充快速开始章节”。
2. **查看事件流**：终端会实时输出 `task_started`、`agent_message`、`tool_execution` 等事件，帮助理解当前步骤。
3. **批准执行**：当触发审批策略时，CLI 会提示命令内容，可通过 `y/n` 进行批准或拒绝。
4. **查看结果**：任务完成后输出最终答复及最后一次模型回复。
5. **中断**：使用 `Ctrl+C` 退出或中断当前任务，引擎会优雅关闭。

## 🧑‍💻 开发与测试

### 项目结构

```
creative-agent/
├── src/
│   ├── cli/             # 命令行入口与交互逻辑
│   ├── core/            # 会话引擎、配置、事件与模型客户端
│   ├── tools/           # 工具实现与注册中心
│   ├── prompt/          # 系统提示词模板
│   └── utils/           # 通用辅助函数与日志
├── tests/               # 针对工具的单元测试
├── workspace/           # 运行时沙箱工作区
└── design.md            # 架构设计文档
```

### 运行测试

```bash
pytest
```

测试覆盖常用工具的功能与边界情况，建议在扩展工具或修改执行器后运行。

### 代码风格

项目遵循 [Black](https://black.readthedocs.io/) + [isort](https://pycqa.github.io/isort/) 格式化约定，并提供 `mypy` 类型检查配置：

```bash
black src tests
isort src tests
mypy src
```

## 📄 许可证

本项目采用 [MIT License](LICENSE)。欢迎提交 Issue、PR 或工具扩展提案。

---

如果你也在探索“最小可用且具备创造力的 Agent”，欢迎加入讨论，共建更开放的自动化编程生态。
