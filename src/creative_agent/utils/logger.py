import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


class Logger:
    """封装项目日志配置，允许区分文件与控制台级别"""

    def __init__(
        self,
        name: str = 'creative-agent',
        level: int = logging.DEBUG,
        console_level: Optional[int] = logging.INFO,
        log_dir: Optional[str] = None,
    ) -> None:
        project_root = Path(__file__).parent.parent.parent.resolve()
        self.log_dir = log_dir or os.path.join(project_root, 'logs')
        self.file_level = level
        self.console_level = console_level if console_level is not None else level

        self.logger = logging.getLogger(name)
        self.logger.setLevel(min(self.file_level, self.console_level))
        self.logger.propagate = False

        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self) -> None:
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

        log_file = os.path.join(self.log_dir, 'ctv-ai.log')
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8',
        )
        file_handler.setLevel(self.file_level)
        file_handler.setFormatter(formatter)
        file_handler.suffix = '%Y-%m-%d'

        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def debug(self, message: str) -> None:
        self.logger.debug(message, stacklevel=2)

    def info(self, message: str) -> None:
        self.logger.info(message, stacklevel=2)

    def warning(self, message: str) -> None:
        self.logger.warning(message, stacklevel=2)

    def error(self, message: str) -> None:
        self.logger.error(message, stacklevel=2)

    def critical(self, message: str) -> None:
        self.logger.critical(message, stacklevel=2)


logger = Logger()

debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical


def get_logger(
    name: str = 'creative-agent',
    level: int = logging.DEBUG,
    console_level: Optional[int] = logging.INFO,
    log_dir: Optional[str] = None,
) -> Logger:
    """返回具备自定义级别的日志器实例"""
    return Logger(name=name, level=level, console_level=console_level, log_dir=log_dir)


if __name__ == '__main__':
    info('这是一条INFO级别的日志')
    debug('这是一条DEBUG级别的日志')
    warning('这是一条WARNING级别的日志')
    error('这是一条ERROR级别的日志')
    critical('这是一条CRITICAL级别的日志')

    logger.info('这是一条INFO级别的日志2')
