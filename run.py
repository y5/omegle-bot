import hashlib
import json
import logging
import os
import random
import time
from threading import Thread

import requests
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String

import omegle_api

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


class config_prod():
    DEBUG = False

    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + \
        os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')


app = Flask(__name__)
app.config.from_object(config_prod)
db = SQLAlchemy()
db.init_app(app)


@app.before_first_request
def initialize_database():
    db.create_all()


@app.teardown_request
def shutdown_session(exception=None):
    db.session.remove()


class Thing(db.Model):
    __tablename__ = 'things'
    name = Column(String, primary_key=True, unique=True)
    value = Column(String)

    def __init__(self, **kwargs):
        for property, value in kwargs.items():
            if hasattr(value, '__iter__') and not isinstance(value, str):
                value = value[0]
            setattr(self, property, value)


status = 0


def it_convo(convo, replacements, api):
    for m in convo:
        time.sleep(0.2)
        api.start_typing()
        # TODO: adjust typing speed in wpm here
        typing_speed = 140
        time.sleep((len(m) / (typing_speed * 5)) * 60)
        api.stop_typing()

        for i in replacements:
            m = m.replace(i["key"], i["val"])

        api.send(m)

        last_proper_event = time.time()

        # TODO: adjust this to the max wait time to spend waiting (time without any kind of activity from partner)
        max_wait_time = 10
        while True:
            polled_event = api.get_event()

            if time.time() - last_proper_event > max_wait_time and polled_event[0] not in [7, 5]:
                api.disconnect()
                return

            if polled_event[0] == 6:
                break

            if polled_event[0] == 3:
                api.disconnect()
                return
    api.disconnect()


def worker():
    time.sleep(5)
    while True:
        res = requests.get("http://127.0.0.1:5000/api/status").json()
        if int(res["data"]["status"]) != 1:
            time.sleep(1)
            continue

        interests = requests.get(
            "http://127.0.0.1:5000/api/interests").json()["data"]["key"]
        convo = requests.get(
            "http://127.0.0.1:5000/api/conversation").json()["data"]["key"]
        replacements = requests.get(
            "http://127.0.0.1:5000/api/replace").json()["data"]["key"]
        proxy = requests.get(
            "http://127.0.0.1:5000/api/proxy").json()["data"]["key"]
        captchakey = requests.get(
            "http://127.0.0.1:5000/api/captchakey").json()["data"]["key"]
        api = omegle_api.omegle_api("de", interests, proxy, captchakey)
        r = api.start()

        if r is None:
            requests.post("http://127.0.0.1:5000/api/status", data="-1")
            continue

        while True:
            event = api.get_event()
            if event[0] == 4:
                print("[-] server notice", event[1])
                break
            elif event[0] == 2:
                time.sleep(0.1)

        it_convo(convo, replacements, api)


threads = []
# TODO: change thread count here
thread_count = 5
# TODO: (remove pound sign to use cpu core count times a factor)
# thread_count = int(multiprocessing.cpu_count()) * 5)

for _ in range(thread_count):
    t = Thread(target=worker)
    t.start()
    threads.append(t)


def make_id():
    return str(hashlib.md5((str(int(time.time())) + str(random.getrandbits(80))).encode('utf-8')).hexdigest())


@app.route("/")
def index():
    return render_template("home.html")


@app.route("/api/status", methods=["GET", "POST"])
def api_status():
    res = Thing.query.filter_by(name="status").first()

    if request.method == "GET":
        return {"status": "success", "message": "successfully retrieved system status", "data": {"status": res.value}}

    try:
        global status
        res.value = int(request.data)
        status = res.value
        db.session.commit()
        return {"status": "success", "message": "successfully updated system status"}
    except Exception:
        return {"status": "fail", "message": "failed to update system status"}


@app.route("/api/captchakey", methods=["GET", "POST"])
def captchakey():
    result = Thing.query.filter_by(name="2captcha_api_key").first()
    if request.method == "GET":
        return {"status": "success", "message": "successfully retrieved 2captcha api key", "data": {"key": result.value}}

    try:
        result.value = str(request.data.decode("utf-8"))
        db.session.commit()
        return {"status": "success", "message": "successfully updated 2captcha api key"}
    except Exception:
        return {"status": "fail", "message": "failed to update 2captcha api key"}


@app.route("/api/proxy", methods=["GET", "POST"])
def proxy():
    result = Thing.query.filter_by(name="proxy").first()
    if request.method == "GET":
        return {"status": "success", "message": "successfully retrieved proxy", "data": {"key": result.value}}

    try:
        result.value = str(request.data.decode("utf-8"))
        db.session.commit()
        return {"status": "success", "message": "successfully updated proxy"}
    except Exception:
        return {"status": "fail", "message": "failed to update proxy"}


@app.route("/api/conversation", methods=["GET", "POST"])
def conversation():
    result = Thing.query.filter_by(name="conversation").first()
    if request.method == "GET":
        return {"status": "success", "message": "successfully retrieved conversation", "data": {"key": json.loads(result.value)}}

    try:
        result.value = str(request.data.decode("utf-8"))
        db.session.commit()
        return {"status": "success", "message": "successfully updated conversation"}
    except Exception:
        return {"status": "fail", "message": "failed to update conversation"}


@app.route("/api/interests", methods=["GET", "POST"])
def api_interests():
    result = Thing.query.filter_by(name="interests").first()
    if request.method == "GET":
        return {"status": "success", "message": "successfully retrieved interests", "data": {"key": json.loads(result.value)}}

    try:
        result.value = str(request.data.decode("utf-8"))
        db.session.commit()
        return {"status": "success", "message": "successfully updated interests"}
    except Exception:
        return {"status": "fail", "message": "failed to update conversation"}


@app.route("/api/replace", methods=["GET", "POST"])
def replace():
    result = Thing.query.filter_by(name="replacements").first()
    if request.method == "GET":
        return {"status": "success", "message": "successfully retrieved replacements", "data": {"key": json.loads(result.value)}}

    try:
        result.value = str(request.data.decode("utf-8"))
        db.session.commit()
        return {"status": "success", "message": "successfully updated replacements"}
    except Exception:
        return {"status": "fail", "message": "failed to update replacements"}


@app.route("/api/add_thing/<string:key>/<value>", methods=["POST"])
def save(key, value):
    try:
        print(key, value)
        db.session.add(Thing(name=key, value=value))
        db.session.commit()
        return {"status": "success", "message": "successfully added new key-value pair"}
    except Exception:
        return {"status": "fail", "message": "failed to add new key-value pair"}


app.run(debug=True)
