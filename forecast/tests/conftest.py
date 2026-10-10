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


@pytest.fixture
def trained_models(tmp_path, site, monkeypatch):
    """A small trained model set under tmp_path/models, as cmd_train would write it."""
    import json

    import baselines
    import model

    root = tmp_path / "models"
    t = model.synthetic_table(site, "2024-06-01", 150)
    model.save(model.train(t, max_rounds=60), root / "sky")
    t[["month", "hour", "k"]].to_parquet(root / "climatology.parquet", index=False)
    (root / "raw_forecast.json").write_text(json.dumps(baselines.residual_offsets(t)))
    (root / "choice.json").write_text(json.dumps({"model": "lightgbm", "pinball10": {}}))
    monkeypatch.setattr(config, "MODELS", root)
    return root
