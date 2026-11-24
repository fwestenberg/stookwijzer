"""Render a Stookwijzer map: PDOK basemap with the RIVM advice areas on top."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from io import BytesIO

import aiohttp
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .const import RIVM_LAYER, RIVM_WMS_URL, SERVICE_KEY

# PDOK only offers the BRT basemap as WMTS (tiles)
PDOK_WMTS = (
    "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/"
    "{layer}/EPSG:3857/{z}/{x}/{y}.png"
)
TILE = 256
EARTH_RADIUS = 6378137.0
WORLD = 2 * math.pi * EARTH_RADIUS  # width of the Web Mercator world in meters
MAX_ZOOM = 17
BACKGROUND = (236, 236, 236)  # colour for foreign countries/sea without a tile

# The whole of the Netherlands in EPSG:3857 (Web Mercator)
NL_BBOX = (356000.0, 6555000.0, 813000.0, 7092000.0)

LEVEL_ORDER = ("code_yellow", "code_orange", "code_red")  # red last = on top

DEFAULT_LABELS = {
    "code_yellow": "Code geel",
    "code_orange": "Code oranje",
    "code_red": "Code rood",
}

# Colours of the advice levels in the RIVM WMS layer (from its SLD style). The
# Stookwijzer website draws them as is, at 60% opacity.
RIVM_COLORS = {
    "code_yellow": (255, 255, 191),
    "code_orange": (253, 174, 97),
    "code_red": (215, 25, 28),
}
# Max difference per RGB channel (RIVM pixels vary by ~3). Anti-aliased pixels
# where red and yellow meet come within ~21 of orange and fall outside it.
COLOR_TOLERANCE = 15

ATTRIBUTION = "© RIVM Stookwijzer · PDOK/Kadaster"

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class MapOptions:
    """Options for rendering a Stookwijzer map."""

    width: int = 800
    levels: tuple[str, ...] = ("code_yellow", "code_orange", "code_red")
    opacity: float = 0.6
    basemap: str = "grijs"  # PDOK: standaard, grijs, pastel, water
    show_location: bool = True
    radius_km: float | None = None  # None = whole NL, else a crop around the location
    supersample: int = 2
    title: str = "Stookwijzer"
    # Legend text per level, e.g. {"code_red": "Code red"}; missing levels use
    # the Dutch default. Not part of the hash, so MapOptions stays usable as key.
    labels: dict[str, str] = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class StookwijzerMap:
    """A rendered map and the coverage per advice level in percent."""

    image: bytes
    coverage: dict[str, float]


def to_mercator(lat: float, lon: float) -> tuple[float, float]:
    """Convert WGS84 to Web Mercator (EPSG:3857)."""
    x = EARTH_RADIUS * math.radians(lon)
    y = EARTH_RADIUS * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def compute_bbox(opt: MapOptions, location: tuple[float, float]) -> tuple[BBox, int, int]:
    """Return (bbox, width, height) of the final image."""
    if opt.radius_km:
        lat, lon = location
        cx, cy = to_mercator(lat, lon)
        # Mercator stretches with 1/cos(lat): correct so the radius is in real km
        half = opt.radius_km * 1000 / math.cos(math.radians(lat))
        bbox = (cx - half, cy - half, cx + half, cy + half)
    else:
        bbox = NL_BBOX
    width = opt.width
    height = round(width * (bbox[3] - bbox[1]) / (bbox[2] - bbox[0]))
    return bbox, width, height


def _tile_zoom(bbox: BBox, px_width: int) -> int:
    target_res = (bbox[2] - bbox[0]) / px_width
    zoom = math.log2(WORLD / (TILE * target_res))
    # Round down a little: fewer tiles, the basemap is faded anyway
    return max(0, min(MAX_ZOOM, math.ceil(zoom - 0.3)))


def _tile_range(bbox: BBox, zoom: int) -> tuple[int, int, int, int, float]:
    span = WORLD / (2**zoom)
    half = WORLD / 2
    x0 = int((bbox[0] + half) // span)
    x1 = int((bbox[2] + half - 1e-6) // span)
    y0 = int((half - bbox[3]) // span)
    y1 = int((half - bbox[1] - 1e-6) // span)
    return x0, x1, y0, y1, span


def stitch_tiles(
    tiles: dict[tuple[int, int], bytes | None], bbox: BBox, zoom: int, width: int, height: int
) -> bytes:
    """Stitch tiles together, crop exactly to the bbox and scale to width×height."""
    x0, x1, y0, y1, span = _tile_range(bbox, zoom)
    mosaic = Image.new("RGB", ((x1 - x0 + 1) * TILE, (y1 - y0 + 1) * TILE), BACKGROUND)
    for (tx, ty), data in tiles.items():
        if not data:
            continue
        tile = Image.open(BytesIO(data)).convert("RGBA")
        # Foreign countries are transparent
        mosaic.paste(tile, ((tx - x0) * TILE, (ty - y0) * TILE), tile)
    half = WORLD / 2
    res = span / TILE
    box = (
        (bbox[0] + half) / res - x0 * TILE,
        (half - bbox[3]) / res - y0 * TILE,
        (bbox[2] + half) / res - x0 * TILE,
        (half - bbox[1]) / res - y0 * TILE,
    )
    img = mosaic.resize((width, height), Image.LANCZOS, box=box)
    out = BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


async def fetch_basemap(
    session: aiohttp.ClientSession, bbox: BBox, width: int, height: int, opt: MapOptions
) -> bytes:
    """Fetch the PDOK WMTS tiles and stitch them into one basemap."""
    scale = opt.supersample
    zoom = _tile_zoom(bbox, width * scale)
    x0, x1, y0, y1, _ = _tile_range(bbox, zoom)
    semaphore = asyncio.Semaphore(8)

    async def fetch_tile(tx: int, ty: int) -> tuple[tuple[int, int], bytes | None]:
        url = PDOK_WMTS.format(layer=opt.basemap, z=zoom, x=tx, y=ty)
        async with semaphore:
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    if response.status != 200:
                        return (tx, ty), None
                    return (tx, ty), await response.read()
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return (tx, ty), None

    results = await asyncio.gather(
        *(fetch_tile(tx, ty) for tx in range(x0, x1 + 1) for ty in range(y0, y1 + 1))
    )
    tiles = dict(results)
    if not any(tiles.values()):
        raise ValueError("No PDOK tile could be fetched")
    return await asyncio.get_running_loop().run_in_executor(
        None, stitch_tiles, tiles, bbox, zoom, width * scale, height * scale
    )


async def fetch_overlay(
    session: aiohttp.ClientSession, bbox: BBox, width: int, height: int, opt: MapOptions
) -> bytes:
    """Fetch the RIVM Stookwijzer layer as a transparent PNG."""
    scale = opt.supersample
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": RIVM_LAYER,
        "STYLES": "",
        "FORMAT": "image/png",
        "TRANSPARENT": "true",
        "CRS": "EPSG:3857",
        "BBOX": ",".join(f"{v:.2f}" for v in bbox),
        "WIDTH": str(width * scale),
        "HEIGHT": str(height * scale),
        "servicekey": SERVICE_KEY,
    }
    async with session.get(
        RIVM_WMS_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)
    ) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        data = await response.read()
    if not content_type.startswith("image/"):
        raise ValueError(f"No image from RIVM: {content_type} {data[:200]!r}")
    return data


def level_masks(overlay_png: bytes) -> dict[str, Image.Image]:
    """Split the RIVM layer into a mask per advice level."""
    overlay = Image.open(BytesIO(overlay_png)).convert("RGBA")
    opaque = overlay.getchannel("A").point(lambda a: 255 if a > 40 else 0)
    rgb = overlay.convert("RGB")
    masks = {}
    for name, color in RIVM_COLORS.items():
        diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, color))
        mask = opaque
        for channel in diff.split():
            mask = ImageChops.multiply(
                mask, channel.point(lambda v: 255 if v <= COLOR_TOLERANCE else 0)
            )
        masks[name] = mask
    return masks


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def compose(
    base_png: bytes,
    overlay_png: bytes,
    bbox: BBox,
    opt: MapOptions,
    location: tuple[float, float],
) -> StookwijzerMap:
    """Build the final image. Blocking: run it in an executor."""
    base = Image.open(BytesIO(base_png)).convert("RGB")
    width = base.size[0] // opt.supersample
    height = base.size[1] // opt.supersample
    # Lighten the basemap a bit so the colours stand out
    base = Image.blend(base, Image.new("RGB", base.size, (255, 255, 255)), 0.25)
    base = base.convert("RGBA")

    masks = level_masks(overlay_png)
    coverage: dict[str, float] = {}
    total_px = base.size[0] * base.size[1]

    for name in LEVEL_ORDER:
        mask = masks[name]
        if mask.size != base.size:
            mask = mask.resize(base.size, Image.NEAREST)
        coverage[name] = round(100 * sum(mask.histogram()[128:]) / total_px, 2)
        if name not in opt.levels or coverage[name] == 0:
            continue
        color = RIVM_COLORS[name]
        soft = mask.filter(ImageFilter.GaussianBlur(1.2 * opt.supersample))
        fill = Image.new("RGBA", base.size, color + (0,))
        fill.putalpha(soft.point(lambda a, o=opt.opacity: int(a * o)))
        base = Image.alpha_composite(base, fill)
        # Thin outline in full colour
        edge = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
        line = Image.new("RGBA", base.size, color + (0,))
        line.putalpha(edge.point(lambda a: 230 if a > 60 else 0))
        base = Image.alpha_composite(base, line)

    img = base.resize((width, height), Image.LANCZOS)
    draw = ImageDraw.Draw(img, "RGBA")

    if opt.show_location:
        hx, hy = to_mercator(*location)
        px = (hx - bbox[0]) / (bbox[2] - bbox[0]) * width
        py = (bbox[3] - hy) / (bbox[3] - bbox[1]) * height
        r = max(5, width // 110)
        draw.ellipse((px - r - 3, py - r - 3, px + r + 3, py + r + 3), fill=(255, 255, 255, 255))
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(3, 105, 161, 255))

    _draw_legend(draw, opt, width, height)

    out = BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return StookwijzerMap(image=out.getvalue(), coverage=coverage)


def _draw_legend(draw: ImageDraw.ImageDraw, opt: MapOptions, width: int, height: int) -> None:
    shown = [name for name in LEVEL_ORDER if name in opt.levels]
    fs = max(13, width // 50)
    f_title, f_text = _font(round(fs * 1.25)), _font(fs)
    pad, swatch, gap = fs, fs, round(fs * 0.5)
    lines = [
        (opt.labels.get(name, DEFAULT_LABELS[name]), RIVM_COLORS[name])
        for name in shown
    ]

    text_w = max(
        [draw.textlength(opt.title, font=f_title)]
        + [swatch + gap + draw.textlength(text, font=f_text) for text, _ in lines]
    )
    box_w = int(text_w + 2 * pad)
    box_h = int(pad * 2 + fs * 1.25 + gap + len(lines) * (fs + gap))
    x0, y0 = pad, height - box_h - pad
    draw.rounded_rectangle(
        (x0, y0, x0 + box_w, y0 + box_h),
        radius=fs // 2,
        fill=(255, 255, 255, 225),
        outline=(0, 0, 0, 40),
    )
    y = y0 + pad
    draw.text((x0 + pad, y), opt.title, font=f_title, fill=(30, 30, 30, 255))
    y += round(fs * 1.25) + gap
    for text, color in lines:
        draw.rounded_rectangle(
            (x0 + pad, y + 1, x0 + pad + swatch, y + 1 + swatch),
            radius=3,
            fill=color + (round(255 * opt.opacity),),
            outline=color + (255,),
        )
        draw.text((x0 + pad + swatch + gap, y), text, font=f_text, fill=(40, 40, 40, 255))
        y += fs + gap

    f_attr = _font(max(10, fs - 3))
    attr_w = draw.textlength(ATTRIBUTION, font=f_attr)
    draw.rectangle((width - attr_w - 10, height - fs - 4, width, height), fill=(255, 255, 255, 190))
    draw.text((width - attr_w - 5, height - fs - 2), ATTRIBUTION, font=f_attr, fill=(80, 80, 80, 255))
