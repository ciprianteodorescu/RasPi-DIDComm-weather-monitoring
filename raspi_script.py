import asyncio
import nest_asyncio
from demo.runners import raspberry_agent
from utils import get_agent_endpoint

# TSL2561 imports
import board
import busio
import adafruit_tsl2561 as tsl2561

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

def readTSL2561():
    i2c = busio.I2C(board.SCL, board.SDA)
    sensor = tsl2561.TSL2561(i2c)
    print("Reading TSL2561 data")
    print(f'Broadband: {sensor.broadband}')
    print(f'Infrared: {sensor.infrared}')
    print(f'Luminosity: {sensor.luminosity}')


def readHW611():
    bus = SMBus(1)
    bmp280 = BMP280(i2c_dev=bus)
    print("Reading HW-611 data")
    print(f"Temperature: {bmp280.get_temperature()}")
    print(f"Pressure: {bmp280.get_pressure()}")


def readDHT22():
    dht22 = DHT22(board.D4)
    print("Reading DHT22 data")
    while True:
        try:
            print(f"Temperature: {dht22.temperature}")
            print(f"Humidity: {dht22.humidity}")
        except RuntimeError:
            print("waiting for sensor")
            sleep(1)
        sleep(1)


def start_agent():
    loop.run_until_complete(raspberry_agent.runAgent(get_agent_endpoint()))


if __name__ == "__main__":
    # TODO: check if postgres docker container is running, if not start it
    # start_agent()
    while True:
        readTSL2561()
        readHW611()
        readDHT22()
