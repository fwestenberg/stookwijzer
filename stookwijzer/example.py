"""Example usage of the Stookwijzer API."""
import stookwijzerapi

if __name__ == "__main__":
    x, y = stookwijzerapi.Stookwijzer.transform_coordinates(52.123456, 6.123456)
    print(x)
    print(y)

    sw = stookwijzerapi.Stookwijzer(x, y)
    sw.update()
    
    print(sw.state)
    print(sw.alert)
    print(sw.windspeed_bft)
    print(sw.windspeed_ms)
    print(sw.lki)
    print(sw.forecast)
    