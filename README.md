# creative-agent

最小可用的创造型 Coding Agent，聚焦 Tool 协作与可控执行。其设计和实现参考了主流Coding Agent（Codex，Claude Code，OpenCode，Gemini Cli）。

## 特性

- 基于 `CtvEngine` 的事件驱动执行流程
- 内置多种工具（文件、命令、搜索、任务编排等）
- 支持沙箱与命令审批策略
- 支持会话持久化与恢复（memory/session）
- 支持上下文压缩（compaction，默认关闭）


## 环境要求

- Python 3.10+
- 可用的模型 API Key（最少需要 `OPENAI_API_KEY`, `OPENAI_BASE_URL`）

## 快速开始

1. 安装依赖

```bash
uv venv
source .venv/bin/activate
uv sync
```

2. 配置环境变量

```bash
cp .env.example .env
```

至少修改以下字段：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `CTV_MODEL`
- `CTV_MODEL_PROVIDER`（可选）


3. 启动聊天模式

```bash
ctvagent chat
```

## CLI 命令

查看帮助：

```bash
ctvagent --help
```

常用命令：

- `chat`：进入交互式聊天模式
- `sessions`：列出历史会话
- `resume`：恢复会话继续聊天
- `version`：查看版本

示例：

```bash
ctvagent sessions
ctvagent resume --session-id <id_prefix>
ctvagent chat --model qwen-plus --sandbox workspace_write
```

如果你不想安装脚本入口，也可以直接使用 Python 脚本路径：

```bash
python3 src/cli/main.py chat
python3 src/cli/main.py sessions
```

## 运行测试

```bash
pytest -v
```

或指定模块：

```bash
pytest tests/core/ tests/tools/ -v
```

## 配置说明

主要配置在 `Config`（`src/core/config.py`）中，优先级如下：

1. 代码传参
2. `.env`
3. 系统环境变量
4. 默认值

关键配置项：

- `model_provider` / `model` / `api_key`
- `cwd`（默认 `./workspace`）
- `sandbox_policy`：`strict | workspace_write | none`
- `approval_policy`：`always | on_request | never`
- `enable_memory`、`session_dir`
- `enable_compaction`、`max_context_tokens`


## 项目结构

```text
src/
  cli/            # Typer CLI 入口
  core/           # Engine / Session / Config / Memory / Hooks
  tools/          # 工具实现与注册
  prompt/         # 系统提示词与模板
tests/            # 单元测试
workspace/        # 默认工作目录
```


## 核心组件

- `CtvEngine`：任务生命周期与事件编排
- `Session`：消息历史、状态与上下文管理
- `ModelClient`：模型调用与消息组织
- `Tool Registry`：工具注册、调度与执行
- `MemoryManager`：会话落盘、读取和恢复

## 开发建议

- 首次开发先跑 `pytest -v` 验证环境
- 提交前建议至少执行相关模块测试
- 新增工具时同步补测试（参考 `tests/tools/`）
