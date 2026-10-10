"""Synthetic harvest records. Tagged source=sim; for tests and dry runs only."""

from __future__ import annotations

import pandas as pd

import config
import node as node_mod


def harvest_records(site, node, hour_start, k_actual, ratio, store_full=None, source="sim") -> pd.DataFrame:
    hs = config.utc_ns(hour_start)
    e = node_mod.clear_sky_energy_j(site, node, hs)
    k = pd.Series(k_actual, index=hs) if not isinstance(k_actual, pd.Series) else k_actual.reindex(hs).fillna(0.0)
    r = pd.Series(ratio, index=hs) if not isinstance(ratio, pd.Series) else ratio.reindex(hs).ffill().bfill()
    full = pd.Series(False, index=hs) if store_full is None else store_full.reindex(hs).fillna(False).astype(bool)
    energy = (e * k * r).where(~full, 0.0)
    return pd.DataFrame(
        {
            "node": node.id,
            "hour_start": hs,
            "energy_j": energy.to_numpy(),
            "seconds": 3600.0,
            "source": source,
            "store_full": full.to_numpy(),
        }
    )
