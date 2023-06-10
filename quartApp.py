from quart import Quart, render_template, request
import datetime as dt
import locale
import asyncio
from threading import Thread
import json

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/aca-py")
from demo.runners import faber

import nest_asyncio

nest_asyncio.apply()

DATE_FORMAT = '%b %Y'
try:
    locale.setlocale(locale.LC_TIME, "ro_RO")
except:
    None

app = Quart(__name__)

IP_SCRIPT_DIR = "RasPi-DIDComm-weather-monitoring"

HOST = '0.0.0.0'
PORT = 5040

USER = "Ciprian"
labels = []
connection_ids = []
agent: faber.FaberAgent = None

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

latest_invitation = ""


@app.route("/")
@app.route("/home")
async def home():
    return await render_template('home.html', user=USER, labels=labels, date=get_current_date())


@app.route("/devices")
async def devices():
    global latest_invitation, labels, connection_ids

    refresh_connections()

    try:
        latest_invitation = json.dumps(run_in_coroutine(generate_invitation())["invitation"])
    except:
        latest_invitation = "agent not initialized yet"

    if agent is not None:
        return await render_template('devices.html', user=USER, labels=labels, connectionIds=connection_ids,
                                     date=get_current_date(), invitation=latest_invitation)
    return await render_template('devices.html', user=USER, labels=labels, connectionIds=connection_ids,
                                 date=get_current_date())


@app.route("/devices/<connection_id>")
async def device(connection_id):
    connection = await get_connection(connection_id)
    messages = sorted((await get_messages(connection_id)), key=sort_messages_key)
    timestamps = [m["sent_time"] for m in messages]
    messages = [int(m["content"]) for m in messages]

    return await render_template("device.html", user=USER, connection=connection, messages=messages, timestamps=timestamps, date=get_current_date())


@app.route("/login")
async def login():
    return await render_template('login.html', date=get_current_date())


def run_in_coroutine(task):
    return loop.run_until_complete(task)


@app.route("/get-invitation")
async def generate_invitation():
    try:
        return run_in_coroutine(
            agent.generate_invitation(display_qr=False, reuse_connections=agent.reuse_connections, wait=False))
    except:
        return {}


@app.route("/send-message", methods=['POST'])
async def send_message_to_device():
    args = await request.get_data()
    json_args = json.loads(args.decode("utf-8"))
    connection_id = json_args["connection_id"]
    t = json_args["t"]
    h = json_args["h"]
    w = json_args["w"]

    return run_in_coroutine(
        agent.agent.admin_POST(
            f"/connections/{connection_id}/send-message",
            {"content": args.decode("utf-8")},
        )
    )


@app.route("/connections")
async def connections():
    try:
        return run_in_coroutine(agent.admin_GET(f"/connections"))
    except:
        return {}


@app.route("/get-connection/<connection_id>")
async def get_connection(connection_id):
    try:
        return run_in_coroutine(agent.admin_GET(f"/connections/{connection_id}"))
    except:
        return {}


@app.route("/get-messages/<connection_id>")
async def get_messages(connection_id):
    try:
        return run_in_coroutine(agent.admin_GET(f"/connections/{connection_id}/basic-messages"))["results"]
    except:
        return {}


def refresh_connections():
    global connection_ids, labels
    try:
        conns = run_in_coroutine(agent.admin_GET(f"/connections"))["results"]
        labels = [i.get("their_label", None) for i in conns if i.get("their_label", None) is not None]
        connection_ids = [i.get("connection_id", None) for i in conns if i.get("connection_id", None) is not None]
    except:
        labels = []
        connection_ids = []
        print("failed retrieving connections")


def get_current_date():
    return dt.date.today().strftime(DATE_FORMAT)


def sort_messages_key(message):
    return message["sent_time"]


def start_web_app():
    app.run(debug=True, host=HOST, port=PORT)


def start_agent():
    global agent, loop
    agent = loop.run_until_complete(faber.runFaberAgentForWebApp(get_agent_endpoint()))


def get_agent_endpoint():
    agent_endpoint = ""
    if os.popen("uname").read().strip() == "Darwin":
        # determine if we need to go back to find the script
        wd = os.popen("pwd").read().strip().split("/")
        proj_i = 0
        for i in range(len(wd)):
            if wd[i] == IP_SCRIPT_DIR:
                proj_i = i
                break
        back = len(wd) - proj_i - 1

        # run the script
        if back == 0:
            agent_endpoint = os.popen("chmod +x ./macOS_get_ip.sh && ./macOS_get_ip.sh").read().strip()
        else:
            command = "chmod +x " + (back * "../") + "macOS_get_ip.sh && " + (back * "../") + "macOS_get_ip.sh"
            agent_endpoint = os.popen(command).read().strip()

    elif os.popen("uname").read().strip() == "Linux":
        agent_endpoint = os.popen("ip route get 8.8.8.8 | grep -oP 'src \\K[^ ]+'").read().strip()

    return agent_endpoint


if __name__ == '__main__':
    Thread(target=start_agent).start()
    start_web_app()
