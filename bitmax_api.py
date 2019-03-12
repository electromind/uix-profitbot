# -*- coding: utf-8 -*-
import socket
import sys
from datetime import datetime

import constants as constants
from bot_utils import get_utc_timestamp, send_request, time_prefix, uuid32, write_error_log


class Bitmax:

    def __init__(self, user=None, base_url='https://bitmax.io/', pair=None):
        try:
            if user:
                self.base_url = base_url
                self.api_key = user.get('public_key')
                self.secret = user.get('secret')
                self.id = self.api_key
                self.account_group = self._get_user_info()
                self.my_orders = []
                self.limit_to_send_stat = 10
                self.name = '_'.join(['unit', self.api_key[:4]])
                try:
                    self.btmx_limit = int(user.get('btmx_limit'))
                except Exception as e:
                    write_error_log('limit - required_config_fields option', e)
                    sys.exit('limit - required_config_fields option')
                if pair is not None:
                    self.pair = pair
                else:
                    sys.exit('Invalid Pair or missing')

            else:
                raise AttributeError('user credentials wrong or missing. Please recheck config file and try again')
        except Exception as e:
            write_error_log(f'{self.name} init error', e)

    def auth(self):
        user_id = self.api_key

        if constants.AppMode.get_app_status() == constants.AppMode.DEBUG:
            return True
        else:
            host, port = constants.AppMode.setup_transport()
            with socket.socket() as s2:
                try:
                    s2.settimeout(20)
                    s2.connect(constants.AppMode.setup_transport())
                except ConnectionError as e:
                    print(f"Connection error {e}")
                    s2.close()
                    sys.exit(1)
                auth_string = f"auth_me:{user_id}".encode('utf-8')
                s2.send(auth_string)
                data = s2.recv(4096)
                resp = str(data, encoding='utf-8')
                if resp == 'True':
                    time_prefix()
                    print(f'{self.name}\tauthorized.')
                    s2.close()
                    return True
                else:
                    time_prefix()
                    print('Invalid Key. Please recheck config file.')
                    s2.close()
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
        return resp

    @classmethod
    def get_all_assets(cls):
        return send_request(method='GET', base_path='api/v1/assets')

    @staticmethod
    def get_pairs_info():
        return send_request(method='GET', base_path='api/v1/products')

    @staticmethod
    def get_current_fees():
        return send_request('GET', base_path='api/v1/fees')

    @staticmethod
    def get_tik(pair):
        return send_request('GET', base_path=f"api/v1/quote?symbol={pair}")

    def get_market_depth(self, depth=5):
        params = {
            "symbol": self.pair.replace('/', '-'),
            "n": depth
        }
        resp = send_request(method='GET', base_path='api/v1/depth', params=params)
        return resp

    def get_assets_balance(self, asset):
        core_path = f'{self.account_group}/api/v1/balance'
        resp = send_request(
            method='GET',
            is_signed=True,
            api_path='balance',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=get_utc_timestamp(),
            base_path=core_path
        )
        return resp

    def create_order(self, price, qty, side, symbol, order_type='limit'):
        ts = get_utc_timestamp()
        coid = uuid32()
        params = dict(
            coid=coid,
            time=ts,
            symbol=symbol,
            orderPrice=price,
            orderQty=qty,
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
        return resp

    def get_filled_ordes_list(self, coid: str):
        ts = get_utc_timestamp()
        resp = send_request(
            is_signed=True,
            method='GET',
            base_path=f'{self.account_group}/api/v1/order/fills/{coid}',
            api_path='order/fills',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts)
        if resp['status'] == 'success':
            return resp['data']
        else:
            msg = f"Error get_filled_details()"
            raise Exception([msg, resp])

    def get_filled_order_data(self, coid: str):
        ts = get_utc_timestamp()
        resp = send_request(
            is_signed=True,
            method='GET',
            base_path=f'{self.account_group}/api/v1/order/{coid}',
            api_path='order',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts)
        return resp

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
        if resp['data']:
            return resp['data']
        else:
            msg = f"Error cancel_order_by_id({orig_coid}). With params: {params}"
            raise Exception([msg, resp])

    def cancel_open_orders_by_pair_or_all(self):
        ts = get_utc_timestamp()
        resp = send_request(
            is_signed=True,
            method='DELETE',
            base_path=f'{self.account_group}/api/v1/order/all?symbol={self.pair.replace("-", "/")}',
            api_path='order/all',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts
        )
        return resp

    def cancel_all_open_orders(self):
        ts = get_utc_timestamp()
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
        return resp

    def get_orders_history(self, start_in_min=5, n=50, end=datetime.now().timestamp()):
        ts = get_utc_timestamp()
        one_minute = constants.TradeInterval.ONE_MINUTE
        params = dict(
            startTime=str(end - one_minute * start_in_min),
            endTime=str(end),
            symbol=self.pair,
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
        return resp
