"""代码补丁应用器"""

import re
import difflib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import tempfile
import shutil

from core.config import Config


class PatchApplier:
    """代码补丁应用器"""
    
    def __init__(self, config: Config):
        self.config = config
    
    async def apply_patch(self, file_path: Path, patch_content: str) -> Dict[str, Any]:
        """应用unified diff格式的补丁"""
        
        try:
            # 检查文件是否存在
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"目标文件不存在: {file_path}"
                }
            
            # 读取原文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 解析补丁
            parsed_patch = self._parse_unified_diff(patch_content)
            if not parsed_patch:
                return {
                    "success": False,
                    "error": "无法解析补丁格式"
                }
            
            # 应用补丁
            new_content = self._apply_parsed_patch(original_content, parsed_patch)
            if new_content is None:
                return {
                    "success": False,
                    "error": "补丁应用失败，可能是由于上下文不匹配"
                }
            
            # 创建备份
            backup_path = file_path.with_suffix(file_path.suffix + '.bak')
            shutil.copy2(file_path, backup_path)
            
            # 写入新内容
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # 计算变更统计
            stats = self._calculate_patch_stats(original_content, new_content)
            
            return {
                "success": True,
                "message": f"补丁应用成功，{stats['added']} 行添加，{stats['removed']} 行删除",
                "backup_path": str(backup_path),
                "stats": stats
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"应用补丁时出错: {str(e)}"
            }
    
    def _parse_unified_diff(self, patch_content: str) -> Optional[List[Dict[str, Any]]]:
        """解析unified diff格式的补丁"""
        
        lines = patch_content.strip().split('\n')
        chunks = []
        current_chunk = None
        
        for line in lines:
            # 跳过文件头
            if line.startswith('---') or line.startswith('+++'):
                continue
            
            # 块头：@@ -start,count +start,count @@
            if line.startswith('@@'):
                if current_chunk:
                    chunks.append(current_chunk)
                
                # 解析块头
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if not match:
                    return None
                
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1
                
                current_chunk = {
                    'old_start': old_start,
                    'old_count': old_count,
                    'new_start': new_start,
                    'new_count': new_count,
                    'lines': []
                }
            elif current_chunk is not None:
                # 补丁行
                if line.startswith(' '):
                    # 上下文行
                    current_chunk['lines'].append({
                        'type': 'context',
                        'content': line[1:]
                    })
                elif line.startswith('-'):
                    # 删除行
                    current_chunk['lines'].append({
                        'type': 'remove',
                        'content': line[1:]
                    })
                elif line.startswith('+'):
                    # 添加行
                    current_chunk['lines'].append({
                        'type': 'add',
                        'content': line[1:]
                    })
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else None
    
    def _apply_parsed_patch(self, original_content: str, chunks: List[Dict[str, Any]]) -> Optional[str]:
        """应用解析后的补丁"""
        
        original_lines = original_content.split('\n')
        result_lines = original_lines.copy()
        
        # 从后往前应用补丁，避免行号偏移问题
        for chunk in reversed(chunks):
            old_start = chunk['old_start'] - 1  # 转换为0索引
            
            # 验证上下文
            if not self._validate_context(original_lines, chunk, old_start):
                return None
            
            # 应用这个块的变更
            new_chunk_lines = []
            for patch_line in chunk['lines']:
                if patch_line['type'] == 'context':
                    new_chunk_lines.append(patch_line['content'])
                elif patch_line['type'] == 'add':
                    new_chunk_lines.append(patch_line['content'])
                # remove类型的行不添加到新内容中
            
            # 计算要替换的行数
            remove_count = sum(1 for line in chunk['lines'] 
                             if line['type'] in ['context', 'remove'])
            
            # 替换行
            result_lines[old_start:old_start + remove_count] = new_chunk_lines
        
        return '\n'.join(result_lines)
    
    def _validate_context(self, original_lines: List[str], chunk: Dict[str, Any], start_line: int) -> bool:
        """验证补丁上下文是否匹配"""
        
        original_idx = start_line
        
        for patch_line in chunk['lines']:
            if patch_line['type'] in ['context', 'remove']:
                if (original_idx >= len(original_lines) or 
                    original_lines[original_idx] != patch_line['content']):
                    return False
                original_idx += 1
        
        return True
    
    def _calculate_patch_stats(self, original: str, modified: str) -> Dict[str, int]:
        """计算补丁统计信息"""
        
        original_lines = original.split('\n')
        modified_lines = modified.split('\n')
        
        differ = difflib.unified_diff(original_lines, modified_lines, lineterm='')
        
        added = 0
        removed = 0
        
        for line in differ:
            if line.startswith('+') and not line.startswith('+++'):
                added += 1
            elif line.startswith('-') and not line.startswith('---'):
                removed += 1
        
        return {
            'added': added,
            'removed': removed,
            'modified': min(added, removed)
        }
    
    async def create_patch(self, file_path: Path, new_content: str) -> str:
        """创建补丁"""
        
        if not file_path.exists():
            # 新文件
            lines = new_content.split('\n')
            patch_lines = ['--- /dev/null', f'+++ {file_path}', '@@ -0,0 +1,{len(lines)} @@']
            patch_lines.extend(f'+{line}' for line in lines)
            return '\n'.join(patch_lines)
        
        # 现有文件
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        original_lines = original_content.split('\n')
        new_lines = new_content.split('\n')
        
        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f'a/{file_path}',
            tofile=f'b/{file_path}',
            lineterm=''
        )
        
        return '\n'.join(diff)
    
    async def preview_patch(self, file_path: Path, patch_content: str) -> Dict[str, Any]:
        """预览补丁效果"""
        
        try:
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"目标文件不存在: {file_path}"
                }
            
            # 读取原文件
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 解析并应用补丁
            parsed_patch = self._parse_unified_diff(patch_content)
            if not parsed_patch:
                return {
                    "success": False,
                    "error": "无法解析补丁格式"
                }
            
            new_content = self._apply_parsed_patch(original_content, parsed_patch)
            if new_content is None:
                return {
                    "success": False,
                    "error": "补丁应用失败"
                }
            
            # 生成预览
            original_lines = original_content.split('\n')
            new_lines = new_content.split('\n')
            
            diff = list(difflib.unified_diff(
                original_lines,
                new_lines,
                fromfile='原文件',
                tofile='修改后',
                lineterm=''
            ))
            
            stats = self._calculate_patch_stats(original_content, new_content)
            
            return {
                "success": True,
                "preview": '\n'.join(diff),
                "stats": stats
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"预览补丁时出错: {str(e)}"
            }
    
    async def revert_patch(self, file_path: Path) -> Dict[str, Any]:
        """恢复补丁（从备份文件）"""
        
        backup_path = file_path.with_suffix(file_path.suffix + '.bak')
        
        try:
            if not backup_path.exists():
                return {
                    "success": False,
                    "error": f"备份文件不存在: {backup_path}"
                }
            
            # 恢复文件
            shutil.copy2(backup_path, file_path)
            
            return {
                "success": True,
                "message": f"已从备份恢复文件: {file_path}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"恢复文件时出错: {str(e)}"
            }
