"""Tests for the Stookwijzer map."""

import asyncio
from io import BytesIO

import aiohttp
from PIL import Image

import stookwijzer.stookwijzerapi as api
from stookwijzer import MapOptions, Stookwijzer, StookwijzerMap
from stookwijzer.map import NL_BBOX, compose, compute_bbox, level_masks

# Colours as delivered by the RIVM WMS layer
RED = (215, 25, 28, 255)
ORANGE = (253, 174, 97, 255)
YELLOW = (255, 255, 191, 255)
CLEAR = (0, 0, 0, 0)


def png(size: tuple[int, int], color=(200, 200, 200, 255), right=None) -> bytes:
    """Create a PNG; with `right` the right half gets that colour."""
    img = Image.new("RGBA", size, color)
    if right is not None:
        img.paste(right, (size[0] // 2, 0, size[0], size[1]))
    out = BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def coverage_pct(mask: Image.Image) -> float:
    return 100 * sum(mask.histogram()[128:]) / (mask.size[0] * mask.size[1])


def test_rd_wgs84_round_trip() -> None:
    """RD -> WGS84 must invert the existing WGS84 -> RD transformation."""
    for lat, lon in [(52.0, 5.0), (53.2, 6.5), (50.85, 5.7), (52.155, 5.387)]:
        xy = asyncio.run(Stookwijzer.async_transform_coordinates(lat, lon))
        back = Stookwijzer.transform_rd_to_wgs84(xy["x"], xy["y"])
        assert abs(back[0] - lat) < 1e-5
        assert abs(back[1] - lon) < 1e-5


def test_compute_bbox_whole_country() -> None:
    bbox, width, height = compute_bbox(MapOptions(width=400), (52.0, 5.0))
    assert bbox == NL_BBOX
    assert width == 400
    assert height == round(400 * (NL_BBOX[3] - NL_BBOX[1]) / (NL_BBOX[2] - NL_BBOX[0]))


def test_compute_bbox_radius_is_square_around_location() -> None:
    bbox, width, height = compute_bbox(MapOptions(width=400, radius_km=40), (52.0, 5.0))
    assert width == height == 400
    assert abs((bbox[2] - bbox[0]) - (bbox[3] - bbox[1])) < 1e-6
    # 40 km stretched by 1/cos(52°) in Web Mercator
    assert 129000 < bbox[2] - bbox[0] < 131000


def test_level_masks_recognise_colours() -> None:
    for color, name in [(RED, "code_red"), (ORANGE, "code_orange"), (YELLOW, "code_yellow")]:
        masks = level_masks(png((20, 10), CLEAR, right=color))
        assert coverage_pct(masks[name]) == 50
        assert all(coverage_pct(m) == 0 for n, m in masks.items() if n != name)


def test_level_masks_ignore_grey_and_transparent() -> None:
    masks = level_masks(png((20, 10), (128, 128, 128, 255), right=(215, 25, 28, 0)))
    assert all(coverage_pct(m) == 0 for m in masks.values())


def test_level_masks_ignore_blended_edges() -> None:
    """A red/yellow border blends into orange-ish pixels: no orange area."""
    for t in (0.3, 0.5, 0.56, 0.6, 0.65, 0.8):
        blend = tuple(round(r + (y - r) * t) for r, y in zip(RED, YELLOW))
        masks = level_masks(png((20, 10), CLEAR, right=blend))
        assert coverage_pct(masks["code_orange"]) == 0


def test_compose_returns_png_and_coverage() -> None:
    opt = MapOptions(width=200, supersample=2)
    result = compose(
        png((400, 300)), png((400, 300), CLEAR, right=RED), NL_BBOX, opt, (52.0, 5.0)
    )
    img = Image.open(BytesIO(result.image))
    assert img.format == "PNG"
    assert img.size == (200, 150)
    assert result.coverage == {"code_yellow": 0, "code_orange": 0, "code_red": 50}


class FakeLayers:
    """Replace the network calls of the map."""

    def __init__(self, monkeypatch, fail: bool = False) -> None:
        self.basemap_calls = 0
        self.overlay_calls = 0
        self.fail = fail
        monkeypatch.setattr(api, "fetch_basemap", self.fetch_basemap)
        monkeypatch.setattr(api, "fetch_overlay", self.fetch_overlay)

    async def fetch_basemap(self, session, bbox, width, height, opt) -> bytes:
        self.basemap_calls += 1
        return png((width * opt.supersample, height * opt.supersample))

    async def fetch_overlay(self, session, bbox, width, height, opt) -> bytes:
        self.overlay_calls += 1
        if self.fail:
            raise aiohttp.ClientError("boom")
        return png((width * opt.supersample, height * opt.supersample), CLEAR, right=ORANGE)


def no_update(monkeypatch, client: Stookwijzer) -> None:
    async def fake_get_stookwijzer():
        return None

    monkeypatch.setattr(client, "async_get_stookwijzer", fake_get_stookwijzer)


def test_map_is_cached_until_next_update(monkeypatch) -> None:
    layers = FakeLayers(monkeypatch)
    client = Stookwijzer(None, 155000, 463000)
    no_update(monkeypatch, client)
    opt = MapOptions(width=100, radius_km=20)

    async def run():
        first = await client.async_get_map(opt)
        second = await client.async_get_map(opt)
        assert isinstance(first, StookwijzerMap)
        assert second is first
        assert layers.overlay_calls == 1

        await client.async_update()
        third = await client.async_get_map(opt)
        assert third is not first
        assert layers.overlay_calls == 2
        # The basemap never changes, so it is fetched only once
        assert layers.basemap_calls == 1

    asyncio.run(run())


def test_update_does_not_fetch_map(monkeypatch) -> None:
    layers = FakeLayers(monkeypatch)
    client = Stookwijzer(None, 155000, 463000)
    no_update(monkeypatch, client)

    asyncio.run(client.async_update())
    assert layers.basemap_calls == layers.overlay_calls == 0


def test_failed_map_returns_none_without_retrying(monkeypatch) -> None:
    layers = FakeLayers(monkeypatch, fail=True)
    client = Stookwijzer(None, 155000, 463000)
    opt = MapOptions(width=100, radius_km=20)

    async def run():
        assert await client.async_get_map(opt) is None
        assert await client.async_get_map(opt) is None
        assert layers.overlay_calls == 1

    asyncio.run(run())


def test_failed_map_keeps_last_good_map(monkeypatch) -> None:
    layers = FakeLayers(monkeypatch)
    client = Stookwijzer(None, 155000, 463000)
    no_update(monkeypatch, client)
    opt = MapOptions(width=100, radius_km=20)

    async def run():
        good = await client.async_get_map(opt)
        layers.fail = True
        await client.async_update()
        assert await client.async_get_map(opt) is good

    asyncio.run(run())


def test_labels_are_used_and_options_stay_hashable() -> None:
    opt = MapOptions(width=200, labels={"code_red": "Code red"})
    same = MapOptions(width=200, labels={"code_red": "Code red"})
    other = MapOptions(width=200, labels={"code_red": "Rood"})
    assert {opt: 1}[same] == 1
    assert opt != other

    base, overlay = png((400, 300)), png((400, 300), CLEAR, right=RED)
    image = compose(base, overlay, NL_BBOX, opt, (52.0, 5.0)).image
    assert image != compose(base, overlay, NL_BBOX, other, (52.0, 5.0)).image
