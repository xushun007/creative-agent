import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path


class Logger:
    """
    日志工具类，支持按天记录日志
    """
    
    def __init__(self, name='creative-agent',  level=logging.INFO):
        """
        初始化日志器
        
        Args:
            name (str): 日志器名称
            log_dir (str): 日志文件存储目录
            level (int): 日志级别
        """
        project_root_dir = Path(__file__).parent.parent.resolve()
        log_dir = os.path.join(project_root_dir, 'logs')
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers(log_dir, level)
    
    def _setup_handlers(self, log_dir, level):
        """
        设置日志处理器
        
        Args:
            log_dir (str): 日志目录
            level (int): 日志级别
        """
        # 创建日志目录
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 设置日志格式
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 文件处理器 - 按天轮转
        log_file = os.path.join(log_dir, 'ctv-ai.log')
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',  # 每天午夜轮转
            interval=1,       # 间隔1天
            backupCount=30,   # 保留30天的日志文件
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        # 设置轮转后的文件名格式
        file_handler.suffix = "%Y-%m-%d"
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        
        # 添加处理器到日志器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message):
        """记录DEBUG级别日志"""
        self.logger.debug(message, stacklevel=2)
    
    def info(self, message):
        """记录INFO级别日志"""
        self.logger.info(message, stacklevel=2)
    
    def warning(self, message):
        """记录WARNING级别日志"""
        self.logger.warning(message, stacklevel=2)
    
    def error(self, message):
        """记录ERROR级别日志"""
        self.logger.error(message, stacklevel=2)
    
    def critical(self, message):
        """记录CRITICAL级别日志"""
        self.logger.critical(message, stacklevel=2)


# 创建全局日志实例
logger = Logger()

# 导出常用方法，方便直接使用
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical


def get_logger(name='sigma-ai', log_dir='logs', level=logging.INFO):
    """
    获取日志器实例
    
    Args:
        name (str): 日志器名称
        log_dir (str): 日志目录
        level (int): 日志级别
    
    Returns:
        Logger: 日志器实例
    """
    return Logger(name, log_dir, level)


if __name__ == "__main__":
    # 测试日志功能
    info("这是一条INFO级别的日志")
    debug("这是一条DEBUG级别的日志")
    warning("这是一条WARNING级别的日志")
    error("这是一条ERROR级别的日志")
    critical("这是一条CRITICAL级别的日志")

    logger.info("这是一条INFO级别的日志2")
