"""Prompt file loader — reads AI prompts from docs/prompt/*.md.

Usage:
    from utils.prompt_loader import load_prompt

    prompt = load_prompt("requirement_refinement")
    template = load_prompt("ui-script-generation")  # may contain {placeholders}
"""

from __future__ import annotations

import re
from pathlib import Path

_prompt_cache: dict[str, str] = {}


def _prompt_dir() -> Path:
    """Path to backend/docs/prompt/, works from any CWD and inside Docker."""
    return Path(__file__).resolve().parents[1] / "docs" / "prompt"


def load_prompt(name: str) -> str:
    """Load a prompt by name (without .md extension).  Cached in memory."""
    if name not in _prompt_cache:
        file_path = _prompt_dir() / f"{name}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        _prompt_cache[name] = file_path.read_text(encoding="utf-8")
    return re.sub(
        r"\n?<!--\s*PROMPT_SECTION:[\w.-]+\s*-->.*?<!--\s*/PROMPT_SECTION\s*-->\n?",
        "\n",
        _prompt_cache[name],
        flags=re.DOTALL,
    ).strip()


def load_prompt_section(name: str, section: str) -> str:
    """Load a section from a prompt file by a level-2 heading."""
    raw_content = _prompt_cache.get(name)
    if raw_content is None:
        load_prompt(name)
        raw_content = _prompt_cache[name]
    block_pattern = (
        rf"<!--\s*PROMPT_SECTION:{re.escape(section)}\s*-->\s*"
        rf"(.*?)\s*<!--\s*/PROMPT_SECTION\s*-->"
    )
    block_match = re.search(block_pattern, raw_content, flags=re.DOTALL)
    if block_match:
        return block_match.group(1).strip()
    content = raw_content
    marker = f"## {section}"
    start = content.find(marker)
    if start < 0:
        raise ValueError(f"Prompt section not found: {name}.md#{section}")
    body_start = content.find("\n", start)
    if body_start < 0:
        return ""
    next_section = content.find("\n## ", body_start + 1)
    if next_section < 0:
        next_section = len(content)
    return content[body_start + 1:next_section].strip()
