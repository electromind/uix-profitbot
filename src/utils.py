# -*- coding: utf-8 -*-
import requests
import json
import hmac
import base64
import hashlib
import random
import string
from datetime import datetime


def uuid32():
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(32))


def utc_timestamp():
    tm = datetime.utcnow().timestamp()
    return int(tm * 1e3)


def print_logtime(logging=False):
    init_time = datetime.now()
    now = init_time.strftime("[%d-%m-%Y %H:%M:%S:%f] ")
    if not logging:
        print(f'{now}', end='')
    else:
        now = init_time.strftime("[%d-%m-%Y %H]")
        return f'{now}'


def make_auth_header(timestamp, api_path, api_key, secret, coid=None):

    if isinstance(timestamp, bytes):
        timestamp = timestamp.decode("utf-8")
    elif isinstance(timestamp, int):
        timestamp = str(timestamp)

    if coid is None:
        msg = bytearray(f"{timestamp}+{api_path}".encode("utf-8"))
    else:
        msg = bytearray(f"{timestamp}+{api_path}+{coid}".encode("utf-8"))

    hmac_key = base64.b64decode(secret)
    signature = hmac.new(hmac_key, msg, hashlib.sha256)
    signature_b64 = base64.b64encode(signature.digest()).decode("utf-8")
    header = {
        "x-auth-key": api_key,
        "x-auth-signature": signature_b64,
        "x-auth-timestamp": timestamp,
    }

    if coid is not None:
        header["x-auth-coid"] = coid
        header["Content-Type"] = 'application/json'
    return header


def send_request(method, base_path, is_signed=False, base_url='https://bitmax.io/', api_path=None,
                 api_key=None, api_sec=None, params=None, ts=None, coid=None):

    full_url = base_url + base_path
    try:
        if method == "GET" or "POST" or "DELETE":
            if is_signed:
                ### REQUEST AUTH HEADER
                headers = make_auth_header(api_path=api_path, api_key=api_key, secret=api_sec, timestamp=ts, coid=coid)
                response = requests.request(method=method, url=full_url, headers=headers, json=params)
            else:
                response = requests.request(method=method, url=full_url, params=params)
        else:
            response = None

        if response and response.status_code == 200:
            return response.json()
        else:
            raise requests.exceptions.ConnectionError
    except requests.exceptions.ConnectionError as err:
        return {'error': f'{err.errno}', 'data': f'{err.args}'}
    except Exception as err:
        return {'error': f'{err.args}', 'data': f'url: {full_url}\tmethod: {method}\nPARAMS:\n{params}'}


def read_config():
    try:
        with open('config.json', 'r') as f:
            config = json.loads(f.read())
            return dict(config)
    except Exception as err:
        print(f"{err.args}")


def cross_side(side):
    if side == 'sell':
        return 'buy'
    elif side == 'buy':
        return 'sell'
    else:
        return None


