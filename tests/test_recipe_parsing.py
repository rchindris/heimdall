"""Tests for recipe parsing with python-frontmatter."""

from pathlib import Path

import frontmatter

from heimdall.models import RecipeMetadata, RecipeSpec


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

    def test_parse_to_recipe_spec(self):
        post = frontmatter.loads(SAMPLE_RECIPE)
        metadata = RecipeMetadata(**post.metadata)

        # Split content into sections by h2 headers
        content = post.content
        sections = []
        current = []
        for line in content.split("\n"):
            if line.startswith("## "):
                if current:
                    sections.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current))

        spec = RecipeSpec(
            metadata=metadata,
            raw_content=content,
            sections=sections,
        )
        assert spec.metadata.name == "Test Recipe"
        # sections[0] is the H1 preamble, H2 sections follow
        assert len(spec.sections) >= 3
        assert "nginx" in spec.sections[1]
        assert "firewall" in spec.sections[2]

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

    def test_empty_frontmatter(self):
        raw = "# Just a title\n\nSome content."
        post = frontmatter.loads(raw)
        # No frontmatter — metadata dict is empty
        metadata = RecipeMetadata(**post.metadata)
        assert metadata.name == ""
        assert metadata.tags == []
