# -*- coding: utf-8 -*-
import sys
import time
from decimal import Decimal

# from apscheduler.schedulers.background import BackgroundScheduler
# from apscheduler.triggers.interval import IntervalTrigger
# from datetime import datetime
from bot_utils import send_request, get_utc_timestamp, time_now, get_config, TCPClient, Log, uuid32
from constants import PBProtocol as PB
from constants import Role, AppMode
from req_counter import ReqCounter

logger = Log('core_')
ReqCounter.flush()
dec = Decimal()


class Bot:
    def __init__(self, settings: dict):
        AppMode.set_app_status(AppMode.RELEASE)
        if 'role' in settings.keys():
            if settings.get('role') == 'mine':
                self.role = Role.MINER
            else:
                self.role = Role.REVERSER
        self.https_entry_point = 'https://bitmax.io'
        self.websocket_entry_point = 'ws://bitmax.io'
        self.public = settings['public_key']
        self.secret = settings['private_key']
        self.pair = settings['pair'] if 'pair' in settings.keys() else sys.exit('wrong pair format')
        self.spread = settings['spread']
        # self.btmx_limit = settings['btmx_limit']
        self.mining_limit = settings['mining_limit']
        self.name = '...'.join([self.public[:4], self.public[-4:]])
        self.left, self.right = self.pair.split('/')
        self.account_group = self.account_group()
        self.statsrv_addr = (AppMode.mainnet, AppMode.port_main)
        self.tcp_client = TCPClient(server_address=self.statsrv_addr)

        self.starting_left = 0.0
        self.starting_right = 0.0
        self.starting_btmx = 0.0
        self.starting_btc = 0.0
        self.prev_price = 0.0
        self.max_amount = 0.0
        self.min_amount = 0.0
        # self.reverse_mining = False
        # self.mining = False
        self.step = 0.0
        self.price_scale = 0
        self.loop_state = 'ok'

    def _user_info(self):
        ReqCounter.add()
        resp = send_request(
            is_signed=True,
            method='GET',
            base_path='api/v1/user/info',
            api_path='user/info',
            api_key=self.public,
            api_sec=self.secret,
            ts=get_utc_timestamp()
        )
        return resp

    def account_group(self):
        ag = self._user_info()
        if 'accountGroup' in ag.keys():
            return ag.get('accountGroup')
        else:
            msg = f"{time_now()} Initialization Error \n{ag}"
            raise Exception(msg)

    def trade(self):
        tik = self.tik()
        bal = self.get_pair_balance()
        l_bal = bal.get(self.left)
        r_bal = bal.get(self.right)
        if tik['delta_step'] <= self.step:
            if self.role == Role.MINER:
                if float(bal.get('in_btc')) > self.starting_btc * 0.8:
                    print(f'{time_now()} now: {float(bal.get("in_btc"))}')
                    print(f'{time_now()} off {self.starting_btc * 0.8}')
                    if l_bal >= r_bal:
                        side = 'sell'
                        amount = bal[self.left]
                        price = tik['bid']
                        print(self.create_order(price=price, qty=amount, side=side, symbol=self.pair))
                    else:
                        side = 'buy'
                        amount = bal[self.right]
                        price = tik['ask']
                        print(self.create_order(price=price, qty=amount, side=side, symbol=self.pair))
                else:
                    self.role = Role.REVERSER
            elif self.role == Role.REVERSER:
                my_token = self.get_pair_balance(asset='BTMX')
                if my_token['BTMX'] < 1:
                    self.role = Role.MINER
                if l_bal >= r_bal:
                    side = 'sell'
                    amount = bal[self.left]
                    price = tik['ask']
                    self.create_order(price=price, qty=amount, side=side, symbol=self.pair)
                else:
                    side = 'buy'
                    amount = bal[self.right]
                    price = tik['bid']
                    self.create_order(price=price, qty=amount, side=side, symbol=self.pair)

    def setup_pair(self):
        ReqCounter.add()
        for data in send_request(method='GET', base_path='api/v1/products'):
            if isinstance(data, dict):
                if \
                        data.get('status') == 'Normal' and \
                        data.get('miningStatus') == 'Mining,ReverseMining' and \
                        data.get('symbol') == self.pair:
                    self.max_amount = float(data['maxNotional'])
                    self.min_amount = float(data['minNotional'])
                    self.price_scale = int(data['priceScale'])
                    self.step = float(data['minQty']) * 10.0 ** self.price_scale
                    return data
                else:

                    continue

    def is_my_pair_asset(self, a):
        if isinstance(a, str) and (a == self.left or a == self.right or a == 'BTMX'):
            return True
        else:
            return False

    def get_pair_balance(self, asset=None):
        suffix = f'/{asset}' if asset else ''
        core_path = f'{self.account_group}/api/v1/balance' + suffix
        resp = send_request(
            method='GET',
            is_signed=True,
            api_path='balance',
            api_key=self.public,
            api_sec=self.secret,
            ts=get_utc_timestamp(),
            base_path=core_path
        )
        ReqCounter.add()
        if 'data' in resp.keys():
            if asset is None:
                pair_balance = {}
                btc = 0.0
                for item in resp.get('data'):
                    if 'assetCode' in dict(item).keys() and self.is_my_pair_asset(item.get('assetCode')):
                        # pair_balance['assetCode'] = float(item.get('availableAmount'))
                        pair_balance[item.get('assetCode')] = float(item.get('availableAmount'))
                        btc += float(item.get('btcValue'))
                    elif float(item['availableAmount']) > 0:
                        pair_balance[item.get('assetCode')] = float(item.get('availableAmount'))
                    else:
                        continue
                pair_balance['in_btc'] = btc
                return pair_balance
            else:
                try:
                    item = resp.get('data')
                    return {item.get('assetCode'): float(item.get('availableAmount'))}
                except KeyError as err:
                    logger.error(err)
        else:
            return None

    def tik(self):
        resp = send_request('GET', base_path=f"api/v1/quote?symbol={self.pair}")
        ReqCounter.add()
        return dict(
            bid=float(resp['bidPrice']),
            ask=float(resp['askPrice']),
            bSize=float(resp['bidSize']),
            aSize=float(resp['askSize']),
            delta_clean=float(resp['askPrice']) - float(resp['bidPrice']),
            delta_step=(float(resp['askPrice']) - float(resp['bidPrice'])) / float(self.spread)
        )

    def check_online(self):
        try:
            online = self.tcp_client.send_msg(PB.ONLINE)
            if online == 'True':
                return True
            else:
                self.check_online()
                # return False
        except TypeError as err:
            print(err)
            return False

    def set_loop_state(self, state: str):
        self.loop_state = state

    def create_order(self, price, qty, side, symbol):
        ts = get_utc_timestamp()
        coid = uuid32()
        params = dict(
            coid=coid,
            time=ts,
            symbol=symbol,
            orderPrice=str(price),
            orderQty=str(qty * 0.99),
            orderType='limit',
            side=side
        )
        resp = send_request(
            is_signed=True,
            method='POST',
            base_path=f'{self.account_group}/api/v1/order',
            api_path='order',
            api_key=self.public,
            api_sec=self.secret,
            ts=ts,
            coid=coid,
            params=params)
        ReqCounter.add()
        return resp


