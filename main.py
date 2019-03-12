# -*- coding: utf-8 -*-

from bot_utils import \
    send_request, get_utc_timestamp, get_logger, time_now, \
    get_config, countdown, LazyConnection, recvall, send_msg
from constants import Role, AppMode


class Bot:
    def __init__(self, settings):
        self.https_entry_point = 'https://bitmax.io'
        self.websocket_entry_point = 'ws://bitmax.io'
        self.public = settings['public_key']
        self.secret = settings['private_key']
        self.pair = settings['pair']
        self.spread = settings['spread']
        self.btmx_limit = settings['btmx_limit']
        self.mining_limit = settings['mining_limit']
        self.role = Role.MINER
        self.name = '...'.join([self.public[:4], self.public[-4:]])
        self.left, self.right = self.pair.split('/')
        self.account_group = self.set_account_group()
        self.pb_cmd = None


    def set_account_group(self):
        ag = self.get_user_info()
        if 'accountGroup' in ag.keys():
            return ag.get('account_group')
        else:
            msg = f"{time_now()[:-15]} Initialization Error"
            raise Exception(msg)

    def get_user_info(self):
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

    def get_pairs_info(self):
        return send_request(method='GET', base_path='api/v1/products')

    def get_assets_balance(self):
        core_path = f'{self.account_group}/api/v1/balance'
        resp = send_request(
            method='GET',
            is_signed=True,
            api_path='balance',
            api_key=self.public,
            api_sec=self.secret,
            ts=get_utc_timestamp(),
            base_path=core_path
        )
        return resp

    def do_system_request(self, conn, data=None):
        with conn as c:
            if isinstance(data, str):
                send_msg(c, data.encode('utf-8'))
                raw_resp = recvall(c, 512)
                if not raw_resp:
                    return None
                else:
                    return str(raw_resp, encoding='utf-8')

    def update(self, connection, service_msg=None, ping_msg=None):
        resp = dict()
        if not service_msg and not ping_msg:
            return False
        if service_msg:
            resp['service'] = self.do_system_request(connection, data=service_msg)
        else:
            resp['service'] = None

        if ping_msg:
            resp['ping'] = self.do_system_request(connection, data=ping_msg)
        else:
            resp['ping'] = None
        return resp


if __name__ == '__main__':

    conn = LazyConnection(address=AppMode.setup_transport())
    config = get_config('config.txt')
    bot = Bot(settings=config)

    loggr = bot.get_logger()
    auth_message = f"auth_me:{bot.public}"
    print(str(bot.update(connection=conn, service_msg=auth_message)))
    print(f'{time_now()} Bot initialization complete successful.\n{time_now()} {bot.__sizeof__()} bytes\n{time_now()} name: {bot.public}')

    print(f'{time_now()} {countdown(1)}\n')
    pair_list = bot.get_pairs_info()
    print(pair_list)
    print(bot.get_assets_balance())
    print(bot.get_user_info())
