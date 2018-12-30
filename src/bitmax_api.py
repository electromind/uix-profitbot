# -*- coding: utf-8 -*-
from typing import Dict, Any, Union
import sys
from utils import send_request, utc_timestamp, print_logtime, uuid32
from datetime import datetime


class Bitmax:

    def __init__(self, user=None, base_url='https://bitmax.io/'):
        if user:
            try:
                self.email = user.get('login')
                self.base_url = base_url
                self.api_key = user.get('api')
                self.secret = user.get('secret')
                self.id = user.get('id')
                self.account_group = self._get_user_info()
                self.lastSellPrice = 0.0
                self.lastBuyPrice = 0.0
                self.is_maker = False
                #print(f"\t{user.get('login')} created")
            except AttributeError as err:
                print(f"\n{err.args}")
        else:
            raise Exception('Bot init error')

    def _get_user_info(self):
        resp = send_request(
            is_signed=True,
            method='GET',
            base_path='api/v1/user/info',
            api_path='user/info',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=utc_timestamp()
        )
        return resp.get('accountGroup')

############### request asset list or single asset ###############
    @classmethod
    def _request_assets(cls):
        try:
            assets = send_request(method='GET', base_path='api/v1/assets')
            return assets
        except Exception as err:
            print(f'invalid data of requesting asset list.\n{err.args}')
            return sys.exit(1)

    @classmethod
    def get_assets(cls) -> dict:
        working_assets: Dict[Union[str, Any], Dict[str, Union[float, Any]]] = {}
        btmx_assets = cls._request_assets()
        for asset in btmx_assets:
            if asset.get('status') == 'Normal':
                working_assets[asset['assetCode']] = {
                        'id': asset.get('assetCode'),
                        'name': asset.get('assetName'),
                        'step': round(0.1 ** (asset.get('nativeScale')), int(asset.get('nativeScale'))),
                        'nativeScale': asset.get('nativeScale')
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

############### trade pair methods ###############
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
                except KeyError as err:
                    print_logtime()
                    print(f'Asset Code or param is invalid.\n{err.args}')
                    sys.exit(1)

    @staticmethod
    def get_current_fees():
        resp = send_request('GET', base_path='api/v1/fees', ts=utc_timestamp())
        #print(f'\t{resp}')
        return resp

    @staticmethod
    def get_tik(pair):
        resp = send_request('GET', base_path=f'api/v1/quote?symbol={pair}', ts=utc_timestamp())
        tiker = dict(
            buyPrice=float(resp.get('askPrice')),
            buySize=float(resp.get('bidSize')),
            sellPrice=float(resp.get('bidPrice')),
            sellSize=float(resp.get('askSize'))
        )
        return tiker

    @staticmethod
    def get_market_depth(symbol, n=5):
        params = {
            "symbol": symbol,
            "n": n
        }
        resp = send_request(method='GET', base_path='api/v1/depth', params=params)
        r = dict(ask=resp.get('asks'), bid=resp.get('bids'))
        print_logtime()
        print(f"\tConcurent asks: {r.get('ask')}")
        print_logtime()
        print(f"\tConcurent bids: {r.get('bid')}")
        return r

    # def get_amount(self, price):
    #     self.canBuy = self.

    def get_balances(self, asset=None, pair=None):
        core_path = f'{self.account_group}/api/v1/balance'
        base_path = ''.join([core_path, f'/{asset}']) if asset is not None and pair is None else core_path
        if pair and asset is None:
            data = {}
            for asset in pair.split('/'):
                base_path = ''.join([core_path, f'/{asset}'])
                tmp = self.get_balances(asset=asset, pair=None)
                data[asset] = tmp[asset]
            return data
        resp = send_request(
            method='GET',
            is_signed=True,
            api_path='balance',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=utc_timestamp(),
            base_path=base_path
        )

        tmp = dict()
        tmp[str(resp['data']['assetCode'])] = float(resp['data']['availableAmount'])
        self.__setattr__(resp['data']['assetCode'], tmp[resp['data']['assetCode']])
        return tmp if asset else resp['data']

    def create_order(self, price, quantity, symbol, order_type, side):
        ts = utc_timestamp()
        coid = uuid32()
        params = dict(
            coid=coid,
            time=ts,
            symbol=symbol,
            orderPrice=str(price),
            orderQty=str(quantity),
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
        r = resp.get('data')
        print(r)
        return r

    def get_fills_of_order(self, coid):
        ts = utc_timestamp()
        res = send_request(
            is_signed=True,
            method='GET',
            base_path=f'{self.account_group}/api/v1/order/fills/{coid}',
            api_path='order/fills',
            api_key=self.api_key,
            api_sec=self.secret,
            ts=ts)
        return res

    def is_filled(self, coid):
        order = self.get_fills_of_order(coid=coid)
        if order['data'] is None:
            return False
        if float(order['data'][0]['l']) < float(order['data'][0]['q']):
            return False
        else:
            return True

    def cancel_order_by_id(self, orig_coid, pair):
        ts = utc_timestamp()
        coid = uuid32()
        params = {
            'coid': coid,
            'time': ts,
            'symbol': pair.replace("-", "/"),
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
        ts = utc_timestamp()
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
        ts = utc_timestamp()
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
        ts = utc_timestamp()
        if pair is None:
            return False
        else:
            pair=pair

        params = dict(
            startTime=start,
            endTime=end,
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
        return resp['data']

