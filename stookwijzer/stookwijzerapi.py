"""The Stookwijze API."""
from datetime import datetime, timedelta

import aiohttp
import asyncio
import json
import logging
import pytz

_LOGGER = logging.getLogger(__name__)


class Stookwijzer(object):
    """The Stookwijze API."""

    def __init__(self, session: aiohttp.ClientSession, x: float, y: float):
        self._boundary_box = self.get_boundary_box(x, y)
        self._advice = None
        self._alert = None
        self._last_updated = None
        self._stookwijzer = None
        self._session = session

    @property
    def advice(self) -> str | None:
        """Return the advice."""
        return self._advice

    @property
    def windspeed_bft(self) -> int | None:
        """Return the windspeed in bft."""
        return self.get_property("wind_bft")

    @property
    def windspeed_ms(self) -> float | None:
        """Return the windspeed in m/s."""
        windspeed = self.get_property("wind")
        return round(float(windspeed), 1) if windspeed else windspeed

    @property
    def lki(self) -> int | None:
        """Return the lki."""
        return self.get_property("lki")

    @property
    def forecast_advice(self) -> list:
        """Return the forecast array for advices."""
        return self.get_forecast_array(True)

    @property
    def last_updated(self) -> datetime | None:
        """Get the last updated date."""
        return self._last_updated

    @staticmethod
    async def async_transform_coordinates(
        session: aiohttp.ClientSession, latitude: float, longitude: float
    ):
        """Transform the coordinates from EPSG:4326 to EPSG:28992."""
        url = f"https://epsg.io/srs/transform/{longitude},{latitude}.json?key=default&s_srs=4326&t_srs=28992"
        try:
            async with session.get(url=url, timeout=10) as response:
                response = await response.read()

            coordinates = json.loads(response)
            return coordinates["results"][0]["x"], coordinates["results"][0]["y"]

        except aiohttp.ClientConnectorError:
            _LOGGER.error("Error requesting coordinate conversion")
            return None, None
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout requesting coordinate conversion")
            return None, None
        except KeyError:
            _LOGGER.error("Received invalid response transforming coordinates")
            return None, None

    async def async_update(self) -> None:
        """Get the stookwijzer data."""
        self._stookwijzer = await self.async_get_stookwijzer()

        advice = self.get_property("advies_0")
        if advice:
            self._advice = self.get_color(advice)
            self._last_updated = datetime.now()

    def get_forecast_array(self, advice: bool) -> list:
        """Return the forecast array."""
        forecast = []
        runtime = self.get_property("model_runtime")

        if not runtime:
            return None

        dt = datetime.strptime(runtime, "%d-%m-%Y %H:%M")
        localdt = dt.astimezone(pytz.timezone("Europe/Amsterdam"))

        for offset in range(0, 19, 6):
            forecast.append(self.get_forecast_at_offset(localdt, offset, advice))

        return forecast

    def get_forecast_at_offset(
        self, runtime: datetime, offset: int, advice: bool
    ) -> dict:
        """Get forecast at a certain offset."""
        dt = {"datetime": (runtime + timedelta(hours=offset)).isoformat()}
        forecast = (
            {"advice": self.get_color(self.get_property("advies_" + str(offset)))}
        )
        dt.update(forecast)

        return dt

    def get_boundary_box(self, x: float, y: float) -> str | None:
        """Create a boundary box with the coordinates"""
        return str(x) + "%2C" + str(y) + "%2C" + str(x + 10) + "%2C" + str(y + 10)

    def get_color(self, advice: str) -> str:
        """Convert the Stookwijzer data into a color."""
        if advice == "0":
            return "code_yellow"
        if advice == "1":
            return "code_orange"
        if advice == "2":
            return "code_red"
        return ""

    def get_property(self, prop: str) -> str:
        """Get a feature from the JSON data"""
        try:
            return str(self._stookwijzer["features"][0]["properties"][prop])
        except (KeyError, IndexError, TypeError):
            _LOGGER.error("Property %s not available", prop)
            return ""

    async def async_get_stookwijzer(self):
        """Get the stookwijzer data."""
        url = (
            "https://data.rivm.nl/geo/alo/wms?service=WMS&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&FORMAT=image/png&TRANSPARENT=true&QUERY_LAYERS=stookwijzer_v2&LAYERS=stookwijzer_v2&servicekey=82b124ad-834d-4c10-8bd0-ee730d5c1cc8&STYLES=&BUFFER=1&EXCEPTIONS=INIMAGE&info_format=application/json&feature_count=1&I=139&J=222&WIDTH=256&HEIGHT=256&CRS=EPSG:28992&BBOX="
            + self._boundary_box
        )

        try:
            async with self._session.get(
                url=url, allow_redirects=False, timeout=10
            ) as response:
                response = await response.read()

            return json.loads(response)

        except aiohttp.ClientConnectorError:
            _LOGGER.error("Error getting Stookwijzer data")
            return None
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting Stookwijzer data")
            return None
        except KeyError:
            _LOGGER.error("Received invalid response from Stookwijzer")
            return None
