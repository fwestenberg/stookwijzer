"""Example usage of the Stookwijzer API."""
import aiohttp
import asyncio
import stookwijzerapi

async def main():
    session = aiohttp.ClientSession()

    x, y = await stookwijzerapi.Stookwijzer.async_transform_coordinates(session, 52.123456, 6.123456)
    print(x)
    print(y)

    if x and y:
        sw = stookwijzerapi.Stookwijzer(session, x, y)
        await sw.async_update()

        print(sw.advice)
        print(sw.alert)
        print(sw.windspeed_bft)
        print(sw.windspeed_ms)
        print(sw.lki)
        print(sw.forecast_advice)
        print(sw.forecast_alert)
    
    await session.close()
    
if __name__ == "__main__":
    asyncio.run(main())