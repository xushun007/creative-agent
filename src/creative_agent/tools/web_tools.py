import asyncio
import re
import time
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin
import aiohttp
from bs4 import BeautifulSoup
import html2text
from ddgs import DDGS

from .base_tool import BaseTool, ToolContext, ToolResult


class WebFetchTool(BaseTool[Dict[str, Any]]):
    """网页获取工具 - 从指定 URL 获取内容"""
    
    # 配置常量
    MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB
    DEFAULT_TIMEOUT = 30  # 30 seconds
    MAX_TIMEOUT = 120  # 2 minutes
    CACHE_DURATION = 15 * 60  # 15 minutes
    
    def __init__(self):
        description = """从指定的 URL 获取内容。

功能特性：
- 从有效的 URL 获取和分析网页内容
- 支持多种输出格式（text、markdown、html）
- 自动处理 HTML 到 Markdown 的转换
- 内置 15 分钟缓存机制，提高重复访问效率
- 支持自定义超时设置

使用说明：
- 重要：如果有可用的 MCP 提供的网页获取工具，请优先使用那个工具，因为它可能有更少的限制。所有 MCP 提供的工具都以 "mcp__" 开头
- URL 必须是完整有效的 URL
- HTTP URL 将自动升级为 HTTPS
- 此工具是只读的，不会修改任何文件
- 如果内容很大，结果可能会被总结
- 包含自清理的 15 分钟缓存，以便在重复访问同一 URL 时获得更快的响应"""
        
        super().__init__("webfetch", description)
        self._cache: Dict[str, Tuple[str, float]] = {}  # URL -> (content, timestamp)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要获取内容的 URL"
                },
                "format": {
                    "type": "string",
                    "enum": ["text", "markdown", "html"],
                    "description": "返回内容的格式（text、markdown 或 html）",
                    "default": "markdown"
                },
                "timeout": {
                    "type": "number",
                    "description": "可选的超时时间（秒，最大 120）",
                    "minimum": 1,
                    "maximum": 120,
                    "default": 30
                }
            },
            "required": ["url", "format"]
        }
    
    def _clean_cache(self):
        """清理过期的缓存条目"""
        current_time = time.time()
        expired_keys = [
            url for url, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.CACHE_DURATION
        ]
        for key in expired_keys:
            del self._cache[key]
    
    def _get_from_cache(self, url: str) -> Optional[str]:
        """从缓存获取内容"""
        self._clean_cache()
        if url in self._cache:
            content, timestamp = self._cache[url]
            if time.time() - timestamp <= self.CACHE_DURATION:
                return content
            else:
                del self._cache[url]
        return None
    
    def _set_cache(self, url: str, content: str):
        """设置缓存内容"""
        self._cache[url] = (content, time.time())
    
    def _validate_url(self, url: str) -> str:
        """验证和标准化 URL"""
        if not url.startswith(("http://", "https://")):
            raise ValueError("URL 必须以 http:// 或 https:// 开头")
        
        # 自动将 HTTP 升级为 HTTPS（如果合适）
        if url.startswith("http://"):
            https_url = url.replace("http://", "https://", 1)
            return https_url
        
        return url
    
    def _extract_text_from_html(self, html: str) -> str:
        """从 HTML 中提取纯文本"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # 移除脚本和样式元素
        for element in soup(['script', 'style', 'noscript', 'iframe', 'object', 'embed']):
            element.decompose()
        
        # 获取文本内容
        text = soup.get_text()
        
        # 清理空白字符
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def _convert_html_to_markdown(self, html: str) -> str:
        """将 HTML 转换为 Markdown"""
        # 配置 html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.body_width = 0  # 不换行
        h.unicode_snob = True
        h.skip_internal_links = True
        
        # 转换
        markdown = h.handle(html)
        
        # 清理多余的空行
        markdown = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown)
        
        return markdown.strip()
    
    async def _fetch_content(self, url: str, timeout: int) -> Tuple[str, str]:
        """获取网页内容"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN,zh;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.get(url, headers=headers) as response:
                if not response.ok:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"请求失败，状态码: {response.status}"
                    )
                
                # 检查内容长度
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > self.MAX_RESPONSE_SIZE:
                    raise ValueError("响应过大（超过 5MB 限制）")
                
                # 读取内容
                content = await response.read()
                if len(content) > self.MAX_RESPONSE_SIZE:
                    raise ValueError("响应过大（超过 5MB 限制）")
                
                # 解码内容
                charset = 'utf-8'
                content_type = response.headers.get('content-type', '')
                if 'charset=' in content_type:
                    charset = content_type.split('charset=')[1].split(';')[0].strip()
                
                try:
                    text_content = content.decode(charset)
                except UnicodeDecodeError:
                    text_content = content.decode('utf-8', errors='ignore')
                
                return text_content, content_type
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行网页获取"""
        url = params["url"]
        format_type = params.get("format", "markdown")
        timeout = min(params.get("timeout", self.DEFAULT_TIMEOUT), self.MAX_TIMEOUT)
        
        try:
            # 验证 URL
            url = self._validate_url(url)
            
            # 检查缓存
            cached_content = self._get_from_cache(url)
            if cached_content:
                content, content_type = cached_content, "text/html (cached)"
            else:
                # 获取内容
                content, content_type = await self._fetch_content(url, timeout)
                # 缓存内容
                self._set_cache(url, content)
            
            title = f"{url} ({content_type})"
            
            # 根据格式处理内容
            if format_type == "text":
                if "text/html" in content_type:
                    output = self._extract_text_from_html(content)
                else:
                    output = content
            elif format_type == "markdown":
                if "text/html" in content_type:
                    output = self._convert_html_to_markdown(content)
                else:
                    output = f"```\n{content}\n```"
            elif format_type == "html":
                output = content
            else:
                output = content
            
            return ToolResult(
                title=title,
                output=output,
                metadata={
                    "url": url,
                    "content_type": content_type,
                    "format": format_type,
                    "content_length": len(content),
                    "cached": "cached" in content_type
                }
            )
            
        except ValueError as e:
            return ToolResult(
                title=f"参数错误: {url}",
                output=str(e),
                metadata={"error": "validation_error", "url": url}
            )
        except aiohttp.ClientError as e:
            return ToolResult(
                title=f"网络错误: {url}",
                output=f"无法获取网页内容: {str(e)}",
                metadata={"error": "network_error", "url": url}
            )
        except asyncio.TimeoutError:
            return ToolResult(
                title=f"超时错误: {url}",
                output=f"请求超时（{timeout}秒）",
                metadata={"error": "timeout_error", "url": url, "timeout": timeout}
            )
        except Exception as e:
            return ToolResult(
                title=f"未知错误: {url}",
                output=f"获取网页时发生错误: {str(e)}",
                metadata={"error": "unknown_error", "url": url, "error_message": str(e)}
            )


class WebSearchTool(BaseTool[Dict[str, Any]]):
    """网络搜索工具 - 使用 DuckDuckGo 搜索"""
    
    def __init__(self):
        description = """使用 DuckDuckGo 搜索引擎进行网络搜索。

