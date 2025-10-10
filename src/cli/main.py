import asyncio
import sys
from pathlib import Path
from typing import Optional
import signal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm

from core import Config, CodexEngine
from core.protocol import Event, EventMsg


# 全局变量
console = Console()
app = typer.Typer(name="codex", help="Codex - AI编程助手")


class CodexCLI:
    """Codex CLI控制器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.engine: Optional[CodexEngine] = None
        self.running = False
        self.pending_approvals = {}
    
    async def start(self):
        """启动CLI"""
        try:
            # 启动引擎
            self.engine = CodexEngine(self.config)
            await self.engine.start()
            
            self.show_start_UI()
            
            self.running = True
            
            # 启动事件处理
            event_task = asyncio.create_task(self._handle_events())
            
            # 启动用户输入处理
            input_task = asyncio.create_task(self._handle_user_input())
            
            # 等待任务完成
            try:
                await asyncio.gather(event_task, input_task)
            except asyncio.CancelledError:
                # 任务被取消，正常退出
                pass
            
        except KeyboardInterrupt:
            console.print("\n[yellow]收到中断信号，正在关闭...[/yellow]")
        except Exception as e:
            console.print(f"[red]启动失败: {e}[/red]")
        finally:
            await self.stop()

    def show_start_UI(self):
        """显示启动UI"""
        console.print(Panel.fit(
            f"[bold green]Codex Python 已启动[/bold green]\n"
            f"模型: {self.config.model}\n"
            f"工作目录: {self.config.cwd}\n"
            f"沙箱策略: {self.config.sandbox_policy}",
            title="🤖 Codex"
        ))

    async def stop(self):
        """停止CLI"""
        self.running = False
        if self.engine:
            await self.engine.stop()
        console.print("[green]Codex已关闭[/green]")
    
    async def _handle_events(self):
        """处理事件流"""
        if not self.engine:
            return
        
        try:
            async for event in self.engine.get_events():
                if not self.running:
                    break
                await self._process_event(event)
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
    
    async def _process_event(self, event: Event):
        """处理单个事件"""
        msg = event.msg
        
        if msg.type == "task_started":
            console.print("[blue]🚀 任务开始...[/blue]")
        
        elif msg.type == "task_complete":
            console.print("[green]✅ 任务完成[/green]")
            last_message = msg.data.get("last_agent_message")
            if last_message:
                console.print()
            print("\n> ", end="", flush=True)
        
        elif msg.type == "agent_message":
            message = msg.data.get("message", "")
            if message:
                console.print(Panel(
                    Markdown(message),
                    title="🤖 Codex",
                    border_style="blue"
                ))
        
        elif msg.type == "user_message":
            message = msg.data.get("message", "")
            console.print(Panel(
                Text(message),
                title="👤 用户",
                border_style="green"
            ))
        
        elif msg.type == "exec_command_begin":
            command = " ".join(msg.data.get("command", []))
            cwd = msg.data.get("cwd", "")
            console.print(f"[yellow]⚡ 执行命令: {command}[/yellow]")
            if cwd:
                console.print(f"[dim]工作目录: {cwd}[/dim]")
        
        elif msg.type == "exec_command_end":
            stdout = msg.data.get("stdout", "")
            stderr = msg.data.get("stderr", "")
            exit_code = msg.data.get("exit_code", 0)
            
            if exit_code == 0:
                console.print("[green]✅ 命令执行成功[/green]")
            else:
                console.print(f"[red]❌ 命令执行失败 (退出码: {exit_code})[/red]")
            
            if stdout:
                console.print(Panel(stdout, title="标准输出", border_style="green"))
            if stderr:\
                console.print(Panel(stderr, title="标准错误", border_style="red"))
        
        elif msg.type == "exec_approval_request":
            await self._handle_approval_request(event)
        
        elif msg.type == "token_count":
            usage = msg.data
            total = usage.get("total_tokens", 0)
            if total > 0:
                console.print(f"[dim]Token使用: {total}[/dim]")
        
        elif msg.type == "error":
            error_msg = msg.data.get("message", "未知错误")
            console.print(f"[red]❌ 错误: {error_msg}[/red]")
        
        elif msg.type == "tool_execution_begin":
            tool_name = msg.data.get("tool_name", "")
            console.print(f"[yellow]🔧 执行工具: {tool_name}[/yellow]")
        
        elif msg.type == "tool_execution_end":
            tool_name = msg.data.get("tool_name", "")
            success = msg.data.get("success", False)
            
            if success:
                console.print(f"[green]✅ 工具 {tool_name} 执行成功[/green]")
                # 可选：显示工具结果的简要信息
                result = msg.data.get("result", "")
                if result and len(result) < 200:  # 只显示简短结果
                    console.print(f"[dim]结果: {result[:100]}...[/dim]")
            else:
                error = msg.data.get("error", "未知错误")
                console.print(f"[red]❌ 工具 {tool_name} 执行失败: {error}[/red]")
        
        elif msg.type == "approval_complete":
            decision = msg.data.get("decision", "")
            result = msg.data.get("result", "")
            if decision == "approved":
                console.print(f"[green]✅ 批准执行完成: {result}[/green]")
            else:
                console.print(f"[yellow]ℹ️  批准处理: {result}[/yellow]")
        
        elif msg.type == "session_configured":
            # 会话配置完成，静默处理
            pass
        
        else:
            # 其他事件类型，包括未知的新事件
            console.print(f"[dim]事件: {msg.type}[/dim]")
    
    async def _handle_approval_request(self, event: Event):
        """处理批准请求"""
        msg = event.msg
        call_id = msg.data.get("call_id", "")
        command = " ".join(msg.data.get("command", []))
        cwd = msg.data.get("cwd", "")
        reason = msg.data.get("reason", "")
        
        console.print()
        console.print(Panel(
            f"[yellow]命令需要批准:[/yellow]\n"
            f"[bold]{command}[/bold]\n"
            f"工作目录: {cwd}\n"
            f"原因: {reason}",
            title="⚠️  批准请求",
            border_style="yellow"
        ))
        
        # 询问用户
        approved = Confirm.ask("是否批准执行此命令?", default=False)
        
        if self.engine:
            await self.engine.approve_execution(event.id, approved)
        
        if approved:
            console.print("[green]✅ 已批准执行[/green]")
        else:
            console.print("[red]❌ 已拒绝执行[/red]")
    
    async def _handle_user_input(self):
        """处理用户输入"""
        console.print("\n[bold cyan]输入你的请求 (输入 'exit' 退出, 'help' 查看帮助):[/bold cyan]")
        
        while self.running:
            try:
                # 使用异步方式获取用户输入
                user_input = await self._get_user_input()
                
                if not user_input:
                    continue
                
                user_input = user_input.strip()
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    console.print("[yellow]正在退出...[/yellow]")
                    self.running = False
                    if self.engine:
                        await self.engine.stop()
                    break
                
                elif user_input.lower() in ['help', 'h']:
                    self._show_help()
                    continue
                
                elif user_input.lower() in ['clear', 'cls']:
                    console.clear()
                    continue
                
                elif user_input.lower() == 'status':
                    self._show_status()
                    continue
                
                # 提交用户输入
                if self.engine:
                    await self.engine.submit_user_input(user_input)
                
            except KeyboardInterrupt:
                if self.engine:
                    await self.engine.interrupt_current_task()
                console.print("\n[yellow]已中断当前任务[/yellow]")
            except Exception as e:
                console.print(f"[red]处理输入时出错: {e}[/red]")
    
    async def _get_user_input(self) -> str:
        """异步获取用户输入"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, input, "\n> ")
    
    def _show_help(self):
        """显示帮助信息"""
        help_text = """
[bold cyan]Codex Python 帮助[/bold cyan]

[bold]基本命令:[/bold]
- help, h        显示此帮助信息
- exit, quit, q  退出程序
- clear, cls     清屏
- status         显示状态信息

[bold]使用方法:[/bold]
直接输入你的编程请求，例如：
- "创建一个Python脚本来计算斐波那契数列"
- "帮我修复这个bug"
- "解释这段代码的作用"

[bold]快捷键:[/bold]
- Ctrl+C         中断当前任务
- Ctrl+D         退出程序

[bold]配置:[/bold]
- 模型: {model}
- 工作目录: {cwd}
- 沙箱策略: {sandbox_policy}
        """.format(
            model=self.config.model,
            cwd=self.config.cwd,
            sandbox_policy=self.config.sandbox_policy
        )
        
        console.print(Panel(help_text, title="帮助", border_style="cyan"))
    
    def _show_status(self):
        """显示状态信息"""
        if not self.engine:
            status = "[red]未启动[/red]"
            token_info = "N/A"
        else:
            status = "[green]运行中[/green]" if self.engine.is_running else "[red]已停止[/red]"
            usage = self.engine.token_usage
            if usage and not usage.is_zero():
                token_info = f"输入: {usage.input_tokens}, 输出: {usage.output_tokens}, 总计: {usage.total_tokens}"
            else:
                token_info = "无使用记录"
        
        status_text = f"""
[bold]引擎状态:[/bold] {status}
[bold]Token使用:[/bold] {token_info}
[bold]配置文件:[/bold] {self.config.model}
[bold]工作目录:[/bold] {self.config.cwd}
        """
        
        console.print(Panel(status_text.strip(), title="状态", border_style="blue"))


