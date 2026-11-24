# Stookwijzer
This is a Python package for the Stookwijzer API. The Stookwijzer data is retrieved from the [Atlas Leefomgeving](https://www.atlasleefomgeving.nl/stookwijzer) API.

## Installation ##
Stookwijzer requires Python 3.6+ to run.

`pip install stookwijzer`

## Map ##
Besides the advice for a location, the package can render a map of the Stookwijzer advice areas on a [PDOK](https://www.pdok.nl) basemap, for example for a Home Assistant camera entity.

```python
from stookwijzer import MapOptions, Stookwijzer

sw = Stookwijzer(session, x, y)
await sw.async_update()

result = await sw.async_get_map(MapOptions(radius_km=40))
if result:
    open("stookwijzer.png", "wb").write(result.image)  # PNG bytes
    print(result.coverage)  # {"code_yellow": 53.0, "code_orange": 0.0, "code_red": 36.4}
```

The map is optional: it is only fetched when `async_get_map()` is called. It is cached per `MapOptions` and only fetched again after the next `async_update()`, so calling it often causes no extra requests. The basemap is fetched once and kept in memory. When fetching fails, the last successful map is returned (`None` if there is none).

`MapOptions`:

| Option | Default | Description |
| --- | --- | --- |
| `width` | `800` | Width of the image in pixels |
| `levels` | `("code_yellow", "code_orange", "code_red")` | Advice levels to draw |
| `opacity` | `0.6` | Opacity of the coloured areas |
| `basemap` | `"grijs"` | PDOK basemap: `standaard`, `grijs`, `pastel` or `water` |
| `show_location` | `True` | Show a marker at the Stookwijzer location |
| `radius_km` | `None` | `None` for the whole country, otherwise a square around the location |
| `supersample` | `2` | Render at a higher resolution for smoother edges |
| `title` | `"Stookwijzer"` | Title in the legend |
| `labels` | `{}` | Legend text per level, e.g. `{"code_red": "Code red"}`. Missing levels use the Dutch default (`Code geel`, `Code oranje`, `Code rood`) |
