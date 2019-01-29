# -*- coding: utf-8 -*-
import json
import os
import socket
import sys
from datetime import datetime
from typing import Dict, Any, Union

import constants
from bot_utils import send_request, get_utc_timestamp, uuid32, time_prefix, write_tx

testnet_url = 'https://bitmax-test.io/'
mainnet_url = 'https://bitmax.io/'
websocket_url = 'wss://bitmax.io/'


# logger = get_logger('tx')


class Bitmax:

    def __init__(self, user=None, base_url='https://bitmax.io/', pair=None):
        try:
            if user:
                try:
                    self.name = user.get('name')
                except Exception:
                    self.name = '_'.join(['bot', uuid32()[:4]])
                    print(f"{self.name}")
                self.base_url = base_url
                self.api_key = user.get('public_key')
                self.secret = user.get('secret')
                self.id = self.api_key
                self.account_group = self._get_user_info()
                self.is_maker = False
                self.open_orders = []

                if pair is None:
                    time_prefix()
                    print('Invalid Pair or missing')
                    sys.exit(1)
                else:
                    self.pair = pair
            else:
                raise AttributeError(
                    'Cant create bot instance, user credentials wrong or missing. Please recheck config file and try again')
        except AttributeError as e:
            print(f"{e}")

    def auth(self):
        p = constants.port_main
        t = constants.mainnet
        idd = self.api_key
        if constants.app_mode == 'debug_no_auth':
            return True
        else:
            with socket.socket() as s:
                try:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.settimeout(15)
                    s.connect((t, p))
                    auth_string = f"auth_me:{idd}".encode('utf-8')
                except ConnectionError as e:
                    print(f"{e.strerror}\n{e}")
                    sys.exit('No connection to server')
                s.send(auth_string)
                tmp_data = s.recv(512)
                resp = str(tmp_data, encoding='utf-8')
                if resp == 'True':
                    time_prefix()
                    print(f'{self.name}\tauthorized.')
                    s.close()
                    return True
                else:
                    time_prefix()
                    print('Invalid Key. Please recheck config file.')
                    s.close()
                    return False

    def _get_user_info(self):
        resp = send_request(
            is_signed=True,
            method='GET',
            base_path='api/v1/user/info',
            api_path='user/info',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=get_utc_timestamp()
        )
        r = resp.get('accountGroup')
        print(r)
        return r

# ############## request asset list or single asset ############## #

    @classmethod
    def request_assets(cls):
        try:
            assets = send_request(method='GET', base_path='api/v1/assets')
            return assets
        except Exception as e:
            time_prefix()
            print(f'invalid request \t{cls.request_assets.__name__}\n{e}')
            return sys.exit(1)

    @classmethod
    def get_assets(cls) -> dict:
        working_assets = dict()
        for a in cls.request_assets():
            if a.get('status') == 'Normal':
                working_assets[a['assetCode']] = {
                        'id': a.get('assetCode'),
                        'name': a.get('assetName'),
                        'step': round(0.1 ** (a.get('nativeScale')), int(a.get('nativeScale'))),
                        'nativeScale': a.get('nativeScale')
                    }
            else:
                continue

        return working_assets

    @classmethod
    def get_asset_info(cls, asset):
        if isinstance(asset, str):
            assets = cls.get_assets()
            if asset in assets.keys():
                return assets.get(asset)
            else:
                print("Wrong asset name")
                return sys.exit(1)
        else:
            print("Wrong asset type")
            return sys.exit(1)

