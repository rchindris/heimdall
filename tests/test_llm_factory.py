"""Tests for the LLM provider abstraction layer."""

import asyncio
from pathlib import Path

import pytest

from heimdall.config import AdminConfig
from heimdall.hooks import set_config
from heimdall.llm import LLMRunRequest, create_llm_client
from heimdall.llm.anthropic_client import AnthropicLLMClient
from heimdall.llm.openrouter_client import OpenRouterLLMClient, ToolExecutor


class TestFactory:
    def test_returns_anthropic_client_by_default(self):
        cfg = AdminConfig()
        client = create_llm_client(cfg)
        assert isinstance(client, AnthropicLLMClient)

    def test_returns_openrouter_client_when_requested(self):
        cfg = AdminConfig(llm_provider="openrouter")
        client = create_llm_client(cfg)
        assert isinstance(client, OpenRouterLLMClient)


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_read_write_cycle(self, tmp_path: Path):
        cfg = AdminConfig()
        set_config(cfg)
        executor = ToolExecutor(cfg)
        file_path = tmp_path / "sample.txt"
        content = "hello world"
        await executor.run("Write", {"path": str(file_path), "content": content})
        data = await executor.run("Read", {"path": str(file_path)})
        assert content in data

    @pytest.mark.asyncio
    async def test_glob_lists_files(self, tmp_path: Path):
        cfg = AdminConfig()
        set_config(cfg)
        executor = ToolExecutor(cfg)
        (tmp_path / "a.txt").write_text("one")
        (tmp_path / "b.txt").write_text("two")
        result = await executor.run("Glob", {"pattern": str(tmp_path / "*.txt")})
        assert "a.txt" in result
        assert "b.txt" in result
