"""Backward-compatible import path. Prefer atlas.data.get_adapter."""

from atlas.data import get_adapter

__all__ = ["get_adapter"]
