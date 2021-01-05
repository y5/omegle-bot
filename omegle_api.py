import json
import queue
import random
import time
import requests
from requests.auth import HTTPProxyAuth

#TODO: SORRY FOR SHITTY CODE THIS WAS WRITTEN IN UNDER 30MINS OK COOL THANKS
#TODO: also most of this code is pasted from https://github.com/coal0/python-omegle/

class omegle_api():
    def __init__(self, language, interests, proxy, captchakey):
        self.language = language
        self.captchakey = captchakey
        self._server_url = f"https://front{str(random.randrange(31) + 1)}.omegle.com/"
        self._events = queue.Queue()
        self._random_id = "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        self._chat_id = None
        self._chat_ready_flag = False
        self.interests = interests

        if proxy != "":
            protocol = proxy[:proxy.find("--")]
            proxy = proxy[proxy.find("--") + 2:]
            host = proxy[:proxy.find("--")]
            proxy = proxy[proxy.find("--") + 2:]
            port = proxy[:proxy.find("--")]
            proxy = proxy[proxy.find("--") + 2:]
            self.proxies = {protocol:host + ":" + str(port)}
            self.auth = HTTPProxyAuth(proxy[:proxy.find("--")], proxy[proxy.find("--") + 2:])

    def start(self):
        response = requests.get(self._server_url + "start?caps=recaptcha2&rcs=1&firstevents=1&randid={}&lang={}&topics={}".format(self._random_id, self.language, json.dumps(self.interests)), proxies=self.proxies if hasattr(self, "proxies") else None, auth=self.auth if hasattr(self, "proxies") else None)

        if response.status_code != 200:
            return None

        if response.text == "{}":
            return None

        json_data = response.json()
        try:
            self._chat_id = json_data["clientID"]
        except:
            return None

        try:
            events_json = json_data["events"]
        except:
            return None
        self.classify_events(events_json=events_json)
        return True

    def bypass_captcha(self, site_key):
        url = requests.get(f"https://2captcha.com/in.php?key={self.captchakey}&method=userrecaptcha&googlekey={site_key}&pageurl=https://omegle.com/&json=1")
        status = url.json()["status"]
        if status != 1:
            return False

        time.sleep(10)
        solve_id = url.json()["request"]
        result = requests.get(f"https://2captcha.com/res.php?key={self.captchakey}&action=get&id={solve_id}")
        while result.text != "CAPTCHA_NOT_READY":
            result = requests.get(f"https://2captcha.com/res.php?key={self.captchakey}&action=get&id={solve_id}")
        
        response = requests.post(self._server_url + "recaptcha", proxies=self.proxies if hasattr(self, "proxies") else None, auth=self.auth if hasattr(self, "proxies") else None, data={"response":result.text, "id": str(self._chat_id)})
        return response.text == "win"

    def classify_events(self, events_json):
        for event in events_json:
            event_type = event[0]

            if event_type == "connected":
                self._chat_ready_flag = True
                self._events.put((1, None))

            elif event_type == "waiting":
                self._events.put((2, None))

            elif event_type == "typing":
                if not self._chat_ready_flag:
                    self._chat_ready_flag = True
                self._events.put((6, None))

            elif event_type == "stoppedTyping":
                self._events.put((7, None))

            elif event_type == "gotMessage":
                if not self._chat_ready_flag:
                    self._chat_ready_flag = True
                self._events.put((5, event[1]))

            elif event_type == "strangerDisconnected":
                self._events.put((3, None))
                self._chat_ready_flag = False

            elif event_type == "serverMessage":
                notice = event[1]
                self._events.put((4, notice))

            elif event_type == "recaptchaRequired":
                print("[+] bypassing captcha...")
                if not self.bypass_captcha(event[1]):
                    raise Exception("fuck imagine actually managing to solve the captcha reeeeeeeeeeeeee")
                self._events.put(self.get_event())

    def send(self, message):
        requests.post(self._server_url + "send", data={"id": self._chat_id, "msg": message}, proxies=self.proxies if hasattr(self, "proxies") else None, auth=self.auth if hasattr(self, "proxies") else None)

    def get_event(self):
        try:
            return self._events.get_nowait()
        except queue.Empty:
            pass

        events_json = self._get_new_events()
        self.classify_events(events_json=events_json)
        return self._events.get()

    def disconnect(self):
        requests.post(self._server_url + "disconnect", data={"id": self._chat_id}, proxies=self.proxies if hasattr(self, "proxies") else None, auth=self.auth if hasattr(self, "proxies") else None)
        self._chat_ready_flag = False

    def start_typing(self):
        requests.post(self._server_url + "typing", data={"id": self._chat_id}, proxies=self.proxies if hasattr(self, "proxies") else None, auth=self.auth if hasattr(self, "proxies") else None)

    def stop_typing(self):
        requests.post(self._server_url + "stoppedtyping", data={"id": self._chat_id}, proxies=self.proxies if hasattr(self, "proxies") else None, auth=self.auth if hasattr(self, "proxies") else None)

    def _get_new_events(self):
        while True:
            json_data = requests.post(self._server_url + "events", data={"id": self._chat_id}, proxies=self.proxies if hasattr(self, "proxies") else None, auth=self.auth if hasattr(self, "proxies") else None).json()
            if json_data not in (None, []):
                return json_data
