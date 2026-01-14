#!/usr/bin/env python3
"""Hook system unit tests."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
import tempfile
from pathlib import Path
import json

# Keep consistent with existing tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from core.agent_turn import AgentTurn  # noqa: E402
from core.config import Config  # noqa: E402
from core.hooks import HookContext, HooksBase, HookProvider, LoggerHooks, set_hook_provider  # noqa: E402
from core.model_client import ChatResponse  # noqa: E402
from core.protocol import TokenUsage  # noqa: E402
from core.session import Session  # noqa: E402
from tools.base_tool import ToolResult  # noqa: E402


class CollectorHooks(HooksBase):
    """Collects hook events for assertions."""

    def __init__(self):
        self.events = []

    def on_session_start(self, context: HookContext) -> None:
        self.events.append(context)

    def on_session_stop(self, context: HookContext) -> None:
        self.events.append(context)

    def on_task_start(self, context: HookContext) -> None:
        self.events.append(context)

    def on_task_complete(self, context: HookContext) -> None:
        self.events.append(context)

    def on_turn_start(self, context: HookContext) -> None:
        self.events.append(context)

    def on_turn_complete(self, context: HookContext) -> None:
        self.events.append(context)

    def on_llm_start(self, context: HookContext) -> None:
        self.events.append(context)

    def on_llm_complete(self, context: HookContext) -> None:
        self.events.append(context)

    def on_tool_start(self, context: HookContext) -> None:
        self.events.append(context)

    def on_tool_complete(self, context: HookContext) -> None:
        self.events.append(context)

    def on_error(self, context: HookContext) -> None:
        self.events.append(context)


class FailingHook(HooksBase):
    """Hook that raises to test isolation."""

    def on_session_start(self, context: HookContext) -> None:
        raise RuntimeError("boom")


class HookProviderTestCase(unittest.TestCase):
    """Unit tests for HookProvider behavior."""

    def test_provider_dispatches_events(self):
        provider = HookProvider(with_default_processors=False)
        collector = CollectorHooks()
        provider.register_hook(collector)

        provider.on_session_start("s1", {"foo": "bar"})

        self.assertEqual(len(collector.events), 1)
        self.assertEqual(collector.events[0].name, "session.start")
        self.assertEqual(collector.events[0].payload["foo"], "bar")

    def test_default_logger_processor_registered(self):
        provider = HookProvider()

        hooks = provider._hooks
        self.assertTrue(any(isinstance(p, LoggerHooks) for p in hooks))

    def test_provider_disabled_skips_events(self):
        provider = HookProvider(disabled=True, with_default_processors=False)
        collector = CollectorHooks()
        provider.register_hook(collector)

        provider.on_task_start("s1", "sub1", {})

        self.assertEqual(len(collector.events), 0)

    def test_provider_isolates_processor_failures(self):
        provider = HookProvider(with_default_processors=False)
        collector = CollectorHooks()
        provider.register_hook(FailingHook())
        provider.register_hook(collector)

        provider.on_session_start("s1", {})

        self.assertEqual(len(collector.events), 1)
        self.assertEqual(collector.events[0].name, "session.start")

    def test_provider_sets_context_fields(self):
        provider = HookProvider(with_default_processors=False)
        collector = CollectorHooks()
        provider.register_hook(collector)

        provider.on_task_start("s1", "sub1", {"x": 1})

        self.assertEqual(len(collector.events), 1)
        context = collector.events[0]
        self.assertEqual(context.name, "task.start")
        self.assertEqual(context.session_id, "s1")
        self.assertEqual(context.submission_id, "sub1")
        self.assertEqual(context.payload["x"], 1)
        self.assertTrue(context.timestamp)

    def test_error_hook_includes_name(self):
        provider = HookProvider(with_default_processors=False)
        collector = CollectorHooks()
        provider.register_hook(collector)

        provider.on_error("s1", "sub1", {"message": "boom"})

        self.assertEqual(collector.events[0].name, "error")


class HookIntegrationTestCase(unittest.IsolatedAsyncioTestCase):
    """Integration-style tests for hook emission in existing flow."""

    def setUp(self):
        self.model_client = MagicMock()
        self.model_client.chat_completion = AsyncMock()
        self.model_client.add_assistant_message = MagicMock()
        self.model_client.add_tool_message = MagicMock()

        self.tool_registry = MagicMock()
        self.tool_registry.execute_tool = AsyncMock()

        self.collector = CollectorHooks()
        self.provider = HookProvider(with_default_processors=False)
        self.provider.register_hook(self.collector)

    async def test_agent_turn_emits_turn_hooks(self):
        token_usage = TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)
        response = ChatResponse(
            content="ok",
            tool_calls=[],
            token_usage=token_usage,
            finish_reason="stop",
        )
        self.model_client.chat_completion.return_value = response

        agent_turn = AgentTurn(
            model_client=self.model_client,
            tool_registry=self.tool_registry,
            event_handler=None,
            session_id="session-1",
            hook_provider=self.provider,
        )

        await agent_turn.execute_turn("submission-1")

        names = [event.name for event in self.collector.events]
        self.assertIn("turn.start", names)
        self.assertIn("turn.complete", names)
        self.assertIn("llm.start", names)
        self.assertIn("llm.complete", names)

    async def test_agent_turn_emits_tool_hooks(self):
        tool_call = {
            "id": "call-1",
            "type": "function",
            "function": {"name": "read", "arguments": "{}"},
        }
        response = ChatResponse(
            content="use tool",
            tool_calls=[tool_call],
            token_usage=TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            finish_reason="tool_calls",
        )
        self.model_client.chat_completion.return_value = response
        self.tool_registry.execute_tool.return_value = ToolResult(title="x", output="y")

        agent_turn = AgentTurn(
            model_client=self.model_client,
            tool_registry=self.tool_registry,
            event_handler=None,
            session_id="session-1",
            hook_provider=self.provider,
        )

        await agent_turn.execute_turn("submission-2")

        names = [event.name for event in self.collector.events]
        self.assertIn("tool.start", names)
        self.assertIn("tool.complete", names)

    async def test_session_emits_session_hooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                model="test-model",
                api_key="test-key",
                api_base="https://test.api.com",
                cwd=Path(tmpdir),
                enable_memory=False,
                enable_hooks=True,
                auto_load_project_docs=False,
            )
            set_hook_provider(self.provider)
            session = Session(config)

            await session.start()
            await session.stop()

        names = [event.name for event in self.collector.events]
        self.assertIn("session.start", names)
        self.assertIn("session.stop", names)


class LoggerHooksTestCase(unittest.TestCase):
    """Tests for LoggerHooks JSON output."""

    def test_logger_hooks_outputs_json(self):
        provider = HookProvider(with_default_processors=True)

        with patch("utils.logger.logger.info") as logger_info:
            provider.on_session_start("s1", {"foo": "bar"})

            logger_info.assert_called()
            payload = logger_info.call_args.args[0]
            data = json.loads(payload)
            self.assertEqual(data["name"], "session.start")
            self.assertEqual(data["session_id"], "s1")
            self.assertEqual(data["payload"]["foo"], "bar")


if __name__ == "__main__":
    unittest.main()
