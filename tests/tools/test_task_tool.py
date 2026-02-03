#!/usr/bin/env python3
"""TaskTool 单元测试（不依赖真实 LLM / Session）"""

import unittest
import asyncio
import sys
import os
from unittest.mock import patch, AsyncMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from tools.task_tool import TaskTool
from tools.task_manager import TaskManager
from tools.base_tool import ToolContext


class TestTaskTool(unittest.TestCase):
    def setUp(self):
        self.task_tool = TaskTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent",
        )
        self.task_manager = TaskManager()
        self.task_manager.clear_sessions()

    def test_parameters_schema_only_includes_subagents(self):
        schema = self.task_tool.get_parameters_schema()
        enum_values = schema["properties"]["subagent_type"]["enum"]

        self.assertIn("general", enum_values)
        self.assertIn("explore", enum_values)
        # plan 是 primary agent，不应作为 task subagent 出现
        self.assertNotIn("plan", enum_values)

    def test_unknown_subagent_type_error(self):
        async def run_test():
            result = await self.task_tool.execute(
                {
                    "description": "测试任务",
                    "task_prompt": "执行某个任务",
                    "subagent_type": "nonexistent_agent",
                },
                self.context,
            )

            self.assertIn("未知", result.title)
            self.assertEqual(result.metadata["error"], "unknown_subagent_type")
            self.assertEqual(result.metadata["requested_type"], "nonexistent_agent")
            self.assertIn("available_types", result.metadata)

        asyncio.run(run_test())

    def test_primary_agent_rejected(self):
        async def run_test():
            # plan 存在，但 mode=primary，不允许被 task 调用
            result = await self.task_tool.execute(
                {
                    "description": "测试 plan",
                    "task_prompt": "给我一个方案",
                    "subagent_type": "plan",
                },
                self.context,
            )

            self.assertIn("错误的代理类型", result.title)
            self.assertEqual(result.metadata["error"], "invalid_agent_mode")

        asyncio.run(run_test())

    def test_execute_updates_task_manager_session(self):
        async def run_test():
            with patch.object(self.task_tool, "_execute_subagent", new=AsyncMock(return_value=("OK", []))):
                result = await self.task_tool.execute(
                    {
                        "description": "执行任务",
                        "task_prompt": "做点什么",
                        "subagent_type": "explore",
                    },
                    self.context,
                )

            self.assertEqual(result.metadata["status"], "completed")
            task_session_id = result.metadata["session_id"]
            self.assertTrue(task_session_id.startswith("task_"))

            record = self.task_manager.get_session(task_session_id)
            self.assertIsNotNone(record)
            self.assertEqual(record.status, "completed")
            self.assertEqual(record.result, "OK")

        asyncio.run(run_test())

    def test_cancel_subagent_uses_task_session_id(self):
        async def run_test():
            record = self.task_manager.create_session(
                parent_session_id=self.context.session_id,
                subagent_type="explore",
                task_description="测试取消",
            )

            mock_session = AsyncMock()
            mock_session.stop = AsyncMock()
            mock_session.cleanup = AsyncMock()

            # 注意：active map 的 key 应为 task_session_id（record.id）
            self.task_tool._active_subagents[record.id] = mock_session

            ok = await self.task_tool.cancel_subagent(record.id)
            self.assertTrue(ok)

            mock_session.stop.assert_called_once()
            mock_session.cleanup.assert_called_once()

            updated = self.task_manager.get_session(record.id)
            self.assertEqual(updated.status, "cancelled")
            self.assertIn("取消", updated.error)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
