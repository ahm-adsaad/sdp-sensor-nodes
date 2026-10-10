"""Sun geometry and clear-sky irradiance for one site.

Every function takes hour starts and evaluates the sky at the middle of the
hour, which is where Open-Meteo's backward-averaged hourly radiation sits.
"""

from __future__ import annotations

import pandas as pd
import pvlib

import config


def _location(site: config.Site) -> pvlib.location.Location:
    return pvlib.location.Location(site.lat, site.lon, tz="UTC", altitude=site.altitude_m)


def hour_mid(hour_start) -> pd.DatetimeIndex:
    return config.utc_ns(hour_start) + pd.Timedelta(minutes=30)


def sun_position(site: config.Site, hour_start) -> pd.DataFrame:
    hs = config.utc_ns(hour_start)
    sp = _location(site).get_solarposition(hour_mid(hs))
    out = pd.DataFrame(
        {
            "elevation": sp["apparent_elevation"].to_numpy(),
            "azimuth": sp["azimuth"].to_numpy(),
            "zenith": sp["apparent_zenith"].to_numpy(),
        },
        index=hs,
    )
    out.index.name = "hour_start"
    return out


def clearsky(site: config.Site, hour_start) -> pd.DataFrame:
    hs = config.utc_ns(hour_start)
    cs = _location(site).get_clearsky(hour_mid(hs), model="ineichen", linke_turbidity=config.LINKE_TURBIDITY)
    out = pd.DataFrame(
        {"cs_ghi": cs["ghi"].to_numpy(), "cs_dni": cs["dni"].to_numpy(), "cs_dhi": cs["dhi"].to_numpy()},
        index=hs,
    ).clip(lower=0.0)
    out.index.name = "hour_start"
    return out


def clearsky_poa(site: config.Site, hour_start, tilt_deg: float, azimuth_deg: float) -> pd.Series:
    hs = config.utc_ns(hour_start)
    cs = clearsky(site, hs)
    if tilt_deg == 0:
        return cs["cs_ghi"].rename("cs_poa")
    sp = sun_position(site, hs)
    poa = pvlib.irradiance.get_total_irradiance(
        tilt_deg, azimuth_deg, sp["zenith"], sp["azimuth"], cs["cs_dni"], cs["cs_ghi"], cs["cs_dhi"]
    )
    return poa["poa_global"].clip(lower=0.0).rename("cs_poa")
