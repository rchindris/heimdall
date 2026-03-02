"""Tests for recipe parsing with python-frontmatter."""

from pathlib import Path

import frontmatter
import pytest

from heimdall.models import RecipeMetadata
from heimdall.recipe_parser import ensure_recipe_supported, load_recipe_spec, summarize_sections


SAMPLE_RECIPE = """\
---
name: Test Recipe
description: A test recipe for unit tests
tags: [test, unit]
os_families: [debian]
requires: []
---

# Test Recipe

## Section One

Install nginx and configure it.

## Section Two

Set up the firewall.
"""


class TestRecipeParsing:
    def test_parse_frontmatter(self):
        post = frontmatter.loads(SAMPLE_RECIPE)
        assert post["name"] == "Test Recipe"
        assert post["description"] == "A test recipe for unit tests"
        assert post["tags"] == ["test", "unit"]
        assert post["os_families"] == ["debian"]

    def test_parse_to_metadata(self):
        post = frontmatter.loads(SAMPLE_RECIPE)
        metadata = RecipeMetadata(**post.metadata)
        assert metadata.name == "Test Recipe"
        assert "test" in metadata.tags
        assert metadata.os_families == ["debian"]

    def test_load_recipe_spec(self, tmp_path):
        recipe_path = tmp_path / "recipe.md"
        recipe_path.write_text(SAMPLE_RECIPE)

        spec = load_recipe_spec(recipe_path)
        assert spec.metadata.name == "Test Recipe"
        assert len(spec.sections) >= 3
        assert "nginx" in spec.sections[1]
        assert "firewall" in spec.sections[2]

    def test_summarize_sections(self, tmp_path):
        recipe_path = tmp_path / "recipe.md"
        recipe_path.write_text(SAMPLE_RECIPE)
        spec = load_recipe_spec(recipe_path)
        summary = summarize_sections(spec)
        assert "1." in summary
        assert "Section One" in summary

    def test_parse_real_recipe(self):
        import pytest

        recipe_path = Path(__file__).parent.parent / "recipes" / "home-server.md"
        if not recipe_path.exists():
            pytest.skip("Recipe file not found")

        post = frontmatter.load(str(recipe_path))
        metadata = RecipeMetadata(**post.metadata)
        assert metadata.name == "Home Server"
        assert "debian" in metadata.os_families
        assert len(post.content) > 0

    def test_ensure_recipe_supported_respects_os_list(self, tmp_path, monkeypatch):
        recipe_path = tmp_path / "recipe.md"
        recipe_path.write_text(SAMPLE_RECIPE)
        spec = load_recipe_spec(recipe_path)

        # Force detect_os_family to return something unsupported
        monkeypatch.setattr("heimdall.recipe_parser.detect_os_family", lambda: "redhat")
        with pytest.raises(ValueError):
            ensure_recipe_supported(spec)

    def test_empty_frontmatter(self):
        raw = "# Just a title\n\nSome content."
        post = frontmatter.loads(raw)
        # No frontmatter — metadata dict is empty
        metadata = RecipeMetadata(**post.metadata)
        assert metadata.name == ""
        assert metadata.tags == []
