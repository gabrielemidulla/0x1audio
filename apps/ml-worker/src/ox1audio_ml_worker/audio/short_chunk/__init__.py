"""Vendored Short-chunk CNN (MIT) for Jamendo top-50 tagging.

Source: https://github.com/minzwon/sota-music-tagging-models
Only the ShortChunkCNN_Res definition and Res_2d building block are kept.
"""

from ox1audio_ml_worker.audio.short_chunk.model import ShortChunkCNN_Res
from ox1audio_ml_worker.audio.short_chunk.tags import TAGS

__all__ = ["ShortChunkCNN_Res", "TAGS"]
