from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path

DEPLOYMENT_TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(DEPLOYMENT_TOOLS))

from environment_doctor import inspect_environment


class Tensor:
    def __add__(self, _value): return self
    def item(self): return 1


class FakeTorch:
    __version__ = "test"
    class version: cuda = "test"
    class cuda:
        available = True
        @classmethod
        def is_available(cls): return cls.available
        @staticmethod
        def get_device_name(_): return "Fake GPU"
        @staticmethod
        def get_device_properties(_): return type("P", (), {"total_memory": 1})()
        @staticmethod
        def synchronize(_): return None
    @staticmethod
    def empty(_size, *, device):
        assert device == "cuda:0"
        return Tensor()


def versions(name): return "1.0"


def test_all_vision_requirements_and_cuda_usable_pass():
    report = inspect_environment(torch_module=FakeTorch, package_version=versions, port=8000, port_checker=lambda _: True)
    assert report["overall_result"] == "PASS"
    assert report["runtime_environment"]["cuda_usable"] is True


def test_missing_required_and_optional_packages_are_distinguished():
    def missing(name):
        if name in {"torch", "easyocr"}: raise PackageNotFoundError
        return "1"
    report = inspect_environment(torch_module=FakeTorch, package_version=missing)
    states = {item["name"]: item["status"] for item in report["checks"]}
    assert states["package_torch"] == "fail"
    assert states["package_easyocr"] == "warning"


def test_cpu_and_unusable_cuda_are_honest():
    FakeTorch.cuda.available = False
    try:
        cpu = inspect_environment(torch_module=FakeTorch, package_version=versions)
    finally:
        FakeTorch.cuda.available = True
    assert cpu["overall_result"] == "WARNING"
    class Broken(FakeTorch):
        @staticmethod
        def empty(_size, *, device): raise RuntimeError("broken")
    broken = inspect_environment(torch_module=Broken, package_version=versions)
    assert broken["overall_result"] == "FAIL"
