"""项目文档加载器"""

from pathlib import Path
from typing import List, Optional

try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ProjectDocLoader:
    """项目文档加载器
    
    负责：
    - 从项目目录中查找和加载配置文件（AGENTS.md 等）
    - 支持多层级目录搜索（从 Git 根目录到当前目录）
    - 合并多个文档内容
    """
    
    # 默认搜索的文件名（优先级从高到低）
    DEFAULT_FILENAMES = [
        "AGENTS.override.md",  # 覆盖配置（最高优先级）
        "AGENTS.md",           # 标准配置
        ".agent.md"            # 隐藏配置
    ]
    
    def __init__(
        self, 
        cwd: Path,
        max_size: int = 32768,  # 32KB
        filenames: Optional[List[str]] = None
    ):
        """
        Args:
            cwd: 当前工作目录
            max_size: 最大文档大小（字节）
            filenames: 自定义文件名列表（默认使用 DEFAULT_FILENAMES）
        """
        self.cwd = Path(cwd)
        self.max_size = max_size
        self.filenames = filenames or self.DEFAULT_FILENAMES
    
    def find_git_root(self) -> Optional[Path]:
        """查找 Git 根目录
        
        从当前目录向上搜索，直到找到包含 .git 的目录
        
        Returns:
            Git 根目录路径，如果没有找到则返回 None
        """
        current = self.cwd.resolve()
        
        # 向上遍历目录
        while current != current.parent:
            if (current / ".git").exists():
                logger.debug(f"找到 Git 根目录: {current}")
                return current
            current = current.parent
        
        logger.debug("未找到 Git 根目录")
        return None
    
    def discover_docs(self) -> List[Path]:
        """发现项目文档路径（简化版：仅搜索当前工作目录）
        
        搜索策略：
        1. 仅在当前工作目录 (cwd) 中查找
        2. 按优先级返回第一个匹配的文件
        
        Returns:
            文档路径列表（最多1个文件）
        """
        # 仅在当前工作目录中查找
        for filename in self.filenames:
            doc_path = self.cwd / filename
            if doc_path.exists() and doc_path.is_file():
                logger.info(f"发现文档: {doc_path}")
                return [doc_path]  # 只返回第一个找到的文件
        
        logger.debug(f"未在 {self.cwd} 中找到项目文档")
        return []
    
    def load_docs(self) -> Optional[str]:
        """加载并合并项目文档
        
        Returns:
            合并后的文档内容，如果没有找到文档则返回 None
        """
        doc_paths = self.discover_docs()
        
        if not doc_paths:
            logger.info("未找到项目文档")
            return None
        
        contents = []
        total_size = 0
        
        for doc_path in doc_paths:
            try:
                text = doc_path.read_text(encoding="utf-8")
                size = len(text.encode("utf-8"))
                
                # 检查是否超出大小限制
                if total_size + size > self.max_size:
                    remaining = self.max_size - total_size
                    if remaining > 0:
                        # 截断以适应剩余空间
                        text = text[:remaining]
                        contents.append(f"# {doc_path.name}\n{text}")
                        logger.warning(f"文档 {doc_path} 被截断（超出大小限制）")
                    break
                
                # 添加文档标题和内容
                contents.append(f"# {doc_path.name}\n{text}")
                total_size += size
                logger.info(f"加载文档: {doc_path} ({size} bytes)")
            
            except UnicodeDecodeError as e:
                logger.warning(f"无法读取文档 {doc_path}（编码错误）: {e}")
                continue
            except Exception as e:
                logger.warning(f"读取文档 {doc_path} 失败: {e}")
                continue
        
        if not contents:
            return None
        
        # 用分隔符连接多个文档
        merged = "\n\n--- project-doc ---\n\n".join(contents)
        logger.info(f"合并 {len(contents)} 个文档，总大小 {total_size} bytes")
        
        return merged
    
    def load_as_system_message(self) -> Optional[str]:
        """加载文档并格式化为系统消息
        
        Returns:
            格式化的系统消息内容
        """
        docs = self.load_docs()
        
        if not docs:
            return None
        
        return f"""## 项目文档

以下是项目配置文档，包含项目特定的规则、约定和指引：

{docs}

请在协助用户时遵循上述文档中的规则和约定。
"""

