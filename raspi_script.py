import asyncio
import nest_asyncio
from demo.runners import raspberry_agent
from utils import get_agent_endpoint, run_in_coroutine
import json

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
from time import sleep, time


nest_asyncio.apply()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

i2c = None
bus = None

tsl2561 = None
hw611 = None
dht22 = None

agent: raspberry_agent.RaspberryAgent = None


def initSensors():
    global i2c, bus
    global tsl2561, hw611, dht22

    try:
        i2c.deinit()
    except:
        pass

    try:
        bus.close()
    except:
        pass

    try:
        dht22.exit()
    except:
        pass

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        tsl2561 = TSL2561(i2c)
    except:
        print("TSL2561 sensor not found. Check wiring.")

    try:
        bus = SMBus(1)
        hw611 = BMP280(i2c_dev=bus)
    except:
        print("BMP280 sensor not found. Check wiring.")

    try:
        dht22 = DHT22(board.D4)
    except:
        print("DHT22 sensor not found. Check wiring.")


def readTSL2561():
    try:
        broadband = round(tsl2561.broadband, 1)
        infrared = round(tsl2561.infrared, 1)
        lux = round(tsl2561.lux, 1)
        print("\nReading TSL2561 data")
        print(f'Broadband: {broadband}')
        print(f'Infrared: {infrared}')
        print(f'Lux: {lux}')
        return {"broadband": broadband, "infrared": infrared, "lux": lux}
    except:
        print("\nCould not read TSL2561 data. Check wiring.")
        return {}


def readHW611():
    try:
        temperature = round(hw611.get_temperature(), 1)
        pressure = round(hw611.get_pressure(), 1)
        print("\nReading HW-611 data")
        print(f"Temperature: {temperature}")
        print(f"Pressure: {pressure}")
        return {"temperature": temperature, "pressure": pressure}
    except:
        print("\nCould not read HW-611 data. Check wiring.")
        return {}


def readDHT22():
    print("\nReading DHT22 data")
    while True:
        try:
            temperature = round(dht22.temperature, 1)
            humidity = round(dht22.humidity, 1)
            print(f"Temperature: {temperature}")
            print(f"Humidity: {humidity}")
            return {"temperature": temperature, "humidity": humidity}
        except (RuntimeError, OverflowError) as e:
            if e.args == "A full buffer was not returned. Try again."\
                    or e.args == "unsigned short is greater than maximum":
                print("Waiting for sensor...")
                sleep(1)
            else:
                print("Could not read DHT22 data. Check wiring.")
                return {}
        except TypeError:
            print("Could not read DHT22 data. Check wiring.")
            return {}
        sleep(1)


def sendMeasuredValues():
    content = {
        "TSL2561": readTSL2561(),
        "HW-611": readHW611(),
        "DHT22": readDHT22(),
        "timestamp": time() * 1000,
    }
    content = json.dumps(content)
    try:
        run_in_coroutine(
            loop,
            agent.agent.admin_POST(
                f"/connections/{agent.agent.connection_id}/send-message",
                {"content": content},
            )
        )
    except:
        print("Could not send measured values")


def start_agent():
    global agent
    agent = loop.run_until_complete(raspberry_agent.runAgent("raspberrypi.local"))


if __name__ == "__main__":
    # TODO: check if postgres docker container is running, if not start it
    start_agent()
    while True:
        initSensors()
        sendMeasuredValues()
        sleep(5)
