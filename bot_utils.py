# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import logging
import os
import pathlib
import random
import string
import sys
import time
from datetime import datetime
from socket import socket, AF_INET, SOCK_STREAM

import requests
from requests.exceptions import RequestException as ReqError
from termcolor import colored

from constants import AppMode
from req_counter import ReqCounter as MyRequests

error_log_path = 'log/errors.log'
tx_log_path = 'log/tx.log'
required_config_fields = [
    'public_key',
    'private_key',
    'pair',
    'size',
    'spread',
    'btmx_limit',
    'mining_limit',
    'role'
]


def time_now():
    return datetime.now().strftime('[%d-%m-%Y %H:%M:%S:%f]')


def time_prefix():
    current_time = datetime.now()
    now = current_time.strftime("%H:%M:%S ")
    print(f'{now}', end='')


class Log(logging.Logger):

    def __init__(self, n: str, loglevel=logging.INFO):
        super().__init__(name=n, level=loglevel)
        format('%(levelname)s %(message)s')
        # self.logger_format = '%(levelname)s %(message)s'
        # if platform.system() == 'Windows':
        #     separator = '\\'
        # else:
        #     separator = '/'
        # # tmp = str(__file).replace('.py', '_').split(separator)

        self.logfile_name = ''.join([n, time_now(), '.log'])
        self.__logdir_path = pathlib.Path('\\'.join([os.path.dirname(__file__), 'log']))
        if not os.path.exists(self.__logdir_path):
            os.mkdir(self.__logdir_path)
        self.__path_to_log = self.__logdir_path / self.logfile_name

        if not os.path.isfile(self.__path_to_log):
            file = self.__path_to_log.open('w')
            file.close()

        logfile_handler = logging.FileHandler(filename=self.__path_to_log, encoding='utf-8')
        self.addHandler(logfile_handler)
        logstream = logging.StreamHandler()
        self.addHandler(logstream)


logger = Log('utils_')
r = MyRequests()


def write_tx_log(tx_id: str, tx_side):
    pass


def get_config(path: str):
    if isinstance(path, str):
        with open(path, mode='r') as f:
            raw_config = f.readlines()
            config_data = {}
            for line in raw_config:
                if isinstance(line, str) and ':' in line:
                    k, v = line.replace('\n', '').split(': ')
                    if k in required_config_fields and v:
                        if '//' in v:
                            tmp = v.split('//')[0]
                        else:
                            tmp = v
                        if '%' in tmp:
                            tmp = tmp.split('%')[0].strip()
                            if tmp.isdigit():
                                v_digit = float(tmp) / 100
                                config_data[k] = v_digit
                        elif v.isdigit():
                            config_data[k] = float(v)
                        else:
                            config_data[k] = v
            return config_data


def countdown(sec):
    tmp_time = time_now()
    for i in range(sec, -1, -1):
        counter = colored(f'{i}', color='cyan', attrs=['blink', 'bold'])
        text = colored("\r{0} Miner starts in: {1} seconds".format(tmp_time, counter))
        sys.stdout.write(f"\r{text}")
        sys.stdout.flush()
        time.sleep(1)
    print('')


def uuid32():
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(32))


def get_utc_timestamp() -> int:
    tm = datetime.utcnow().timestamp()
    return int(tm * 1e3)


def get_local_timestamp() -> str:
    ts = datetime.now()
    return ts.strftime("%d-%m-%Y %H:%M:00")


def make_auth_header(timestamp, api_path, api_key, secret, coid=None):
    if isinstance(timestamp, bytes):
        timestamp = timestamp.decode("utf-8")
    elif isinstance(timestamp, int):
        timestamp = str(timestamp)

    if coid is None:
        msg = bytearray(f"{timestamp}+{api_path}".encode("utf-8"))
    elif isinstance(coid, list):
        coids = '+'.join(coid)
        msg = bytearray(f"{timestamp}+{api_path}+{coids}".encode("utf-8"))
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
        # header["Content-Type"] = 'application/json'
    return header


def send_request(
        method,
        base_path,
        is_signed=False,
        base_url='https://bitmax.io/',
        api_path=None,
        api_key=None,
        api_sec=None,
        params=None,
        ts=None,
        coid=None
):
    try:
        full_url = base_url + base_path
        if is_signed:
            # REQUEST AUTH HEADER
            headers = make_auth_header(api_path=api_path, api_key=api_key, secret=api_sec, timestamp=ts, coid=coid)
            response = requests.request(method=method, url=full_url, headers=headers, json=params)
        else:
            response = requests.request(method=method, url=full_url, params=params)

        if response and response.status_code == 200:
            t = response.json()

            print(f'Total: {r.get_total()}')
            return t
        else:
            raise ReqError()
    # except requests.exceptions.ConnectionError as err:
    #     return {'error': f'{err.errno}', 'data': f'{err.args}'}
    except Exception as err:
        return dict(
            error=f'{err.args}',
            data=f'url: {full_url}',
            method=method,
            params=params,
        )


def read_config(path: str) -> dict:
    try:
        with open(path, 'r') as f:
            config = json.loads(f.read())
            return dict(config)
    except Exception as err:
        msg = f"{time_now()} Error: reading config. read_config()"
        logger.error(msg, err)


def read_test_config() -> dict:
    try:
        with open('config_test.json', 'r') as f:
            config = json.loads(f.read())
            return dict(config)
    except Exception as err:
        logger.error(err)


def tx_cross_side(side: str) -> str:
    return 'buy' if side == 'sell' else 'sell'


class TCPClient:
    def __init__(self, server_address=None):
        self.my_socket = socket(AF_INET, SOCK_STREAM)
        if server_address is None:
            self.address = (AppMode.mainnet, AppMode.port_main)
        else:
            self.address = server_address

    def start(self, addr: tuple):
        self.my_socket = socket(AF_INET, SOCK_STREAM)
        self.my_socket.settimeout(10)
        try:
            self.my_socket.connect(addr)
        except ConnectionRefusedError as err:
            print(f"{time_now()} {err}")
            countdown(5)
            # logger.info(f'\nServer offline. Reconnect after {countdown(5)} sec')

            self.start(addr=addr)

    def send_msg(self, smsg: str):
        self.start(self.address)
        raw_msg = bytes(smsg.encode('utf-8'))
        data = b""
        try:
            self.my_socket.send(raw_msg)
            while True:
                packet = self.my_socket.recv(2048)
                if packet:
                    data += packet
                else:
                    break
        except Exception as err:
            print(f"\n{err}")
        # print(f">>> {data.decode('utf-8')}")
        # self.send_msg(smsg=smsg)
        self.my_socket.close()
        return str(data, encoding='utf-8')
