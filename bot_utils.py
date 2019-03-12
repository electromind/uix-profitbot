# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import logging
import os
import random
import string
import struct
import sys
import time
from datetime import datetime
from socket import socket, AF_INET, SOCK_STREAM
import constants
import requests
from termcolor import colored
from requests.exceptions import RequestException as ReqError

error_log_path = 'log/errors.log'
tx_log_path = 'log/tx.log'
required_config_fields = [
    'public_key',
    'private_key',
    'pair',
    'size',
    'spread',
    'btmx_limit',
    'mining_limit'
]


def time_prefix():
    current_time = datetime.now()
    now = current_time.strftime("%H:%M:%S ")
    print(f'{now}', end='')


try:
    log_files = [error_log_path, tx_log_path]
    if not os.path.exists('log/'):
        os.mkdir(''.join([os.getcwd(), '/log']))
    else:
        for name in log_files:
            if not os.path.exists(name):
                with open(name, mode='w') as f:
                    f.close()
except Exception as e:
    msg = f"{time_prefix()} {e}"


def get_logger(logger_name: str):
    logger = logging.getLogger(logger_name)
    logging.basicConfig(level=logging.INFO)
    file_handler = logging.FileHandler(''.join(['log/', logger_name, '.log']))
    file_handler.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(created)s - %(name)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = get_logger('utils')


def write_error_log(msg: str, error=None):
    if isinstance(msg, str) and os.path.exists('log/errors.log'):
        err_flag = colored('ERR', color='red', attrs=['bold', 'blink'])
        timer = datetime.now().strftime("[%d-%m-%Y %H:%M:%S]")
        e_msg = f"{msg}\t{error.args}"
        try:
            with open('log/errors.log', mode='a') as f:
                f.write('\t'.join([timer, e_msg, '\n']))
                print(f"{time_prefix()} [{err_flag}]\terror was detected >> {e_msg}")
                f.close()
        except Exception as e:
            write_error_msg = f"{time_prefix()}\tcant log error.\n{time_prefix()}\t{e}\n{time_prefix()}\t{e.args}"
            logger.error(msg=write_error_msg)


def write_tx_log(tx_id: str, tx_side):
    # if tx_side == 'buy':
    #     flag = colored('BUY', color='green', attrs=['bold'])
    # elif tx_side == 'sell':
    #     flag = colored('SELL', color='magenta', attrs=['bold'])
    # else:
    #     flag = colored('TX', color='blue', attrs=['bold'])
    if isinstance(tx_id, str):
        with open('log/tx.log', mode='a') as f:
            f.write(tx_id + "\n")
            # print(f"[{flag}]\t{tx_id}")
            f.close()
    else:
        e_msg = f"{time_prefix()} Error: logfile not exist."
        logger.error(msg=e_msg)


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
    for i in range(sec, -1, -1):
        counter = colored(f'{i}', color='cyan', attrs=['blink', 'bold'])
        text = colored("\rMiner starts in: {0} seconds".format(counter))
        sys.stdout.write(f"\r{text}")
        sys.stdout.flush()
        time.sleep(1)
    print('')


def time_now():
    return datetime.now().strftime('[%d-%m-%Y %H:%M:%S:%f]')


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


def send_request(method, base_path, is_signed=False, base_url='https://bitmax.io/', api_path=None, api_key=None, api_sec=None, params=None, ts=None, coid=None):
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
            # print(time_prefix())
            print(f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S:%f')} {t}")
            logger.debug(msg=t)
            return t
        else:
            raise ReqError()
    # except requests.exceptions.ConnectionError as err:
    #     return {'error': f'{err.errno}', 'data': f'{err.args}'}
    except Exception as err:
        return {'error': f'{err.args}', 'data': f'url: {full_url}\tmethod: {method}\nPARAMS:\n{params}'}


def read_config() -> dict:
    try:
        with open('config.txt', 'r') as f:
            config = json.loads(f.read())
            return dict(config)
    except Exception as err:
        msg = f"{time_prefix()} Error: reading config. read_config()"
        write_error_log(msg, err)
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


class LazyConnection:
    def __init__(self, address, family=AF_INET, s_type=SOCK_STREAM):
        self.address = address
        self.family = family
        self.type = s_type
        self.sock = None

    def __enter__(self):
        if self.sock is not None:
            raise RuntimeError('Already connected')
        self.sock = socket(self.family, self.type)
        self.sock.connect(self.address)
        return self.sock

    def __exit__(self, exc_ty, exc_val, tb):
        self.sock.close()
        self.sock = None


def send_msg(sock, msg):
    # Prefix each message with a 4-byte length (network byte order)
    # msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)

def recv_msg(sock):
    # Read message length and unpack it into an integer
    raw_msglen = recvall(sock, 1024)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return recvall(sock, raw_msglen)

def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data