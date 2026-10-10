import pandas as pd
import pytest

import influx


class FakeResp:
    def __init__(self, status=204, text=""):
        self.status_code, self.text, self.ok = status, text, status < 400


class FakeSession:
    def __init__(self, resp=None):
        self.resp, self.calls = resp or FakeResp(), []

    def post(self, url, params=None, data=None, headers=None, auth=None, json=None, timeout=None):
        self.calls.append({"url": url, "params": params, "data": data, "headers": headers, "auth": auth, "json": json})
        return self.resp

    def get(self, url, params=None, headers=None, auth=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "auth": auth})
        return self.resp


V2 = influx.Settings("http://db:8086", "2", "tok", "org1", "sdp", "", "", "")
V1 = influx.Settings("http://db:8086", "1", "", "", "", "u", "p", "sdp")


def test_from_env_reads_both_versions():
    s = influx.from_env({"INFLUX_URL": "http://x:8086/", "INFLUX_VERSION": "2", "INFLUX_TOKEN": "t", "INFLUX_ORG": "o", "INFLUX_BUCKET": "b"})
    assert s == influx.Settings("http://x:8086", "2", "t", "o", "b", "", "", "")
    s = influx.from_env({"INFLUX_URL": "http://x:8086", "INFLUX_VERSION": "1", "INFLUX_USER": "u", "INFLUX_PASSWORD": "p", "INFLUX_DB": "d"})
    assert (s.version, s.user, s.database) == ("1", "u", "d")


def test_line_protocol_formatting():
    ts = pd.Timestamp("2026-10-14 06:00", tz="UTC")
    line = influx.line("harvest", {"node": "node 01", "source": "ppk2"}, {"energy_j": 12.5, "seconds": 3600.0, "store_full": False, "lead_h": 3, "issued_at": "2026-10-14T05:00Z"}, ts)
    # 2026-10-14T06:00Z is 1791957600 s after the epoch (checked with pandas)
    assert line == 'harvest,node=node\\ 01,source=ppk2 energy_j=12.5,seconds=3600.0,store_full=false,lead_h=3i,issued_at="2026-10-14T05:00Z" 1791957600000000000'


def test_write_v2_posts_to_api_v2_with_token():
    s = FakeSession()
    influx.write(["m f=1 1"], V2, session=s)
    c = s.calls[0]
    assert c["url"] == "http://db:8086/api/v2/write" and c["params"] == {"org": "org1", "bucket": "sdp", "precision": "ns"}
    assert c["headers"]["Authorization"] == "Token tok" and c["data"] == "m f=1 1"


def test_write_v1_posts_to_write_with_basic_auth():
    s = FakeSession()
    influx.write(["m f=1 1"], V1, session=s)
    c = s.calls[0]
    assert c["url"] == "http://db:8086/write" and c["params"] == {"db": "sdp", "precision": "ns"} and c["auth"] == ("u", "p")


def test_write_raises_on_failure():
    with pytest.raises(influx.InfluxError):
        influx.write(["m f=1 1"], V2, session=FakeSession(FakeResp(401, "unauthorized")))


def test_write_forecast_lines():
    s = FakeSession()
    f = pd.DataFrame({"hour_start": pd.date_range("2026-10-14 06:00", periods=2, freq="h", tz="UTC"), "q10_j": [1.0, 2.0], "q50_j": [2.0, 3.0], "q90_j": [3.0, 4.0]})
    influx.write_forecast(f, "node-01", "lightgbm", pd.Timestamp("2026-10-14 05:00", tz="UTC"), True, V2, session=s)
    lines = s.calls[0]["data"].splitlines()
    assert lines[0].startswith("harvest_forecast,model=lightgbm,node=node-01 ")
    assert "lead_h=1i" in lines[0] and "lead_h=2i" in lines[1] and "node_ratio_default=true" in lines[0]


def test_read_harvest_v2_parses_flux_csv():
    csv = (
        ",result,table,_start,_stop,_time,_measurement,node,source,energy_j,seconds,store_full\r\n"
        ",_result,0,2026-10-01T00:00:00Z,2026-10-15T00:00:00Z,2026-10-14T06:00:00Z,harvest,node-01,ppk2,108.0,3600,false\r\n"
        ",_result,0,2026-10-01T00:00:00Z,2026-10-15T00:00:00Z,2026-10-14T07:00:00Z,harvest,node-01,ppk2,50.0,1800,true\r\n"
    )
    s = FakeSession(FakeResp(200, csv))
    r = influx.read_harvest("node-01", pd.Timestamp("2026-10-01", tz="UTC"), V2, session=s)
    assert list(r.columns) == influx.RECORD_COLUMNS and len(r) == 2
    assert r["store_full"].tolist() == [False, True] and r["energy_j"].tolist() == [108.0, 50.0]
    assert str(r["hour_start"].dtype) == "datetime64[ns, UTC]"
    assert "node-01" in s.calls[0]["json"]["query"]


def test_read_harvest_v1_parses_json():
    import json

    body = json.dumps({"results": [{"series": [{"name": "harvest", "columns": ["time", "energy_j", "seconds", "store_full", "source"], "values": [["2026-10-14T06:00:00Z", 108.0, 3600, False, "ppk2"]]}]}]})
    s = FakeSession(FakeResp(200, body))
    r = influx.read_harvest("node-01", pd.Timestamp("2026-10-01", tz="UTC"), V1, session=s)
    assert len(r) == 1 and r["node"].iloc[0] == "node-01" and r["energy_j"].iloc[0] == 108.0


def test_read_harvest_empty():
    s = FakeSession(FakeResp(200, "\r\n"))
    r = influx.read_harvest("node-01", pd.Timestamp("2026-10-01", tz="UTC"), V2, session=s)
    assert r.empty and list(r.columns) == influx.RECORD_COLUMNS


def test_read_harvest_v1_raises_on_query_error():
    import json

    body = json.dumps({"results": [{"error": "database not found: sdp"}]})
    with pytest.raises(influx.InfluxError, match="database not found"):
        influx.read_harvest("node-01", pd.Timestamp("2026-10-01", tz="UTC"), V1, session=FakeSession(FakeResp(200, body)))


def test_read_harvest_v2_raises_when_fields_are_missing():
    csv = ",result,table,_time,node,source,seconds\r\n,_result,0,2026-10-14T06:00:00Z,node-01,ppk2,3600\r\n"
    with pytest.raises(influx.InfluxError, match="energy_j"):
        influx.read_harvest("node-01", pd.Timestamp("2026-10-01", tz="UTC"), V2, session=FakeSession(FakeResp(200, csv)))
