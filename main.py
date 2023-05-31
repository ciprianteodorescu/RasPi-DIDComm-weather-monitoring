from flask import Flask, render_template
import datetime as dt
import locale
import asyncio
from threading import Thread

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/aca-py")
from runners import faber

DATE_FORMAT = '%b %Y'
locale.setlocale(locale.LC_TIME, "ro_RO")

app = Flask(__name__)

USER = "Ciprian"
DEVICES = ["a", "b"]


@app.route("/")
@app.route("/home")
def home():
    return render_template('home.html', user=USER, devices=DEVICES, date=getCurrentDate())


@app.route("/devices")
def devices():
    return render_template('devices.html', user=USER, devices=DEVICES, date=getCurrentDate())


@app.route("/login")
def login():
    return render_template('login.html', date=getCurrentDate())


def getCurrentDate():
    return dt.date.today().strftime(DATE_FORMAT)


def startWebApp():
    app.run(debug=True, host='0.0.0.0')


def startAgent():
    asyncio.run(faber.runFaberAgent())


if __name__ == '__main__':
    startAgent()
    startWebApp()
