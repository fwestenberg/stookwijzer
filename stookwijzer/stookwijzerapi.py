"""The Stookwijze API."""
from datetime import datetime, timedelta
import logging

from pyreproj import Reprojector
import pytz
import requests

_LOGGER = logging.getLogger(__name__)


class Stookwijzer(object):
    """The Stookwijze API."""

    def __init__(self, latitude, longitude):
        self._boundary_box = self.get_boundary_box(latitude, longitude)
        self._state = None
        self._alert = None
        self._last_updated = None
        self._stookwijzer = None

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

        dt = datetime.strptime(runtime, "%d-%m-%Y %H:%M")
        localdt = dt.astimezone(pytz.timezone("Europe/Amsterdam"))

        for offset in range(2, 25, 2):
            forecast.append(self.get_forecast_at_offset(localdt, offset))

        return {"forecast": forecast}

    @property
    def last_updated(self):
        """Get the last updated date."""
        return self._last_updated

    def update(self):
        """Get the stookwijzer data."""
        self._stookwijzer = self.get_stookwijzer()

        advice = self.get_property("advies_0")
        if advice:
            self._state = self.get_color(advice)
            self._alert = self.get_property("alert_0")
            self._last_updated = datetime.now()

    def get_forecast_at_offset(self, runtime: datetime, offset: int) -> dict:
        """Get forecast at a certain offset."""
        return {
            "datetime": (runtime + timedelta(hours=offset)).isoformat(),
            "advice": self.get_color(self.get_property("advies_" + str(offset))),
            "alert": self.get_property("alert_" + str(offset)),
        }

    def get_boundary_box(self, latitude: float, longitude: float) -> str:
        """Convert the coordinates from EPSG:4326 to EPSG:28992 and create a boundary box"""
        rp = Reprojector()
        transform = rp.get_transformation_function(from_srs=4326, to_srs=28992)

        coordinates = list(transform(latitude, longitude))
        return (
            str(coordinates[0])
            + "%2C"
            + str(coordinates[1])
            + "%2C"
            + str(coordinates[0] + 10)
            + "%2C"
            + str(coordinates[1] + 10)
        )

    def get_color(self, advice: str) -> str:
        """Convert the stookwijzer data into a color."""

        if advice == "0":
            return "codeYellow"
        if advice == "1":
            return "codeOrange"
        if advice == "2":
            return "codeRed"
        return ""

    def get_property(self, prop: str) -> str:
        """Get a feature from the JSON data"""
        try:
            return str(self._stookwijzer["features"][0]["properties"][prop])
        except KeyError:
            _LOGGER.error("Property %s not available", prop)
            return ""

    def get_stookwijzer(self):
        """Get the stookwijzer data."""
        url = (
            "https://data.rivm.nl/geo/alo/wms?service=WMS&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&FORMAT=application%2Fjson&QUERY_LAYERS=stookwijzer&LAYERS=stookwijzer&servicekey=82b124ad-834d-4c10-8bd0-ee730d5c1cc8&STYLES=&BUFFER=1&info_format=application%2Fjson&feature_count=1&I=1&J=1&WIDTH=1&HEIGHT=1&CRS=EPSG%3A28992&BBOX="
            + self._boundary_box
        )

        try:
            response = requests.get(
                url,
                timeout=10,
            )
            return response.json()

        except requests.exceptions.RequestException:
            _LOGGER.error("Error getting Stookwijzer data")