功能特性：
- 使用 DuckDuckGo 搜索引擎进行网络搜索
- 支持多种搜索类型（网页、新闻、图片等）
- 返回结构化的搜索结果
- 包含标题、URL、摘要等信息
- 支持搜索结果数量限制

使用说明：
- 提供搜索查询词
- 可以指定搜索类型和结果数量
- 搜索结果包含相关网页的标题、URL 和摘要
- 适用于获取最新信息和研究主题"""
        
        super().__init__("websearch", description)
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大搜索结果数量",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 10
                },
                "region": {
                    "type": "string",
                    "description": "搜索区域（如 'us-en', 'zh-cn'）",
                    "default": "wt-wt"
                },
                "safesearch": {
                    "type": "string",
                    "enum": ["on", "moderate", "off"],
                    "description": "安全搜索设置",
                    "default": "moderate"
                },
                "timelimit": {
                    "type": "string",
                    "enum": ["d", "w", "m", "y"],
                    "description": "时间限制（d=天，w=周，m=月，y=年）",
                    "default": None
                }
            },
            "required": ["query"]
        }
    
    def _format_search_results(self, results: list) -> str:
        """格式化搜索结果"""
        if not results:
            return "未找到相关搜索结果。"
        
        formatted_results = []
        for i, result in enumerate(results, 1):
            title = result.get('title', '无标题')
            url = result.get('href', '')
            body = result.get('body', '无描述')
            
            formatted_result = f"""**{i}. {title}**
URL: {url}
摘要: {body}
"""
            formatted_results.append(formatted_result)
        
        return "\n".join(formatted_results)
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行网络搜索"""
        query = params["query"]
        max_results = params.get("max_results", 10)
        region = params.get("region", "wt-wt")
        safesearch = params.get("safesearch", "moderate")
        timelimit = params.get("timelimit")
        
        if not query.strip():
            return ToolResult(
                title="搜索错误",
                output="搜索查询不能为空",
                metadata={"error": "empty_query"}
            )
        
        try:
            # 使用 DuckDuckGo 搜索
            with DDGS() as ddgs:
                search_params = {
                    "region": region,
                    "safesearch": safesearch,
                    "max_results": max_results
                }
                
                if timelimit:
                    search_params["timelimit"] = timelimit
                
                results = list(ddgs.text(query, **search_params))
            
            if not results:
                return ToolResult(
                    title=f"搜索结果: {query}",
                    output="未找到相关搜索结果。请尝试使用不同的关键词。",
                    metadata={
                        "query": query,
                        "results_count": 0,
                        "region": region
                    }
                )
            
            formatted_output = self._format_search_results(results)
            
            return ToolResult(
                title=f"搜索结果: {query}",
                output=formatted_output,
                metadata={
                    "query": query,
                    "results_count": len(results),
                    "region": region,
                    "safesearch": safesearch,
                    "timelimit": timelimit,
                    "raw_results": results[:5]  # 只保存前5个原始结果
                }
            )
            
        except Exception as e:
            return ToolResult(
                title=f"搜索错误: {query}",
                output=f"搜索过程中发生错误: {str(e)}",
                metadata={
                    "error": "search_error",
                    "query": query,
                    "error_message": str(e)
                }
            )