def request_limiter(profitbot: Bot):
    if ReqCounter.get_total() >= 30:
        ReqCounter.flush()
        time.sleep(1)
        profitbot.set_loop_state('ok')
    else:
        profitbot.set_loop_state('ok')


def start(profitbot: Bot):
    # countdown(2)
    profitbot.loop_state = 'ok'
    if profitbot.check_online():
        profitbot.setup_pair()
        bal = profitbot.get_pair_balance()
        profitbot.starting_left = bal[profitbot.left]
        profitbot.starting_right = bal[profitbot.right]
        profitbot.starting_btmx = bal['BTMX']
        profitbot.starting_btc = bal['in_btc']

    else:
        logger.info(f'Server offline.')


def loop(profitbot: Bot, endless=True):
    if profitbot.check_online():
        while endless:
            request_limiter(profitbot)
            if profitbot.loop_state == 'pause':
                continue
            elif profitbot.loop_state == 'stop':
                break
            elif profitbot.loop_state == 'ok':
                profitbot.trade()


if __name__ == '__main__':
    config = get_config('config.txt')
    bot = Bot(settings=config)
    sender = TCPClient()
    auth_message = f"{PB.AUTH}{bot.public}"
    if bool(sender.send_msg(PB.ONLINE)):
        print(f'{time_now()} Server online')
        if sender.send_msg(auth_message):
            print(f'{time_now()} Key: {bot.public} authorized')
            start(profitbot=bot)
            loop(profitbot=bot)
        else:
            print(f'{time_now()} Key: {bot.public} authorization has failed')
            sys.exit(1)
