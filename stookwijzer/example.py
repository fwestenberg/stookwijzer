"""Example usage of the Stookwijzer API."""
import sys
import aiohttp
import asyncio
import stookwijzerapi

async def main():
    session = aiohttp.ClientSession()

    x, y = await stookwijzerapi.Stookwijzer.transform_coordinates(session, 52.123456, 6.123456)
    print(x)
    print(y)

    if x and y:
        sw = stookwijzerapi.Stookwijzer(session, x, y)
        await sw.update()

        print(sw.state)
        print(sw.alert)
        print(sw.windspeed_bft)
        print(sw.windspeed_ms)
        print(sw.lki)
        print(sw.forecast)
    
    await session.close()
    
if __name__ == "__main__":
    asyncio.run(main())