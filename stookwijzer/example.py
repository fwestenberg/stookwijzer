"""Example usage of the Stookwijzer API."""
import aiohttp
import asyncio
import stookwijzerapi

async def main():
    x, y = await stookwijzerapi.Stookwijzer.async_transform_coordinates(52.123456, 6.123456)
    print(f"x:               {x}")
    print(f"y:               {y}")

    if x and y:
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        sw = stookwijzerapi.Stookwijzer(session, x, y)
        await sw.async_update()

        print()
        print(f"advice:          {sw.advice}")
        print(f"windspeed bft:   {sw.windspeed_bft}")
        print(f"windspeed ms:    {sw.windspeed_ms}")
        print(f"lki:             {sw.lki}")
        print()
        print(f"forecast_advice: {await sw.async_get_forecast()}")

        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
