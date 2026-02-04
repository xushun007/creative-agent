"""压缩工具函数"""

from typing import Dict, Any, List
from functools import lru_cache


@lru_cache(maxsize=1000)
def estimate_tokens(text: str) -> int:
    """估算文本token数（4字符/token）"""
    return max(0, len(text or "") // 4)


def extract_message_text(message: Dict[str, Any]) -> str:
    """从消息中提取文本内容"""
    content = message.get("content", "")
    
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts)
    
    return ""


def is_system_message(message: Dict[str, Any]) -> bool:
    """判断是否为系统消息"""
    role = message.get("role", "")
    if role == "system":
        return True
    
    if role == "user":
        text = extract_message_text(message)
        system_prefixes = ["<user_instructions>", "<ENVIRONMENT_CONTEXT>", "<project_context>"]
        return any(text.startswith(prefix) for prefix in system_prefixes)
    
    return False


def count_user_turns(messages: List[Dict[str, Any]]) -> int:
    """统计用户轮次"""
    return sum(1 for msg in messages if msg.get("role") == "user" and not is_system_message(msg))
