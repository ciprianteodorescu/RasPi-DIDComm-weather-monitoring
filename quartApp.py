from quart import Quart, render_template, request, redirect, url_for, flash
from quart_auth import AuthManager, login_required, Unauthorized, AuthUser, current_user, login_user, logout_user

import sqlalchemy as sa
import sqlalchemy.orm
from sqlalchemy.orm import Mapped, mapped_column
from quart_sqlalchemy import SQLAlchemyConfig
from quart_sqlalchemy.framework import QuartSQLAlchemy

from werkzeug.security import generate_password_hash, check_password_hash
import secrets
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
    pass

app = Quart(__name__)
db = QuartSQLAlchemy(
  config=SQLAlchemyConfig(
      binds=dict(
          default=dict(
              engine=dict(
                  url="sqlite:///db.sqlite",
                  echo=True,
                  connect_args=dict(check_same_thread=False),
              ),
              session=dict(
                  expire_on_commit=False,
              ),
          )
      )
  ),
  app=app,
)
auth_manager = AuthManager()


class DatabaseUser(db.Model, AuthUser):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(sa.Identity(), primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(sa.String(100), unique=True)
    password: Mapped[str] = mapped_column(sa.String(100))


class AuthenticationUser(AuthUser):
    def __init__(self, auth_id):
        super().__init__(auth_id)
        # self._resolved = False
        self.username = None

    # async def _resolve(self):
    #     if not self._resolved:
    #         with db.bind.Session() as session:
    #             user = session.query(DatabaseUser).filter_by(id=self.auth_id).first()
    #         self._username = user.username
    #         self._resolved = True
    #
    # @property
    # async def username(self):
    #     await self._resolve()
    #     return self._username

    async def load_user_data(self):
        if await current_user.is_authenticated:
            with db.bind.Session() as session:
                user = session.query(DatabaseUser).filter_by(id=self.auth_id).first()
            self.username = user.username


auth_manager.user_class = AuthenticationUser


db.create_all()


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
    return await render_template('home.html', user=current_user.username if current_user is not None else None, labels=labels, date=get_current_date())


@app.route("/devices")
@login_required
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
    location = await get_connection_location(connection_id)
    messages = sorted((await get_messages(connection_id)), key=sort_messages_key)
    timestamps = [m["sent_time"] for m in messages]

    values = [m["content"] for m in messages]
    temp_array = {}
    humidity_array = {}
    wind_array = {}
    for i in range(len(values)):
        # this try-except block is needed in case (some) messages are not json formatted
        try:
            json_values = json.loads(values[i])
            temp = json_values["temp"] if "temp" in json_values.keys() else None
            humidity = json_values["humidity"] if "humidity" in json_values.keys() else None
            wind = json_values["wind"] if "wind" in json_values.keys() else None
            if temp is not None:
                temp_array[timestamps[i]] = temp
            if humidity is not None:
                humidity_array[timestamps[i]] = humidity
            if wind is not None:
                wind_array[timestamps[i]] = wind
        except:
            pass

    return await render_template("device.html", user=USER, connection=connection, temp_array=temp_array,
                                 humidity_array=humidity_array, wind_array=wind_array, date=get_current_date(),
                                 location=location if location != "{}" else "")


@app.route("/signup")
async def signup():
    return await render_template('signup.html', date=get_current_date())


@app.route("/signup", methods=["POST"])
async def post_signup():
    form = await request.form
    username, password = form["username"], form["password"]

    with db.bind.Session() as session:
        user = session.query(DatabaseUser).filter_by(username=username).first()
    if user:
        await flash("Username already exists!")
        return redirect(url_for("signup"))

    new_user = DatabaseUser(username=username, password=generate_password_hash(password, method='sha256'))
    with db.bind.Session() as session:
        with session.begin():
            session.add(new_user)
            session.flush()
            session.refresh(new_user)
        # users = session.scalars(sa.select(User)).all()
    return redirect(url_for("login"))


@app.route("/login")
async def login():
    login_first = request.args.get("login_first", False)
    return await render_template('login.html', date=get_current_date(), login_first=login_first)


@app.route("/login", methods=["POST"])
async def post_login():
    form = await request.form
    username, password = form["username"], form["password"]

    with db.bind.Session() as session:
        user = session.query(DatabaseUser).filter_by(username=username).first()
        print(user)

    if user is None:
        await flash(f"No user found with username {username}!")
    elif check_password_hash(user.password, password):
        login_user(AuthUser(user.id))
    else:
        await flash("Incorrect password!")

    return redirect(url_for("home"))


@app.route("/logout")
async def logout():
    logout_user()

    return redirect(url_for("home"))


@app.before_request
@app.before_websocket
async def load_user():
    await current_user.load_user_data()


@app.errorhandler(Unauthorized)
async def redirect_to_login(*_):
    return redirect(url_for("login", login_first=True))


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
    content = {
        "temp": json_args["temp"],
        "humidity": json_args["humidity"],
        "wind": json_args["wind"]
    }

    content = json.dumps(content)

    return run_in_coroutine(
        agent.agent.admin_POST(
            f"/connections/{connection_id}/send-message",
            {"content": content},
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


@app.route("/set-connection-location/<connection_id>", methods=["POST"])
async def set_connection_location(connection_id):
    try:
        args = await request.get_data()
        json_args = json.loads(args.decode("utf-8"))
        location = json_args["location"]

        location_request = {"metadata": {"location": location}}
        return run_in_coroutine(
            agent.agent.admin_POST(
                f"/connections/{connection_id}/metadata",
                location_request,
            )
        )
    except:
        return {}


@app.route("/get-connection-location/<connection_id>")
async def get_connection_location(connection_id):
    try:
        return run_in_coroutine(
            agent.agent.admin_GET(
                f"/connections/{connection_id}/metadata",
            )
        )["results"]["location"]
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
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'

    app.config["QUART_AUTH_COOKIE_SECURE"] = False
    app.config["QUART_AUTH_COOKIE_NAME"] = "test_cookie"
    app.secret_key = 'oijwWduvRXtvvX2WHMKETA'  # secrets.token_urlsafe(16)

    auth_manager.init_app(app)

    app.run(debug=True, host=HOST, port=PORT)

    # db.init_app(app)
    # db.create_all()


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
