from typing import Any, List, Union

from quart import Quart, render_template, request, redirect, url_for, flash
from quart_auth import AuthManager, login_required, Unauthorized, AuthUser, current_user, login_user, logout_user

import sqlalchemy as sa
import sqlalchemy.orm
from sqlalchemy.orm import Mapped, mapped_column
from quart_sqlalchemy import SQLAlchemyConfig
from quart_sqlalchemy.framework import QuartSQLAlchemy

from werkzeug.security import generate_password_hash, check_password_hash
import datetime as dt
import locale
import asyncio
from threading import Thread
import json

from utils import get_agent_endpoint, run_in_coroutine
from demo.runners import server_agent

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

    async def load_user_data(self):
        if await current_user.is_authenticated:
            with db.bind.Session() as session:
                user = session.query(DatabaseUser).filter_by(id=self.auth_id).first()
            self.username = user.username


auth_manager.user_class = AuthenticationUser

db.create_all()

HOST = '0.0.0.0'
PORT = 5040

USER = "Ciprian"
labels = []
connection_ids = []
agent: server_agent.ServerAgent = None

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


@app.route("/")
@app.route("/home")
async def home():
    await get_last_measured_values()

    return await render_template_with_base_variables('home.html')


@app.route("/devices")
@login_required
async def devices():
    if agent is not None:
        return await render_template_with_base_variables('devices.html')


@app.route("/devices/<connection_id>")
@login_required
async def device(connection_id):
    connection = await get_connection(connection_id)
    location = await get_connection_location(connection_id)

    return await render_template_with_base_variables("device.html", connection=connection,
                                                     location=location if location != {} else "")


@app.route("/signup")
async def signup():
    return await render_template_with_base_variables('signup.html')


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
    return await render_template_with_base_variables('login.html', login_first=login_first)


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


@app.route("/get-invitation")
async def generate_invitation():
    try:
        return run_in_coroutine(
            loop,
            agent.generate_invitation(display_qr=False, reuse_connections=agent.reuse_connections, wait=False)
        )
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
        loop,
        agent.agent.admin_POST(
            f"/connections/{connection_id}/send-message",
            {"content": content},
        )
    )


@app.route("/connections")
async def connections():
    try:
        return run_in_coroutine(loop, agent.admin_GET(f"/connections"))
    except:
        return {}


@app.route("/get-connection/<connection_id>")
async def get_connection(connection_id):
    try:
        return run_in_coroutine(loop, agent.admin_GET(f"/connections/{connection_id}"))
    except:
        return {}


@app.route("/get-messages/<connection_id>")
async def get_messages(connection_id):
    try:
        return run_in_coroutine(loop, agent.admin_GET(f"/connections/{connection_id}/basic-messages"))["results"]
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
            loop,
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
            loop,
            agent.agent.admin_GET(
                f"/connections/{connection_id}/metadata",
            )
        )["results"]["location"]
    except:
        return {}


@app.route("/set-connection-user/<connection_id>", methods=["POST"])
async def set_connection_user(connection_id):
    try:
        args = await request.get_data()
        json_args = json.loads(args.decode("utf-8"))
        user = json_args["user"]

        user_request = {"metadata": {"user": user}}
        return run_in_coroutine(
            loop,
            agent.agent.admin_POST(
                f"/connections/{connection_id}/metadata",
                user_request,
            )
        )
    except:
        return {}


@app.route("/get-connection-user/<connection_id>")
async def get_connection_user(connection_id):
    try:
        return run_in_coroutine(
            loop,
            agent.agent.admin_GET(
                f"/connections/{connection_id}/metadata",
            )
        )["results"]["user"]
    except:
        return {}


@app.route("/set-sensor-types/<connection_id>", methods=["POST"])
async def set_sensor_types(connection_id):
    try:
        args = await request.get_data()
        json_args = json.loads(args.decode("utf-8"))

        sensor_types_request = {"metadata": json_args}
        return run_in_coroutine(
            loop,
            agent.agent.admin_POST(
                f"/connections/{connection_id}/metadata",
                sensor_types_request,
            )
        )
    except:
        return {}


@app.route("/get-sensor-types/<connection_id>")
async def get_sensor_types(connection_id):
    try:
        return run_in_coroutine(
            loop,
            agent.agent.admin_GET(
                f"/connections/{connection_id}/metadata",
            )
        )["results"]["sensor_types"]
    except:
        return {}


@app.route("/get-connection-from-did/<did>")
async def get_connection_from_did(did):
    try:
        return run_in_coroutine(
            loop,
            agent.agent.admin_GET(
                f"/connections", params={"their_did": did}
            )
        )["results"][0]
    except:
        return ""


