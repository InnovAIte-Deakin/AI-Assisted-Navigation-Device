"""Package and standalone import checks for Predictive Path utilities."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
PREDICTIVE_PATH_DIR = BACKEND_DIR / "predictive_path"
PACKAGE_MODULES = (
    "predictive_path.predictive_path",
    "predictive_path.evaluate_model",
    "predictive_path.predict_with_model",
)
STANDALONE_SCRIPTS = (
    "predictive_path.py",
    "evaluate_model.py",
    "predict_with_model.py",
)
_MISSING = object()


def _is_predictive_path_module(module_name: str) -> bool:
    return (
        module_name == "ml_predictor"
        or module_name == "predictive_path"
        or module_name.startswith("predictive_path.")
    )


def _clear_predictive_path_modules() -> None:
    for module_name in tuple(sys.modules):
        if _is_predictive_path_module(module_name):
            sys.modules.pop(module_name)


@pytest.fixture
def import_environment() -> Iterator[None]:
    """Provide only the NumPy symbol needed while modules are imported."""
    original_modules = {
        module_name: module
        for module_name, module in sys.modules.items()
        if _is_predictive_path_module(module_name)
    }
    original_sys_path = sys.path.copy()
    original_numpy = sys.modules.get("numpy", _MISSING)

    numpy_stub = ModuleType("numpy")
    numpy_stub.ndarray = object

    try:
        _clear_predictive_path_modules()
        sys.path.insert(0, str(BACKEND_DIR))
        sys.modules["numpy"] = numpy_stub
        yield
    finally:
        _clear_predictive_path_modules()
        if original_numpy is _MISSING:
            sys.modules.pop("numpy", None)
        else:
            sys.modules["numpy"] = original_numpy
        sys.modules.update(original_modules)
        sys.path[:] = original_sys_path


def test_predictive_path_modules_import_through_package(
    import_environment: None,
) -> None:
    predictor_module = importlib.import_module("predictive_path.ml_predictor")

    for module_name in PACKAGE_MODULES:
        module = importlib.import_module(module_name)
        assert module.MLPredictor is predictor_module.MLPredictor


@pytest.mark.parametrize("script_name", STANDALONE_SCRIPTS)
def test_predictive_path_scripts_keep_direct_import_support(
    import_environment: None, script_name: str
) -> None:
    sys.path.insert(0, str(PREDICTIVE_PATH_DIR))
    module_name = f"direct_import_{Path(script_name).stem}"
    spec = importlib.util.spec_from_file_location(
        module_name, PREDICTIVE_PATH_DIR / script_name
    )
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    predictor_module = importlib.import_module("ml_predictor")
    assert module.MLPredictor is predictor_module.MLPredictor
