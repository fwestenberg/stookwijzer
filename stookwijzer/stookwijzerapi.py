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
        self._state = None
        self._alert = None
        self._last_updated = None
        self._stookwijzer = None
        self._session = session

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def alert(self):
        """Return the stookalert."""
        return self._alert

    @property
    def windspeed_bft(self):
        """Return the windspeed in bft."""
        return self.get_property("wind_bft")

    @property
    def windspeed_ms(self):
        """Return the windspeed in m/s."""
        return self.get_property("wind")

    @property
    def lki(self):
        """Return the lki."""
        return self.get_property("lki")

    @property
    def forecast(self):
        """Return the forecast array."""
        forecast = []
        runtime = self.get_property("model_runtime")

        if not runtime:
            return None

        dt = datetime.strptime(runtime, "%d-%m-%Y %H:%M")
        localdt = dt.astimezone(pytz.timezone("Europe/Amsterdam"))

        for offset in range(2, 25, 2):
            forecast.append(self.get_forecast_at_offset(localdt, offset))
        
        return forecast

    @property
    def last_updated(self):
        """Get the last updated date."""
        return self._last_updated

    @staticmethod
    async def transform_coordinates(session: aiohttp.ClientSession, latitude: float,longitude: float):
        """Transform the coordinates from EPSG:4326 to EPSG:28992."""
        url = f"https://epsg.io/srs/transform/{longitude},{latitude}.json?key=default&s_srs=4326&t_srs=28992"
        try:
            async with session.get(
                url=url, timeout=10
            ) as response:
                response = await response.read()

            coordinates = json.loads(response)
            return coordinates["results"][0]["x"],coordinates["results"][0]["y"]

        except aiohttp.ClientConnectorError:
            _LOGGER.error("Error requesting coordinate conversion")
            return None, None
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout requesting coordinate conversion")
            return None, None
        except KeyError:
            _LOGGER.error("Received invalid response transforming coordinates")
            return None, None

    async def update(self) -> None:
        """Get the stookwijzer data."""
        self._stookwijzer = await self.get_stookwijzer()

        advice = self.get_property("advies_0")
        if advice:
            self._state = self.get_color(advice)
            self._alert = self.get_property("alert_0") == '1'
            self._last_updated = datetime.now()

    def get_forecast_at_offset(self, runtime: datetime, offset: int) -> dict:
        """Get forecast at a certain offset."""
        return {
            "datetime": (runtime + timedelta(hours=offset)).isoformat(),
            "advice": self.get_color(self.get_property("advies_" + str(offset))),
            "alert": self.get_property("alert_" + str(offset))  == '1',
        }

    def get_boundary_box(self, x: float, y: float) -> str | None:
        """Create a boundary box with the coordinates"""
        return (str(x) + "%2C" + str(y) + "%2C" + str(x + 10) + "%2C" + str(y + 10))

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
        except (KeyError, IndexError):
            _LOGGER.error("Property %s not available", prop)
            return ""

    async def get_stookwijzer(self):
        """Get the stookwijzer data."""
        url = (
            "https://data.rivm.nl/geo/alo/wms?service=WMS&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&FORMAT=application%2Fjson&QUERY_LAYERS=stookwijzer&LAYERS=stookwijzer&servicekey=82b124ad-834d-4c10-8bd0-ee730d5c1cc8&STYLES=&BUFFER=1&info_format=application%2Fjson&feature_count=1&I=1&J=1&WIDTH=1&HEIGHT=1&CRS=EPSG%3A28992&BBOX="
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
