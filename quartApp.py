from quart import Quart, render_template
import datetime as dt
import locale
import asyncio
from threading import Thread
import json

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/aca-py")
from runners import faber

import nest_asyncio
nest_asyncio.apply()

DATE_FORMAT = '%b %Y'
locale.setlocale(locale.LC_TIME, "ro_RO")

app = Quart(__name__)

USER = "Ciprian"
DEVICES = ["a", "b"]
agent = None

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

latestInvitation = ""


@app.route("/")
@app.route("/home")
async def home():
    return await render_template('home.html', user=USER, devices=DEVICES, date=getCurrentDate())


@app.route("/devices")
async def devices():
    global agent, latestInvitation

    await background_process_test()

    if agent is not None:
        return await render_template('devices.html', user=USER, devices=DEVICES, date=getCurrentDate(),
                                     invitation=latestInvitation)
    return await render_template('devices.html', user=USER, devices=DEVICES, date=getCurrentDate())


@app.route("/login")
async def login():
    return await render_template('login.html', date=getCurrentDate())


async def background_process_test():
    global agent, loop, latestInvitation
    latestInvitation = "updating..."
    if agent is not None:
        latestInvitation = json.dumps(loop.run_until_complete(generateInvitation())["invitation"])
        print(latestInvitation)
    return latestInvitation


async def generateInvitation():
    global agent
    return await agent.generate_invitation(display_qr=False, reuse_connections=agent.reuse_connections, wait=False)


def getCurrentDate():
    return dt.date.today().strftime(DATE_FORMAT)


def startWebApp():
    app.run(debug=True, host='0.0.0.0', port=5040)


def startAgent():
    global agent, loop
    agent = loop.run_until_complete(faber.runFaberAgentForWebApp())


if __name__ == '__main__':
    Thread(target=startAgent).start()
    startWebApp()
