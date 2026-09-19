# -*- coding: utf-8 -*-
"""conftest.py —— 把 service/ 加进 import 路径，并提供临时数据库。"""
import importlib
import os
import sys

GEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE = os.path.join(GEN, "service")
for p in (SERVICE, GEN):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402

import kucun  # noqa: E402
from zhongzi import SHANGPIN_LIEBIAO  # noqa: E402


@pytest.fixture()
def ku(tmp_path):
    """一个新建的空数据库（已建表 + 灌种子）。"""
    lu = str(tmp_path / "kucun.db")
    kucun.chushihua_zhongzi(lu, SHANGPIN_LIEBIAO)
    return lu


@pytest.fixture()
def kehu(tmp_path, monkeypatch):
    """
    FastAPI 的测试客户端，指向临时库。

    为什么要 reload：app.py 在模块级读环境变量 KUCUN_DB 决定数据库路径，
    不 reload 的话所有测试会共用同一个库，互相污染。
    """
    monkeypatch.setenv("KUCUN_DB", str(tmp_path / "kucun.db"))
    import app as app_module
    importlib.reload(app_module)

    from fastapi.testclient import TestClient
    with TestClient(app_module.app) as ke:
        yield ke
