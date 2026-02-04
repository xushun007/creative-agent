"""工具函数"""

import json
from typing import Any, Optional, Dict
from datetime import timedelta


def format_duration(seconds: float) -> str:
    """格式化持续时间"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        td = timedelta(seconds=seconds)
        return str(td)


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_json_loads(text: str, default: Any = None) -> Any:
    """安全的JSON解析"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def extract_code_blocks(text: str) -> list:
    """从文本中提取代码块"""
    import re
    
    # 匹配```语言\n代码\n```格式的代码块
    pattern = r'```(\w+)?\n(.*?)\n```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    code_blocks = []
    for language, code in matches:
        code_blocks.append({
            'language': language or 'text',
            'code': code.strip()
        })
    
    return code_blocks


def is_binary_file(file_path: str) -> bool:
    """检查是否是二进制文件"""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except:
        return True


def get_file_extension(file_path: str) -> str:
    """获取文件扩展名"""
    from pathlib import Path
    return Path(file_path).suffix.lower()


def is_text_file(file_path: str) -> bool:
    """检查是否是文本文件"""
    if is_binary_file(file_path):
        return False
    
    text_extensions = {
        '.txt', '.py', '.js', '.ts', '.html', '.css', '.json', '.xml',
        '.md', '.rst', '.yml', '.yaml', '.toml', '.ini', '.cfg',
        '.sh', '.bash', '.bat', '.ps1', '.sql', '.go', '.rs', '.java',
        '.c', '.cpp', '.h', '.hpp', '.cs', '.php', '.rb', '.swift',
        '.kt', '.scala', '.clj', '.hs', '.elm', '.ml', '.pl', '.r'
    }
    
    ext = get_file_extension(file_path)
    return ext in text_extensions
