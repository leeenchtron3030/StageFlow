"""Load only CTranslate2's inference extension, excluding converter imports.

The 4.8.1 public initializer eagerly imports converters/transformers.py, which
imports huggingface_hub even when no conversion is requested. The models.Whisper
public name is a direct re-export of _ext.Whisper. Keep this seam version-pinned.
"""
import ctypes
import importlib.machinery
import importlib.metadata
import importlib.util
import os
import sys
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

_dll_handles: list[Any] = []


@cache
def inference_runtime() -> ModuleType:
    # Reuse an already loaded extension (e.g. a private baseline parity worker).
    existing = sys.modules.get("ctranslate2._ext")
    if existing is not None:
        return existing
    distribution = importlib.metadata.distribution("ctranslate2")
    if distribution.version != "4.8.1":
        raise ImportError("unqualified CTranslate2 runtime")
    package = Path(str(distribution.locate_file("ctranslate2")))
    if sys.platform == "win32":
        _dll_handles.append(os.add_dll_directory(str(package)))
        for library in sorted(package.glob("*.dll")):
            _dll_handles.append(ctypes.CDLL(str(library)))
    binary = next((package / ("_ext" + suffix)
                   for suffix in importlib.machinery.EXTENSION_SUFFIXES
                   if (package / ("_ext" + suffix)).is_file()), None)
    if binary is None:
        raise ImportError("CTranslate2 inference extension unavailable")
    spec = importlib.util.spec_from_file_location("ctranslate2._ext", binary)
    if spec is None or spec.loader is None:
        raise ImportError("CTranslate2 inference extension unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules["ctranslate2._ext"] = module
    return module
