"""Style registry loaded from knowledge base.

This module centralizes access to `knowledge/design_2026.json` so the rest of the
codebase doesn't depend on the deprecated DesignerAgent for style discovery.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StyleInfo:
    key: str
    name: str
    description: str
    lighting: str | None = None
    composition: str | None = None
    background: list[str] | None = None
    prompt_template: str | None = None
    negative_prompt: str | None = None


def _knowledge_path() -> Path:
    base = Path(os.getenv("KNOWLEDGE_DIR", "knowledge"))
    return base / "design_2026.json"


def load_styles() -> dict[str, StyleInfo]:
    path = _knowledge_path()
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        kb = json.load(f)
    styles = kb.get("styles", {}) or {}
    out: dict[str, StyleInfo] = {}
    for key, data in styles.items():
        if not isinstance(data, dict):
            continue
        out[key] = StyleInfo(
            key=key,
            name=str(data.get("name", key)),
            description=str(data.get("description", "")),
            lighting=data.get("lighting"),
            composition=data.get("composition"),
            background=data.get("background"),
            prompt_template=data.get("prompt_template"),
            negative_prompt=data.get("negative_prompt"),
        )
    return out


def get_available_style_keys() -> list[str]:
    return sorted(load_styles().keys())


def build_visual_direction_from_style(style_key: str) -> str:
    """Returns a concise directive for CreativeEngine based on a style key."""
    styles = load_styles()
    s = styles.get(style_key)
    if not s:
        return ""
    parts: list[str] = []
    parts.append(f"Use design style '{s.key}' ({s.name}).")
    if s.description:
        parts.append(f"Style description: {s.description}")
    if s.lighting:
        parts.append(f"Lighting: {s.lighting}")
    if s.composition:
        parts.append(f"Composition: {s.composition}")
    if s.background:
        bg = ", ".join([str(x) for x in s.background][:4])
        if bg:
            parts.append(f"Background suggestions: {bg}")
    if s.prompt_template:
        parts.append("Incorporate the style prompt template intent.")
    return "\n".join(parts)