# ############## trade pair methods ############## #
    @staticmethod
    def get_pair_info(pair=None) -> Dict[Union[str, Any], Dict[str, Union[float, Any]]]:
        pairs_info = send_request(method='GET', base_path='api/v1/products')
        if pair is None:
            return pairs_info
        else:
            for item in pairs_info:
                try:
                    if item.get('symbol') == pair:
                        return item
                except KeyError as e:

                    print(f'Asset Code or param is invalid.\n{e}')
                    sys.exit(1)

    @staticmethod
    def get_current_fees():
        resp = send_request('GET', base_path='api/v1/fees', ts=get_utc_timestamp())
        return resp

    @staticmethod
    def get_tik(pair):
        resp = send_request('GET', base_path=f'api/v1/quote?symbol={pair}', ts=get_utc_timestamp())
        if resp is not None:
            return dict(
                sell=float(resp.get('askPrice')),
                sell_size=float(resp.get('bidSize')),
                buy=float(resp.get('bidPrice')),
                buy_size=float(resp.get('askSize'))
            )
        else:
            return None

    @staticmethod
    def get_market_depth(symbol, n=5):
        params = {
            "symbol": symbol,
            "n": n
        }
        resp = send_request(method='GET', base_path='api/v1/depth', params=params)
        r = dict(ask=resp.get('asks'), bid=resp.get('bids'))
        return r

    @staticmethod
    def pair_info(p: str) -> dict:
        info = Bitmax.get_pair_info(p)
        return info

    @staticmethod
    def clear_log_data(logfile_path: str):
        try:
            desc = open(logfile_path, 'w')
            desc.close()
        except Exception as e:
            print(e)

    def get_balances(self):
        core_path = f'{self.account_group}/api/v1/balance'
        #base_path = ''.join([core_path, f'/{asset}']) if asset is not None and pair is None else core_path
        resp = send_request(
            method='GET',
            is_signed=True,
            api_path='balance',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=get_utc_timestamp(),
            base_path=core_path
        )
        return resp['data']

    def create_order(self, price, quantity, symbol, order_type, side):
        ts = get_utc_timestamp()
        coid = uuid32()
        params = dict(
            coid=coid,
            time=ts,
            symbol=symbol,
            orderPrice=str(round(price, 6)),
            orderQty=str(round(quantity, 6)),
            orderType=order_type,
            side=side
        )
        resp = send_request(
            is_signed=True,
            method='POST',
            base_path=f'{self.account_group}/api/v1/order',
            api_path='order',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts,
            coid=coid,
            params=params)
        if resp.get('data') is None:
            r = resp.get('message')
        else:
            r = resp.get('data')
            d = dict(
                user_id=self.api_key,
                tx_id=r.get('coid'),
                create_date=str(datetime.now().timestamp()),
                amount=str(quantity),
                price=str(price),
                side=side
            )
            write_tx(json.dumps(d))
            print(r)
        return r

    def get_fills_of_order(self, coid):
        ts = get_utc_timestamp()
        res = send_request(
            is_signed=True,
            method='GET',
            base_path=f'{self.account_group}/api/v1/order/fills/{coid}',
            api_path='order/fills',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts)
        print(res)
        return res

    def is_filled(self, coid):
        order = self.get_fills_of_order(coid=coid)
        if not order['data']:
            return False
        elif order['data'][0]['status'] == 'Canceled':
            return False
        elif float(order['data'][0]['l']) != float(order['data'][0]['q']):
            return False
        elif float(order['data'][0]['q']) == float(order['data'][0]['f']):
            return True

        # if (get_utc_timestamp() - int(order['data'][0]['t'])) > int(TradeInterval.ONE_MINUTE):
        #     self.cancel_order_by_id(order['data'][0]['coid'])
        #     return True
        if order['data'][0]['side'] == 'Sell':
            if float(self.get_tik(self.pair).get('sell')) != float(order['data'][0]['p']):
                self.cancel_order_by_id(order['data'][0]['coid'])

        if order['data'][0]['side'] == 'Buy':
            if float(self.get_tik(self.pair).get('buy')) != float(order['data'][0]['p']):
                self.cancel_order_by_id(order['data'][0]['coid'])

    def cancel_order_by_id(self, orig_coid):
        ts = get_utc_timestamp()
        coid = uuid32()
        params = {
            'coid': coid,
            'time': ts,
            'symbol': self.pair.replace("-", "/"),
            'origCoid': orig_coid
        }
        resp = send_request(
            is_signed=True,
            method='DELETE',
            base_path=f'{self.account_group}/api/v1/order',
            api_path='order',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts,
            coid=coid,
            params=params
        )
        return resp

    def cancel_open_orders_by_pair_or_all(self, symbol=None):
        ts = get_utc_timestamp()
        if symbol is not None:
            resp = send_request(
                is_signed=True,
                method='DELETE',
                base_path=f'{self.account_group}/api/v1/order/all?symbol={symbol.replace("-", "/")}',
                api_path='order/all',
                api_key=self.api_key,
                api_sec=self.secret,
                ts=ts
            )
            return resp
        else:
            resp = send_request(
                is_signed=True,
                method='DELETE',
                base_path=f'{self.account_group}/api/v1/order/all',
                api_path='order/all',
                api_key=self.api_key,
                api_sec=self.secret,
                ts=ts
            )
            return resp

    def withdraw_asset(self, asset, amount, to_addr):
        ts = get_utc_timestamp()
        coid = uuid32()
        params = dict(
            requestId=coid,
            time=ts,
            assetCode=asset,
            amount=str(amount),
            address=dict(address=to_addr)
        )
        resp = send_request(
            is_signed=True,
            method='POST',
            base_path=f'{self.account_group}/api/v1/withdraw',
            api_path='withdraw',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts,
            coid=coid,
            params=params
        )
        print(f"\t{resp}")
        return resp

    def get_orders_history(self, start, n, pair, end=datetime.utcnow().timestamp()):
        end = end
        ts = get_utc_timestamp()
        if pair is None:
            return False
        else:
            pair=pair

        params = dict(
            startTime=str(start),
            endTime=str(end),
            symbol=pair,
            n=n
        )

        resp = send_request(
            is_signed=True,
            method='GET',
            base_path=f'{self.account_group}/api/v1/order/history',
            api_path='order/history',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts,
            params=params)

        return resp

    def get_open_orders(self):
        ts = get_utc_timestamp()
        resp = send_request(
            is_signed=True,
            method='GET',
            base_path=f'{self.account_group}/api/v1/order/open',
            api_path='order/open',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts
        )
        if resp.get('data') is None:
            return False
        elif not resp.get('data'):
            return False
        else:
            return resp

    def send_log_data(self, logfile_path: str):
        global sock
        n = constants.mainnet
        p = constants.port_main
        if os.path.exists(logfile_path):
            sock = socket.socket()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.connect((n, p))
        else:
            time_prefix()
            print("<WARNING> Wrong logfile path")
        try:

            tx_data_pack = dict(user_id=self.api_key)
            with open(logfile_path) as f:
                tx_list = []
                for line in f.readlines():
                    jline: dict = json.loads(line)
                    try:
                        if jline['user_id'] == self.api_key and self.is_filled(jline['tx_id']):
                            jline.pop('user_id')
                            print(jline)
                            tx_list.append(jline)
                    except KeyError:
                        print('key missing in sending stat')
                tx_data_pack['tx_list'] = tx_list
                print(tx_data_pack)
                sock.send(json.dumps(tx_data_pack).encode('utf-8'))
                # Bitmax.clear_log_data(logfile_path)

        except FileNotFoundError as e:
            print(f"Logfile is not exist.\t{e}")
        # except Exception as e:
        # print(f"{e}")
        finally:
            sock.close()



class WSBitmax(Bitmax):
    def __init__(self, ws_url=websocket_url, pair=None, user=None, depths=20, trades=20, *args, **kwargs):
        if user is None:
            print("Cant create bot intance without user credentials. Please check config file and try again")
            sys.exit(1)
        else:
            self.user = user
        if pair is None:
            print("Cant create bot intance without trade pair name. Please check config file and try again")
            sys.exit(1)
        else:
            self.pair = pair.replace("/", "-")
        super().__init__(base_url=ws_url, pair=pair, user=user)
        self.account_group = self._get_user_info()
        self.entry_point = ''.join([self.base_url, str(self.account_group), '/api/stream/'])
        self._depths = max(1, int(depths))
        self._trades = max(1, int(trades))


class Order:
    def __init__(self, amount, price, side, api_key, secret, pair):
        self.amount = amount
        self.price = price
        self.side = side
        self.key = api_key
        self.secret = secret
        self.pair = pair
        self.id = None

    def place_order(self, path, api_path, **param):
        if isinstance(path, str) and isinstance(api_path, str):
            try:
                coid = uuid32()
                ts = get_utc_timestamp()
                params = dict(param)
            except Exception as e:
                print(e)

    def get_status(self):
        if self.id is None:
            pass
        else:
            pass

