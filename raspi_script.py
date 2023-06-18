import asyncio
import nest_asyncio
from demo.runners import raspberry_agent
from utils import get_agent_endpoint

# TSL2561 imports
import board
import busio
from adafruit_tsl2561 import TSL2561

# HW-611 imports
from smbus2 import SMBus
from bmp280 import BMP280

# DHT22 imports
# import board
from adafruit_dht import DHT22
from time import sleep


nest_asyncio.apply()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

tsl2561 = None
bmp280 = None
dht22 = None


def initSensors():
    global tsl2561, bmp280, dht22
    i2c = busio.I2C(board.SCL, board.SDA)
    tsl2561 = TSL2561(i2c)

    bus = SMBus(1)
    bmp280 = BMP280(i2c_dev=bus)

    dht22 = DHT22(board.D4)


def readTSL2561():
    try:
        print("\nReading TSL2561 data")
        print(f'Broadband: {tsl2561.broadband}')
        print(f'Infrared: {tsl2561.infrared}')
        print(f'Lux: {tsl2561.lux}')
    except:
        print("\nCould not read TSL2561 data. Check wiring")


def readHW611():
    try:
        print("\nReading HW-611 data")
        print(f"Temperature: {bmp280.get_temperature()}")
        print(f"Pressure: {bmp280.get_pressure()}")
    except:
        print("\nCould not read HW-611 data. Check wiring")


def readDHT22():
    # TODO: refactor these try-except blocks
    try:
        print("\nReading DHT22 data")
        while True:
            try:
                print(f"Temperature: {dht22.temperature}")
                print(f"Humidity: {dht22.humidity}")
                break
            except RuntimeError:
                print("waiting for sensor")
                sleep(1)
            sleep(1)
    except:
        print("\nCould not read DHT22 data. Check wiring")


def start_agent():
    loop.run_until_complete(raspberry_agent.runAgent(get_agent_endpoint()))


if __name__ == "__main__":
    # TODO: check if postgres docker container is running, if not start it
    # start_agent()
    initSensors()
    while True:
        readTSL2561()
        readHW611()
        readDHT22()
        sleep(1)
