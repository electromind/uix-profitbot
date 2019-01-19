# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import logging
import os
import random
import socket
import string
from datetime import datetime

import requests

log_dir_path = 'log/'
logfile_name = 'main.log'


# send statistic data to auditor_bot
def send_stat(stat_data):
    try:
        json_data = json.loads(stat_data)
        fragment = (json_data['user_id'])
        tx = (json_data['tx_list'])
        conn = socket.socket()
        conn.connect(('109.104.178.163', 2511))
        conn.send(bytes(json_data, 'utf-8'))
        conn.close()
        del json_data, fragment, tx
        return True
    except Exception as e:
        print(e)
        return False


def create_list(filename=logfile_name):
    if isinstance(filename, str):
        with open(filename) as file:
            tx_list = list()
            for line in file:
                tx_list.append(line)
            return tx_list
    else:
        return False


def clear_log(filename=logfile_name):
    try:
        desc = open(filename, 'w')
        desc.close()
    except Exception as e:
        print(e)


def time_prefix():
    current_time = datetime.now()
    now = current_time.strftime("%d-%m-%Y %H:%M:%S:%f\t")
    print(f'{now}', end='')
    return now


def uuid32():
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(32))


def get_utc_timestamp() -> int:
    tm = datetime.utcnow().timestamp()
    return int(tm * 1e3)


def get_timestamp() -> str:
    ts = datetime.now()
    return ts.strftime("%d-%m-%Y %H:%M:00")


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


def get_logger(logger_name: str):
    if not os.path.exists(log_dir_path):
        os.mkdir(log_dir_path)
    elif not os.path.isfile(logfile_name):
        f = open(logfile_name, 'a')
        f.close()
    else:
        pass

    logger = logging.getLogger(logger_name)
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M',
        filename=f'log/main.log')

    file_handler = logging.FileHandler(''.join(['log/', logger_name, '.log']))
    file_handler.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(levelname)s - %(asctime)s - %(name)s - %(message)s')
    file_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def read_config() -> dict:
    try:
        with open('config.json', 'r') as f:
            config = json.loads(f.read())
            return dict(config)
    except Exception as err:
        print(f"{err.args}")


def tx_cross_side(side: str) -> str:
    return 'buy' if side == 'sell' else 'sell'

