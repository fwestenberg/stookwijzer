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
        self._weather = None
        self._concentrations = None
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

    @property
    def weather(self):
        """Get the weather JSON date."""
        return self._weather

    @property
    def concentrations(self):
        """Get the concentrations JSON date."""
        return self._concentrations

    def update(self):
        """Get the stookwijzer data."""
        self._windspeed = self.request_windspeed()
        self._lqi = self.request_lqi()
        self._state = self.determine_stookwijzer(self._windspeed, self._lqi)

    def determine_stookwijzer(self, windspeed: float, lqi: float) -> str:
        """Get the stookwijzer data."""
        if self._windspeed is None or (self._lqi is None and self._windspeed > 2.0):
            return None

        self._last_updated = datetime.now()

        if self._windspeed <= 2.0 or self._lqi > 7:
            return "Rood"
        if self._windspeed > 2.0 and self._lqi > 4 and self._lqi <= 7:
            return "Oranje"
        else:
            return "Blauw"

    def request_windspeed(self):
        """Get the windstate."""
        url = (
            "https://api.open-meteo.com/v1/forecast?latitude="
            + str(self._latitude)
            + "&longitude="
            + str(self._longitude)
            + "&current_weather=true&windspeed_unit=ms"
        )

        try:
            response = requests.get(
                url,
                timeout=10,
            )

            self._weather = response.json()
            return self._weather["current_weather"]["windspeed"]

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

            self._concentrations = response.json()
            for component in self._concentrations["result"]:
                measured = datetime.fromisoformat(component["timestamp_measured"])

                if (measured - now).total_seconds() > 0:
                    return component["value"]

        except requests.exceptions.RequestException:
            _LOGGER.error("Error getting Stookwijzer LQI data")
        except KeyError:
            _LOGGER.error("No Stookwijzer LQI available")
