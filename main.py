# -*- coding: utf-8 -*-
import sys
from decimal import Decimal
from pprint import pprint

from apscheduler.schedulers.background import BackgroundScheduler as Runner
from apscheduler.triggers.interval import IntervalTrigger

from bot_utils import send_request, get_utc_timestamp, time_now, get_config, TCPClient, Log
from constants import PBProtocol as PB
from constants import Role, AppMode
from req_counter import ReqCounter

logger = Log('core_')
r = ReqCounter()
dec = Decimal()


class Bot:
    def __init__(self, settings: dict):
        AppMode.set_app_status(AppMode.RELEASE)
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
        if 'role' in settings.keys():
            if settings.get('role') == 'mine':
                self.role = Role.MINER
            else:
                self.role = Role.REVERSER
        self.starting_left = dec.from_float(0.0)
        self.starting_right = dec.from_float(0.0)
        self.starting_btmx = dec.from_float(0.0)
        self.prev_price = dec.from_float(0.0)
        self.max_amount = dec.from_float(0.0)
        self.min_amount = dec.from_float(0.0)
        self.reverse_mining = False
        self.mining = False
        self.step = dec.from_float(0.0)
        self.price_scale = 0
        self.loop_state = 'ok'

    def _user_info(self):
        resp = send_request(
            is_signed=True,
            method='GET',
            base_path='api/v1/user/info',
            api_path='user/info',
            api_key=self.public,
            api_sec=self.secret,
            ts=get_utc_timestamp()
        )
        r.add()
        return resp

    def account_group(self):
        ag = self._user_info()
        if 'accountGroup' in ag.keys():
            return ag.get('accountGroup')
        else:
            msg = f"{time_now()} Initialization Error \n{ag}"
            raise Exception(msg)

    def market_state(self):
        resp = send_request('GET', base_path=f"api/v1/quote?symbol={self.pair}")
        print(resp)

    def setup_pair(self):
        r.add()
        for data in send_request(method='GET', base_path='api/v1/products'):
            if isinstance(data, dict):
                if data.get('symbol') == self.pair:
                    self.max_amount = dec.from_float(float(data['maxNotional']))
                    self.min_amount = dec.from_float(float(data['minNotional']))
                    self.price_scale = int(data['priceScale'])
                    self.step = dec.from_float(float(data['minQty']) * 10.0 ** self.price_scale)
                    return data
                else:
                    continue

    def is_pair_asset(self, a):
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
        r.add()
        if 'data' in resp.keys():
            if asset is None:
                pair_balance = {}
                for item in resp.get('data'):

                    if 'assetCode' in dict(item).keys() and self.is_pair_asset(item.get('assetCode')):
                        # pair_balance['assetCode'] = float(item.get('availableAmount'))
                        pair_balance[item.get('assetCode')] = dec.from_float(float(item.get('availableAmount')))
                    elif dec.from_float(float(item['availableAmount'])) > 0:
                        pair_balance[item.get('assetCode')] = dec.from_float(float(item.get('availableAmount')))
                    else:
                        continue
                return pair_balance
            else:
                try:
                    item = resp.get('data')
                    return {item.get('assetCode'): dec.from_float(float(item.get('availableAmount')))}
                except KeyError as err:
                    logger.error(err)
        else:
            return None

    def tik(self):
        resp = send_request('GET', base_path=f"api/v1/quote?symbol={self.pair}")
        return dict(
            bid=dec.from_float(float(resp['bidPrice'])),
            ask=dec.from_float(float(resp['askPrice'])),
            bSize=dec.from_float(float(resp['bidSize'])),
            aSize=dec.from_float(float(resp['askSize'])),
            delta_clean=dec.from_float(float(resp['askPrice']) - float(resp['bidPrice'])),
            delta_step=dec.from_float((float(resp['askPrice']) - float(resp['bidPrice'])) / self.spread)
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

    def request_limiter(self):
        if r.get_total() >= 30:
            self.set_loop_state('pause')
        else:
            self.set_loop_state('ok')

    def set_loop_state(self, state: str):
        self.loop_state = state


def start(profitbot: Bot):
    # countdown(2)
    my_pair_data = profitbot.setup_pair()
    pprint(my_pair_data)
    profitbot.shadow = Runner()
    profitbot.shadow_interval = IntervalTrigger(seconds=1)
    profitbot.shadow.add_job(profitbot.request_limiter, max_instances=1, trigger=profitbot.shadow_interval)

    if profitbot.check_online():
        bal = profitbot.get_pair_balance()
        profitbot.starting_left = bal[profitbot.left]
        profitbot.starting_right = bal[profitbot.right]
        profitbot.starting_btmx = bal['BTMX']
        for k, v in bal.items():
            logger.info(f'{k}: {v:.09f}')
        pprint(profitbot.tik())
    else:
        logger.info(f'Server offline.')


def loop(profitbot: Bot, endless=True):
    global inf
    inf = endless
    while True:
        if profitbot.loop_state == 'ok':
            pprint(profitbot.market_state())

        elif profitbot.loop_state == 'pause':
            continue
        else:
            break
        if profitbot.check_online() and inf:
            pass
        else:
            print(f'{profitbot.setup_pair()}\n{r.get_total()}')


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