# CLI命令定义

@app.command()
def chat(
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="配置文件路径"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="AI模型名称"),
    cwd: Optional[Path] = typer.Option(None, "--cwd", help="工作目录"),
    sandbox: Optional[str] = typer.Option("workspace_write", "--sandbox", "-s", help="沙箱策略"),
    approval: Optional[str] = typer.Option("on_request", "--approval", "-a", help="批准策略"),
):
    """启动Codex聊天模式"""
    
    # 加载配置
    if config_file and config_file.exists():
        config = Config.from_file(config_file)
    else:
        config = Config()
    
    # 覆盖配置
    if model:
        config.model = model
    if cwd:
        config.cwd = cwd
    if sandbox:
        config.sandbox_policy = sandbox
    if approval:
        config.approval_policy = approval
    
    # 配置已在初始化时自动验证，无需手动调用 validate()
    
    # 启动CLI
    cli = CodexCLI(config)
    
    # 设置信号处理
    def signal_handler(signum, frame):
        console.print("\n[yellow]收到中断信号，正在关闭...[/yellow]")
        cli.running = False
        # 发送KeyboardInterrupt异常来中断input()
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        asyncio.run(cli.start())
    except KeyboardInterrupt:
        pass


@app.command()
def config_init(
    config_file: Path = typer.Option(Path.home() / ".codex" / "config.json", "--output", "-o"),
):
    """初始化配置文件"""
    
    config = Config()
    
    # 交互式配置
    console.print("[bold cyan]Codex配置初始化[/bold cyan]")
    
    api_key = Prompt.ask("OpenAI API Key", default=config.api_key or "")
    if api_key:
        config.api_key = api_key
    
    model = Prompt.ask("模型名称", default=config.model)
    config.model = model
    
    cwd = Prompt.ask("默认工作目录", default=str(config.cwd))
    config.cwd = Path(cwd)
    
    sandbox = typer.prompt(
        "沙箱策略",
        default=config.sandbox_policy,
        type=typer.Choice(["strict", "workspace_write", "none"])
    )
    config.sandbox_policy = sandbox
    
    # 保存配置为 JSON
    import json
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_data = config.model_dump()
    config_data["cwd"] = str(config_data["cwd"])
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
    console.print(f"[green]配置已保存到: {config_file}[/green]")


@app.command() 
def version():
    """显示版本信息"""
    __version__ = "0.1.0"
    console.print(f"Codex Python v{__version__}")


def main():
    """主入口函数"""
    app()


if __name__ == "__main__":
    main()
