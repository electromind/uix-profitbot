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
import sys
from datetime import datetime

import requests

import constants


def get_logger(logger_name: str):
    logger = logging.getLogger(logger_name)
    logging.basicConfig(level=logging.INFO)
    file_handler = logging.FileHandler(''.join(['log/', logger_name, '.log']))
    file_handler.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(created)s - %(name)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = get_logger('utils')


def write_tx(txid: str):
    if isinstance(txid, str):
        with open('log/tx.log', mode='a') as f:
            f.writelines(''.join([txid, '\n']))
            f.close()


# send statistic data to statserver
def send_log_data(userkey: str, logfile_path: str):
    global conn
    if os.path.exists(logfile_path):
        conn = socket.socket()
    else:
        sys.exit("wrong file path")
    try:
        conn.connect((constants.network, constants.port))
        tx_data_pack = dict(user_id=userkey)
        with open(logfile_path) as f:
            tx_list = []
            for line in f.readlines():
                tx_list.append(line)
            tx_data_pack['tx_list'] = tx_list
            conn.send(bytes(json.dumps(tx_data_pack), 'utf-8'))
        clear_log_data(logfile_path)
    except FileNotFoundError as e:
        logger.error(f"Logfile is not exist.\t{e}")
    except Exception as e:
        logger.error(f"{e}")
    finally:
        conn.close()


def clear_log_data(logfile_path: str):
    try:
        desc = open(logfile_path, 'w')
        desc.close()
    except Exception as e:
        print(e)


def time_prefix():
    current_time = datetime.now()
    now = current_time.strftime("%d-%m-%Y %H:%M:%S:%f\t")
    print(f'{now}', end='')
    return now


def time_no_prefix():
    current_time = datetime.now()
    now = current_time.strftime("[%d-%m-%Y %H:%M:%S]\t")
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


def read_config() -> dict:
    try:
        with open('config.json', 'r') as f:
            config = json.loads(f.read())
            return dict(config)
    except Exception as err:
        print(f"{err.args}")


def read_test_config() -> dict:
    try:
        with open('config_test.json', 'r') as f:
            config = json.loads(f.read())
            return dict(config)
    except Exception as err:
        print(f"{err.args}")


def tx_cross_side(side: str) -> str:
    return 'buy' if side == 'sell' else 'sell'

