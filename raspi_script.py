import asyncio
import nest_asyncio
from demo.runners import raspberry_agent
from utils import get_agent_endpoint, run_in_coroutine

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

agent: raspberry_agent.RaspberryAgent = None


def initSensors():
    global tsl2561, bmp280, dht22
    i2c = busio.I2C(board.SCL, board.SDA)
    tsl2561 = TSL2561(i2c)

    bus = SMBus(1)
    bmp280 = BMP280(i2c_dev=bus)

    dht22 = DHT22(board.D4)


def readTSL2561():
    try:
        broadband = tsl2561.broadband
        infrared = tsl2561.infrared
        lux = tsl2561.lux
        print("\nReading TSL2561 data")
        print(f'Broadband: {broadband}')
        print(f'Infrared: {infrared}')
        print(f'Lux: {lux}')
        return {"broadband": broadband, "infrared": infrared, "lux": lux}
    except:
        print("\nCould not read TSL2561 data. Check wiring.")


def readHW611():
    try:
        temperature = bmp280.get_temperature()
        pressure = bmp280.get_pressure()
        print("\nReading HW-611 data")
        print(f"Temperature: {temperature}")
        print(f"Pressure: {pressure}")
        return {"temperature": temperature, "pressure": pressure}
    except:
        print("\nCould not read HW-611 data. Check wiring.")


def readDHT22():
    print("\nReading DHT22 data")
    while True:
        temperature = dht22.temperature
        humidity = dht22.humidity
        try:
            print(f"Temperature: {temperature}")
            print(f"Humidity: {humidity}")
            return {"temperature": temperature, "humidity": humidity}
        except RuntimeError as e:
            if e.args is "A full buffer was not returned. Try again.":
                print("Waiting for sensor...")
                sleep(1)
            else:
                print("Could not read DHT22 data. Check wiring.")
        sleep(1)


def sendMeasuredValues():
    content = {
        "TSL2561": readTSL2561(),
        "HW-611": readDHT22(),
        "DHT22": readDHT22(),
    }
    try:
        run_in_coroutine(
            loop,
            agent.agent.admin_POST(
                f"/connections/{raspberry_agent.agent.connection_id}/send-message",
                {"content": content},
            )
        )
    except:
        print("Could not send measured values")


def start_agent():
    global agent
    agent = loop.run_until_complete(raspberry_agent.runAgent(get_agent_endpoint()))


if __name__ == "__main__":
    # TODO: check if postgres docker container is running, if not start it
    start_agent()
    initSensors()
    while True:
        sendMeasuredValues()
        sleep(1)
