"""Named playlist mood colors → curated hex stops for UI gradients."""

from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class PlaylistColor(StrEnum):
    LIGHT_BLUE = "light_blue"
    WASHED_BLUE = "washed_blue"
    DARK_BLUE = "dark_blue"
    TEAL = "teal"
    MINT = "mint"
    GREEN = "green"
    FOREST = "forest"
    YELLOW = "yellow"
    AMBER = "amber"
    ORANGE = "orange"
    CORAL = "coral"
    LIGHT_RED = "light_red"
    ROSE = "rose"
    DARK_RED = "dark_red"
    PINK = "pink"
    MAGENTA = "magenta"
    LAVENDER = "lavender"
    PURPLE = "purple"
    VIOLET = "violet"
    INDIGO = "indigo"
    SLATE = "slate"
    CHARCOAL = "charcoal"


class PlaylistColorEntry(TypedDict):
    value: str
    label: str
    hint: str
    hexes: tuple[str, str, str]


# Single catalog: enum values, UI labels, LLM/UI hints, gradient stops.
PLAYLIST_COLOR_CATALOG: list[PlaylistColorEntry] = [
    {
        "value": PlaylistColor.LIGHT_BLUE.value,
        "label": "Light blue",
        "hint": "air, sky, soft focus",
        "hexes": ("#8ec5e8", "#5ea3d4", "#3a7aad"),
    },
    {
        "value": PlaylistColor.WASHED_BLUE.value,
        "label": "Washed blue",
        "hint": "melancholy, rainy, wistful",
        "hexes": ("#9bb0c2", "#6f879c", "#4a5f70"),
    },
    {
        "value": PlaylistColor.DARK_BLUE.value,
        "label": "Dark blue",
        "hint": "night, deep focus, cool",
        "hexes": ("#3d6f9e", "#2a4f78", "#1a334f"),
    },
    {
        "value": PlaylistColor.TEAL.value,
        "label": "Teal",
        "hint": "calm, aquatic, clean",
        "hexes": ("#5db8b0", "#3a8f8a", "#256660"),
    },
    {
        "value": PlaylistColor.MINT.value,
        "label": "Mint",
        "hint": "fresh, light, breezy",
        "hexes": ("#8fd4b8", "#5fb893", "#3d8568"),
    },
    {
        "value": PlaylistColor.GREEN.value,
        "label": "Green",
        "hint": "nature, growth, easy",
        "hexes": ("#7cbc6e", "#549a4a", "#3a6e35"),
    },
    {
        "value": PlaylistColor.FOREST.value,
        "label": "Forest",
        "hint": "earthy, grounded, dense",
        "hexes": ("#4f8a5b", "#356344", "#234331"),
    },
    {
        "value": PlaylistColor.YELLOW.value,
        "label": "Yellow",
        "hint": "bright, sunny, playful",
        "hexes": ("#e8d06a", "#d4b23a", "#a88820"),
    },
    {
        "value": PlaylistColor.AMBER.value,
        "label": "Amber",
        "hint": "warm, golden hour",
        "hexes": ("#e8b45a", "#d4922e", "#a86c1c"),
    },
    {
        "value": PlaylistColor.ORANGE.value,
        "label": "Orange",
        "hint": "energetic, upbeat",
        "hexes": ("#e8924a", "#d06e28", "#a0501c"),
    },
    {
        "value": PlaylistColor.CORAL.value,
        "label": "Coral",
        "hint": "friendly, lively",
        "hexes": ("#e88878", "#d05e50", "#a04038"),
    },
    {
        "value": PlaylistColor.LIGHT_RED.value,
        "label": "Light red",
        "hint": "warm affection",
        "hexes": ("#e89890", "#d46a62", "#b04842"),
    },
    {
        "value": PlaylistColor.ROSE.value,
        "label": "Rose",
        "hint": "romantic, tender",
        "hexes": ("#d87890", "#b85068", "#8a3850"),
    },
    {
        "value": PlaylistColor.DARK_RED.value,
        "label": "Dark red",
        "hint": "intense, passionate",
        "hexes": ("#b84848", "#8a3030", "#5c2020"),
    },
    {
        "value": PlaylistColor.PINK.value,
        "label": "Pink",
        "hint": "sweet, dreamy",
        "hexes": ("#e8a0c0", "#d070a0", "#a84878"),
    },
    {
        "value": PlaylistColor.MAGENTA.value,
        "label": "Magenta",
        "hint": "bold, nightlife",
        "hexes": ("#d060b0", "#a83888", "#782060"),
    },
    {
        "value": PlaylistColor.LAVENDER.value,
        "label": "Lavender",
        "hint": "soft, dreamy ambient",
        "hexes": ("#b8a8d8", "#9080c0", "#685898"),
    },
    {
        "value": PlaylistColor.PURPLE.value,
        "label": "Purple",
        "hint": "creative, lush",
        "hexes": ("#9a68c8", "#7848a8", "#543078"),
    },
    {
        "value": PlaylistColor.VIOLET.value,
        "label": "Violet",
        "hint": "mysterious, lush night",
        "hexes": ("#8858c0", "#6838a0", "#482870"),
    },
    {
        "value": PlaylistColor.INDIGO.value,
        "label": "Indigo",
        "hint": "deep, contemplative",
        "hexes": ("#6878c8", "#4858a8", "#303878"),
    },
    {
        "value": PlaylistColor.SLATE.value,
        "label": "Slate",
        "hint": "neutral, grey, balanced",
        "hexes": ("#8a96a8", "#5e6a7c", "#3e4858"),
    },
    {
        "value": PlaylistColor.CHARCOAL.value,
        "label": "Charcoal",
        "hint": "dark, moody, minimal",
        "hexes": ("#5a6068", "#3a4048", "#242830"),
    },
]

PLAYLIST_COLOR_HEX: dict[PlaylistColor, tuple[str, str, str]] = {
    PlaylistColor(entry["value"]): entry["hexes"] for entry in PLAYLIST_COLOR_CATALOG
}

PLAYLIST_COLOR_HINTS: dict[PlaylistColor, str] = {
    PlaylistColor(entry["value"]): entry["hint"] for entry in PLAYLIST_COLOR_CATALOG
}

PLAYLIST_COLOR_LABELS: dict[PlaylistColor, str] = {
    PlaylistColor(entry["value"]): entry["label"] for entry in PLAYLIST_COLOR_CATALOG
}


def playlist_colors_for_openapi() -> list[dict[str, object]]:
    return [
        {
            "value": entry["value"],
            "label": entry["label"],
            "hint": entry["hint"],
            "hexes": list(entry["hexes"]),
        }
        for entry in PLAYLIST_COLOR_CATALOG
    ]


def parse_playlist_color(value: str | PlaylistColor) -> PlaylistColor:
    if isinstance(value, PlaylistColor):
        return value
    try:
        return PlaylistColor(value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(c.value for c in PlaylistColor)
        raise ValueError(f"Invalid playlist color. Allowed: {allowed}") from exc


def theme_hexes(color: str | PlaylistColor | None) -> list[str]:
    if color is None:
        return []
    try:
        key = parse_playlist_color(color)
    except ValueError:
        return []
    return list(PLAYLIST_COLOR_HEX[key])


def color_tool_hint() -> str:
    """Compact enum list for LLM tool descriptions."""
    parts = [
        f"{color.value} ({PLAYLIST_COLOR_HINTS[color]})" for color in PlaylistColor
    ]
    return "; ".join(parts)
