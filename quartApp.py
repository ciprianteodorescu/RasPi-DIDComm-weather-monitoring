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
devices = []
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
    global agent, latestInvitation, devices

    try:
        devices = [i.get("their_label", None) for i in runInCoroutine(agent.admin_GET(f"/connections"))["results"] if i.get("their_label", None) is not None]
    except:
        devices = []
        print("failed retrieving connections")

    try:
        latestInvitation = json.dumps(runInCoroutine(generateInvitation())["invitation"])
    except:
        latestInvitation = "agent not initialized yet"

    if agent is not None:
        return await render_template('devices.html', user=USER, devices=devices, date=getCurrentDate(),
                                     invitation=latestInvitation)
    return await render_template('devices.html', user=USER, devices=devices, date=getCurrentDate())


@app.route("/login")
async def login():
    return await render_template('login.html', date=getCurrentDate())


def runInCoroutine(task):
    global agent, loop

    return loop.run_until_complete(task)


async def generateInvitation():
    global agent
    return runInCoroutine(agent.generate_invitation(display_qr=False, reuse_connections=agent.reuse_connections, wait=False))


@app.route("/conn")
async def connections():
    try:
        return runInCoroutine(agent.admin_GET(f"/connections"))
    except:
        return "{}"


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