@app.route("/get-measured-values/<connection_id>")
async def get_measured_values(connection_id):
    messages = sorted((await get_messages(connection_id)), key=sort_messages_key)
    timestamps = [m["sent_time"] for m in messages]

    values = [m["content"] for m in messages]
    lux_array = {}
    temp_hw611_array = {}
    pressure_array = {}
    temp_dht22_array = {}
    humidity_array = {}
    for i in range(len(values)):
        # this try-except block is needed in case (some) messages are not json formatted
        try:
            json_values = json.loads(values[i])
            tsl2561 = json_values["TSL2561"]
            hw611 = json_values["HW-611"]
            dht22 = json_values["DHT22"]

            lux = tsl2561["lux"] if "lux" in tsl2561.keys() else None
            temperature_hw611 = hw611["temperature"] if "temperature" in hw611.keys() else None
            pressure = hw611["pressure"] if "pressure" in hw611.keys() else None
            temperature_dht22 = dht22["temperature"] if "temperature" in dht22.keys() else None
            humidity = dht22["humidity"] if "humidity" in dht22.keys() else None

            if lux is not None:
                lux_array[timestamps[i]] = lux
            if temperature_hw611 is not None:
                temp_hw611_array[timestamps[i]] = temperature_hw611
            if pressure is not None:
                pressure_array[timestamps[i]] = pressure
            if temperature_dht22 is not None:
                temp_dht22_array[timestamps[i]] = temperature_dht22
            if humidity is not None:
                humidity_array[timestamps[i]] = humidity
        except:
            pass
    return {
        "lux_array": lux_array,
        "temp_hw611_array": temp_hw611_array,
        "pressure_array": pressure_array,
        "temp_dht22_array": temp_dht22_array,
        "humidity_array": humidity_array,
    }


@app.route("/get-last-measured-values")
async def get_last_measured_values():
    for conn_id in connection_ids:
        messages = await get_messages(conn_id)

        lux = None
        temp_hw611 = None
        pressure = None
        temp_dht22 = None
        humidity = None

        lux_time = ""
        temp_hw611_time = ""
        pressure_time = ""
        temp_dht22_time = ""
        humidity_time = ""

        for m in messages:
            timestamp = m["sent_time"]

            if timestamp >= lux_time or timestamp >= temp_hw611_time or timestamp >= pressure_time \
                    or timestamp >= temp_dht22_time or timestamp >= humidity_time:
                values = m["content"]
                json_values = json.loads(values)

                if timestamp >= lux_time:
                    tsl2561 = json_values["TSL2561"]
                    if "lux" in tsl2561.keys():
                        lux = tsl2561["lux"]
                        lux_time = timestamp

                if timestamp >= temp_hw611_time or timestamp >= pressure_time:
                    hw611 = json_values["HW-611"]
                    if "temperature" in hw611.keys():
                        temp_hw611 = hw611["temperature"]
                        temp_hw611_time = timestamp
                    if "pressure" in hw611.keys():
                        pressure = hw611["pressure"]
                        pressure_time = timestamp

                if timestamp >= temp_dht22_time or timestamp >= humidity_time:
                    dht22 = json_values["DHT22"]
                    if "temperature" in dht22.keys():
                        temp_dht22 = dht22["temperature"]
                        temp_dht22_time = timestamp
                    if "humidity" in dht22.keys():
                        humidity = dht22["humidity"]
                        humidity_time = timestamp

        return {
            "lux": {lux_time: lux},
            "temp_hw611": {temp_hw611_time: temp_hw611},
            "pressure": {pressure_time: pressure},
            "temp_dht22": {temp_dht22_time: temp_dht22},
            "humidity": {humidity_time: humidity},
        }


async def refresh_connections():
    global connection_ids, labels
    labels = []
    connection_ids = []
    try:
        # only fetch active connections
        conns = run_in_coroutine(loop, agent.admin_GET(f"/connections", params={'state': 'active'}))["results"]
        # filter by user
        for conn in conns:
            conn_user = await get_connection_user(conn.get("connection_id", ""))
            if conn_user == current_user.username and \
                    conn.get("their_label", "") != "" and conn.get("connection_id", "") != "":
                labels.append(conn.get("their_label", ""))
                connection_ids.append(conn.get("connection_id", ""))
    except:
        print("failed retrieving connections")


def get_current_date():
    return dt.date.today().strftime(DATE_FORMAT)


def sort_messages_key(message):
    return message["sent_time"]


async def render_template_with_base_variables(template: Union[str, List[str]], **context: Any) -> str:
    await refresh_connections()

    return await render_template(template, username=current_user.username, labels=labels,
                                 connection_ids=connection_ids, date=get_current_date(), **context)


def start_web_app():
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'

    app.config["QUART_AUTH_COOKIE_SECURE"] = False
    app.config["QUART_AUTH_COOKIE_NAME"] = "test_cookie"
    app.secret_key = 'oijwWduvRXtvvX2WHMKETA'  # secrets.token_urlsafe(16)

    auth_manager.init_app(app)

    app.run(debug=True, host=HOST, port=PORT)


def start_agent():
    global agent, loop
    agent = loop.run_until_complete(server_agent.runServerAgentForWebApp(get_agent_endpoint()))


if __name__ == '__main__':
    Thread(target=start_agent).start()
    start_web_app()
