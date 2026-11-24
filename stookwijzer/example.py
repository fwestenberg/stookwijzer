"""Example usage of the Stookwijzer API.

Run from the repository root: python -m stookwijzer.example
"""
import asyncio

import aiohttp

from stookwijzer import MapOptions, Stookwijzer


async def main():
    xy = await Stookwijzer.async_transform_coordinates(52.123456, 6.123456)
    print(f"x:               {xy['x']}")
    print(f"y:               {xy['y']}")

    if xy:
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        sw = Stookwijzer(session, xy['x'], xy['y'])
        await sw.async_update()

        print()
        print(f"advice:          {sw.advice}")
        print(f"windspeed bft:   {sw.windspeed_bft}")
        print(f"windspeed ms:    {sw.windspeed_ms}")
        print(f"lki:             {sw.lki}")
        print()
        print(f"forecast_advice: {await sw.async_get_forecast()}")

        # Optional: a map of the whole country and one 40 km around the location.
        # The map is only fetched again after the next async_update().
        for name, options in [
            ("stookwijzer_nl.png", MapOptions()),
            ("stookwijzer_regio.png", MapOptions(
                radius_km=40,
                labels={"code_yellow": "Code yellow", "code_orange": "Code orange", "code_red": "Code red"},
            )),
        ]:
            result = await sw.async_get_map(options)
            if result:
                with open(name, "wb") as file:
                    file.write(result.image)
                print(f"{name}: coverage {result.coverage}")

        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
