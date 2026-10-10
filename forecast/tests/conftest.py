import json
import pathlib

import pytest

import config

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def site():
    return config.Site("test site", 25.29, 55.48, 23.0)


@pytest.fixture
def node_cfg():
    # named node_cfg so it never shadows the `node` module inside tests
    return config.Node("node-01", 1, 0.0, 180.0)


@pytest.fixture
def fixture_json():
    def load(name):
        return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))

    return load
