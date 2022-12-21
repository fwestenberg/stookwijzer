"""The Stookwijze API."""
from datetime import datetime
import logging

import pytz
import requests

_LOGGER = logging.getLogger(__name__)


class Stookwijzer(object):
    """The Stookwijze API."""

    def __init__(self, latitude, longitude):
        self._state = None
        self._latitude = latitude
        self._longitude = longitude
        self._last_updated = None
        self._windspeed = None
        self._lqi = None

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def windspeed(self):
        """Return the windspeed."""
        return self._windspeed

    @property
    def lqi(self):
        """Return the lqi."""
        return self._lqi

    @property
    def latitude(self):
        """Return the latitude."""
        return self._latitude

    @property
    def longitude(self):
        """Return the lqlongitudei."""
        return self._longitude

    @property
    def last_updated(self):
        """Get the last updated date."""
        return self._last_updated

    def update(self):
        """Get the stookwijzer data."""
        self._windspeed = self.request_windspeed()
        self._lqi = self.request_lqi()
        self._state = self.determine_stookwijzer(self._windspeed, self._lqi)

    def determine_stookwijzer(self, windspeed: float, lqi: float) -> str:
        """Get the stookwijzer data."""
        if self._windspeed is None or self._lqi is None:
            return None

        self._last_updated = datetime.now()

        if self._lqi <= 4 and self._windspeed > 2:
            return "Blauw"

        if self._lqi > 4 and self._lqi <= 7 and self._windspeed > 2:
            return "Oranje"

        if self._lqi > 7 or self._windspeed <= 2:
            return "Rood"

    def request_windspeed(self):
        """Get the windstate."""
        url = (
            "https://www.stookwijzer.nu/api/weather?lat="
            + str(self._latitude)
            + "&lon="
            + str(self._longitude)
        )

        try:
            response = requests.get(
                url,
                timeout=10,
            )

            windspeed = response.json()["data"]["wind"]["speed"]
            return windspeed

        except requests.exceptions.RequestException:
            _LOGGER.error("Error getting Stookwijzer weather data")
        except KeyError:
            _LOGGER.error("No Stookwijzer windspeed available")

    def request_lqi(self):
        """Get the lqi."""
        now = datetime.now(pytz.timezone("Europe/Amsterdam"))
        url = (
            "https://api2020.luchtmeetnet.nl/ascii/concentrations?formula=LKI&latitude="
            + str(self._latitude)
            + "&longitude="
            + str(self._longitude)
        )

        try:
            response = requests.get(
                url,
                timeout=10,
            )

            for component in response.json()["result"]:
                measured = datetime.fromisoformat(component["timestamp_measured"])

                if (measured - now).total_seconds() > 0:
                    return component["value"]

        except requests.exceptions.RequestException:
            _LOGGER.error("Error getting Stookwijzer LQI data")
        except KeyError:
            _LOGGER.error("No Stookwijzer LQI available")
