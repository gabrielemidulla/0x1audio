"""Shared pytest fixtures for the ox1audio backend."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
