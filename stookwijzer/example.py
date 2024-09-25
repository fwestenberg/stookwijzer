"""Example usage of the Stookwijzer API."""
import aiohttp
import asyncio
import stookwijzerapi

async def main():
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))

    x, y = await stookwijzerapi.Stookwijzer.async_transform_coordinates(session, 52.123456, 6.123456)
    print(f"x:               {x}")
    print(f"y:               {y}")

    if x and y:
        sw = stookwijzerapi.Stookwijzer(session, x, y)
        await sw.async_update()
        print()
        print(f"advice:          {sw.advice}")
        print(f"alert:           {sw.alert}")
        print(f"windspeed bft:   {sw.windspeed_bft}")
        print(f"windspeed ms:    {sw.windspeed_ms}")
        print(f"lki:             {sw.lki}")
        print()
        print(f"forecast_advice: {sw.forecast_advice}")
        print()
        print(f"forecast_alert:  {sw.forecast_alert}")
    
    await session.close()
    
if __name__ == "__main__":
    asyncio.run(main())