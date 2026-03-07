# creative-agent

最小可用的创造型 Coding Agent，聚焦 Tool 协作与可控执行。其设计和实现参考了主流Coding Agent（Codex，Claude Code，OpenCode，Gemini Cli）。

## 特性

- 基于 `CodexEngine` 的事件驱动执行流程
- 内置多种工具（文件、命令、搜索、任务编排等）
- 支持沙箱与命令审批策略
- 支持会话持久化与恢复（memory/session）
- 支持上下文压缩（compaction，默认关闭）

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

## 环境要求

- Python 3.10+
- 可用的模型 API Key（最少需要 `OPENAI_API_KEY`）

## 快速开始

1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 配置环境变量

```bash
cp .env.example .env.mb
```

至少修改以下字段：

- `OPENAI_API_KEY`
- `CTV_MODEL_PROVIDER`
- `CTV_MODEL`

说明：代码默认读取 `.env.mb`（见 `src/core/config.py`）。

3. 启动聊天模式

```bash
PYTHONPATH=src python3 -m cli.main chat
```

## CLI 命令

查看帮助：

```bash
PYTHONPATH=src python3 -m cli.main --help
```

常用命令：

- `chat`：进入交互式聊天模式
- `sessions`：列出历史会话
- `resume`：恢复会话继续聊天
- `config-init`：交互式生成配置文件
- `version`：查看版本

示例：

```bash
PYTHONPATH=src python3 -m cli.main sessions
PYTHONPATH=src python3 -m cli.main resume --session-id <id_prefix>
PYTHONPATH=src python3 -m cli.main chat --model qwen-plus --sandbox workspace_write
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
2. `.env.mb`
3. 系统环境变量
4. 默认值

关键配置项：

- `model_provider` / `model` / `api_key`
- `cwd`（默认 `./workspace`）
- `sandbox_policy`：`strict | workspace_write | none`
- `approval_policy`：`always | on_request | never`
- `enable_memory`、`session_dir`
- `enable_compaction`、`max_context_tokens`

## 核心组件

- `CodexEngine`：任务生命周期与事件编排
- `Session`：消息历史、状态与上下文管理
- `ModelClient`：模型调用与消息组织
- `Tool Registry`：工具注册、调度与执行
- `MemoryManager`：会话落盘、读取和恢复

## 开发建议

- 首次开发先跑 `pytest -v` 验证环境
- 提交前建议至少执行相关模块测试
- 新增工具时同步补测试（参考 `tests/tools/`）
