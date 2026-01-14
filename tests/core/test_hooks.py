#!/usr/bin/env python3
"""Hook system unit tests."""

import unittest
from unittest.mock import AsyncMock, MagicMock
import sys
import os
import tempfile
from pathlib import Path

# Keep consistent with existing tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from core.agent_turn import AgentTurn  # noqa: E402
from core.config import Config  # noqa: E402
from core.hooks import HookEvent, HookProcessor, HookProvider, LoggerHookProcessor, set_hook_provider  # noqa: E402
from core.model_client import ChatResponse  # noqa: E402
from core.protocol import TokenUsage  # noqa: E402
from core.session import Session  # noqa: E402
from tools.base_tool import ToolResult  # noqa: E402


class CollectorProcessor(HookProcessor):
    """Collects hook events for assertions."""

    def __init__(self):
        self.events = []

    def on_event(self, event: HookEvent) -> None:
        self.events.append(event)

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass


class FailingProcessor(HookProcessor):
    """Processor that raises to test isolation."""

    def on_event(self, event: HookEvent) -> None:
        raise RuntimeError("boom")

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass


class HookProviderTestCase(unittest.TestCase):
    """Unit tests for HookProvider behavior."""

    def test_provider_dispatches_events(self):
        provider = HookProvider(with_default_processors=False)
        collector = CollectorProcessor()
        provider.register_processor(collector)

        provider.emit_named("session.start", "s1", None, {"foo": "bar"})

        self.assertEqual(len(collector.events), 1)
        self.assertEqual(collector.events[0].name, "session.start")
        self.assertEqual(collector.events[0].payload["foo"], "bar")

    def test_default_logger_processor_registered(self):
        provider = HookProvider()

        processors = provider._multi_processor._processors
        self.assertTrue(any(isinstance(p, LoggerHookProcessor) for p in processors))

    def test_provider_disabled_skips_events(self):
        provider = HookProvider(disabled=True, with_default_processors=False)
        collector = CollectorProcessor()
        provider.register_processor(collector)

        provider.emit_named("task.start", "s1", "sub1", {})

        self.assertEqual(len(collector.events), 0)

    def test_provider_isolates_processor_failures(self):
        provider = HookProvider(with_default_processors=False)
        collector = CollectorProcessor()
        provider.register_processor(FailingProcessor())
        provider.register_processor(collector)

        provider.emit_named("turn.start", "s1", "sub1", {})

        self.assertEqual(len(collector.events), 1)
        self.assertEqual(collector.events[0].name, "turn.start")


class HookIntegrationTestCase(unittest.IsolatedAsyncioTestCase):
    """Integration-style tests for hook emission in existing flow."""

    def setUp(self):
        self.model_client = MagicMock()
        self.model_client.chat_completion = AsyncMock()
        self.model_client.add_assistant_message = MagicMock()
        self.model_client.add_tool_message = MagicMock()

        self.tool_registry = MagicMock()
        self.tool_registry.execute_tool = AsyncMock()

        self.collector = CollectorProcessor()
        self.provider = HookProvider(with_default_processors=False)
        self.provider.register_processor(self.collector)

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


if __name__ == "__main__":
    unittest.main()
