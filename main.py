# -*- coding: utf-8 -*-
import random
import sys
from datetime import datetime
from time import sleep

import constants
from bitmax_api import Bitmax
from bot_utils import get_logger, time_prefix, read_config, tx_cross_side

actual = dict()
log_dir_path = 'log/'
logfile_name = 'main.log'
logfile_path = ''.join([log_dir_path, logfile_name])
ltx_logger = get_logger('tx')
# if not os.path.exists(logfile_path):
#     os.mkdir(log_dir_path)
# elif not os.path.isfile(logfile_path):
#     f = open(logfile_name, 'a')
#     f.close()
takt = {}


def app_setup(config: dict):
    app_conf = config
    time_prefix()
    print('Reading app settings from config.json ...')
    try:
        app_config = app_conf.get('app')
        actual['pair'] = app_config.get('pair')
        actual['left'], actual['right'] = actual.get('pair').split('/')
        actual['step'] = Bitmax.get_asset_info(actual.get('left')).get('step') / 10.0
        actual['risk'] = int(app_config.get('price_tolerance'))
        actual['pricing_method'] = app_config['pricing_method']
        fees = Bitmax.get_current_fees()
        actual['rev_fee'] = float(fees.get('maker').get('rebate'))
        actual['mining_fee'] = float(fees.get('taker').get('mining'))
        actual['tx_size'] = float(app_config.get('tx_size')) if float(app_config.get('tx_size')) > 0.0 else 1.0
        actual['last_price_m'] = 0.0
    except KeyError as e:
        ltx_logger.error(f"Invalid key. Check config file: {e}")
        sys.exit(1)
    except Exception as e:
        ltx_logger.error(f'App setup error: {e}')
        sys.exit(1)
    else:
        pass


def tradepair_setup(pair):
    if isinstance(pair, str):
        tmp = Bitmax.pair_info(pair)
        actual['minTx'] = float(tmp.get('minQty'))
        actual['maxTx'] = float(tmp.get('maxQty'))
        if tmp.get('miningStatus') == 'Mining,ReverseMining' or 'ReverseMining':
            actual['mining'] = True
            actual['reverse'] = True
        elif tmp.get('miningStatus') == 'Mining':
            actual['reverse'] = False
            actual['mining'] = True


def print_current_settings():
    for key, value in actual.items():
        time_prefix()
        if type(value) is float:
            print(f"{key}: {value:.6f}")
        else:
            print(f'{key}: {value}')


def tik():
    actual_tik = Bitmax.get_tik(actual.get('pair'))
    takt['sell'] = actual_tik.get('sell')
    takt['buy'] = actual_tik.get('buy')
    takt['buy_size'] = actual_tik.get('buy_size')
    takt['sell_size'] = actual_tik.get('sell_size')
    takt['delta'] = round((takt['sell'] - takt['buy']) / actual.get('step'), 6)
    takt['middle'] = round((actual_tik.get('buy') + actual_tik.get('sell')) / 2.0, 6)
    return takt


def get_bot_balance(bot: Bitmax, pair=None):
    b = bot.get_balances()
    if pair is None:
        return b
    else:
        resp = {}
        if isinstance(pair, str):
            left, right = pair.split('/')
            for item in b:
                if item.get('assetCode') == left:
                    resp[left] = float(item.get('availableAmount'))
                elif item.get('assetCode') == right:
                    resp[right] = float(item.get('availableAmount'))
                else:
                    continue
        return resp


def create_order(bot: Bitmax, price: float, side: str, amount: float):
    result = bot.create_order(
        order_type='limit',
        price=price,
        quantity=amount,
        side=side,
        symbol=actual.get('pair')
    )
    ltx_logger.info(result)
    return result


def is_filled(bot: Bitmax, txid):
    if txid is None:
        return False
    else:
        while True:
            if bot.is_filled(txid):
                return True
            else:
                time_prefix()
                print(f"{txid} not filled yet")
                sleep(1)
                continue


def base_to_queue(bal_dic: dict, price2updte):
    for k, v in bal_dic.items():
        if str(k) == actual.get('right'):
            tmp = v / price2updte
            bal_dic.update({k: tmp})
            return bal_dic


def save_to_log(response_data: dict, price: float, amount: float):
    # user_id (foregin_key)
    # tx_id (str)
    # status (str)
    # side (str)
    # amount (float)
    # price (float)
    # fee (float)
    # mined	(float)
    # reversed (float)
    # create_date (timestamp)
    log = dict(
        #
        #user_id=b1.,
        tx_id=response_data.get('coid'),
        create_date=datetime.utcnow().timestamp(),
        price=price,
        amount=amount,
        status='success'
    )


def clear(b1: Bitmax, b2: Bitmax):
    b1.cancel_open_orders_by_pair_or_all()
    b2.cancel_open_orders_by_pair_or_all()


'''
def send_trx(bot: Bitmax, logfile="hourly_stat.log"):
    tx_list = read_log_data(filename='log/tx.log')
    data = '{"user_id": "' + bot.id + '", "tx_list": [' + ','.join(tx_list) + ']}'
    if send_log_data(stat_data=data):
        clear_log_data(logfile)
        time_prefix()
        print("Statistic saved")
    else:
        time_prefix()
        print("Error saving statistc")
'''


def auth_start():
    conf = read_config()
    app_setup(conf)
    tradepair_setup(pair=actual.get('pair'))
    print_current_settings()
    b1 = Bitmax(conf.get('referals')[0], pair=actual.get('pair'))
    b2 = Bitmax(conf.get('referals')[1], pair=actual.get('pair'))
    # scheduler = BackgroundScheduler(daemon=True)
    # scheduler.add_job(lambda: clear(b1, b2), 'interval', minutes=5)
    # scheduler.start()
    if b1.auth() and b2.auth():
        clear(b1, b2)
        return b1, b2
    else:
        return False


def get_balance_list(b1: Bitmax, b2: Bitmax):
    balance_b1 = get_bot_balance(bot=b1, pair=actual.get('pair'))
    balance_b2 = get_bot_balance(bot=b2, pair=actual.get('pair'))
    return [balance_b1, balance_b2]


def dep_equalizer(pair_balance: dict, owner: Bitmax, fast=False, check_is_filled=False):
    left_depo = float(pair_balance.get(actual.get('left')))
    right_depo = float(pair_balance.get(actual.get('right')))
    delta = round(left_depo - right_depo, 6)
    t = owner.get_tik(actual.get('pair'))
    global tx
    if delta >= 0:
        am = (left_depo - right_depo) / 2.0
        if am <= actual['minTx']:
            return False
        else:
            try:
                price = round(t.get('sell'), 6)
                tx = create_order(owner, price=price, amount=round(am, 6), side='sell' if not fast else 'buy')
                ltx_logger.info(tx)
            except Exception:
                time_prefix()
                print(f"Equalizer fail to create order when {actual.get('left')} > {actual.get('right')}")
            if check_is_filled and tx['coid']:
                if is_filled(bot=owner, txid=tx['coid']):
                    return True
                else:
                    return False

    elif delta < 0:

        am = (right_depo - left_depo) / 2.0
        if am < actual['minTx']:
            return False
        else:
            try:
                price = round(t.get('buy'), 6)
                tx = create_order(owner, price=price, amount=round(am, 6), side='buy' if not fast else 'sell')
                ltx_logger.info(tx)
            except Exception:
                ltx_logger.error(f"Equalizer fail to create order when {actual.get('right')} > {actual.get('left')}")
            if check_is_filled and tx['coid']:
                if is_filled(bot=owner, txid=tx['coid']):
                    return True
                else:
                    return False


def equalize_funds(funds: list, bot1, bot2, fast=False):
    dep_equalizer(funds[0], bot1, fast=fast)
    dep_equalizer(funds[1], bot2, fast=fast)


def mine(bot1: Bitmax, bot2: Bitmax, bot_funds: list):
    r_side = random.choice(['sell', 'buy'])
    unit = 'left' if r_side == 'sell' else 'right'
    # c_unit = 'left' if unit == 'right' else 'right'
    #r_side = 'buy'
    #unit = 'right'
    # c_unit = 'left'
    rand = random.randint(1, 100) % 2
    if rand == 0:
        maker = [bot1, bot_funds[0]]
        taker = [bot2, bot_funds[1]]
    else:
        maker = [bot2, bot_funds[1]]
        taker = [bot1, bot_funds[0]]
    tik_now = tik()
    price = round(tik_now.get('middle'), 6)
    am_maker_base = ((taker[1].get(actual.get(unit))) * price) * actual.get('tx_size')
    am_maker = round(am_maker_base - (am_maker_base * actual.get('mining_fee')), 6)
    # am_taker = taker[1].get(actual.get(c_unit)) * actual.get('mining_fee')
    am_taker = am_maker
    if price != actual['last_price_m']:
        actual['last_price_m'] = price
        bot1.cancel_open_orders_by_pair_or_all()
        bot2.cancel_open_orders_by_pair_or_all()
    if tik_now.get('delta') <= 3.0 and am_maker > actual.get('minTx') and am_taker > actual.get('minTx'):
        rev_tx = create_order(bot=maker[0], price=price, amount=am_maker, side=r_side)
        mine_tx = create_order(bot=taker[0], price=price, amount=am_taker, side=tx_cross_side(r_side))
        ltx_logger.info(rev_tx)
        ltx_logger.info(mine_tx)
    elif tik_now.get('delta') >= 3:
        bot1.cancel_open_orders_by_pair_or_all()
        bot2.cancel_open_orders_by_pair_or_all()
        time_prefix()
        print(f"Delta: {tik_now.get('delta')} - too risky, waiting...")


def check_my_orders(bot1: Bitmax, bot2: Bitmax, lp_middle):
    t = tik()
    if lp_middle == 0.0:
        actual['last_price_m'] = t.get('middle')
    if t.get('middle') != lp_middle:
        bot1.cancel_open_orders_by_pair_or_all()
        bot2.cancel_open_orders_by_pair_or_all()
        actual['last_price_m'] = t.get('middle')


if __name__ == '__main__':
    bot_one, bot_two = auth_start()
    bot_funds = get_balance_list(b1=bot_one, b2=bot_two)
    equalize_funds(bot_funds, bot_one, bot_two, fast=True)

    hist1 = bot_one.get_orders_history(start=int(datetime.utcnow().timestamp()) - int(constants.trade_interval.HOUR[0])*5, n=100, pair=actual.get('pair'))['data']['data']
    hist2 = bot_two.get_orders_history(start=int(datetime.utcnow().timestamp()) - int(constants.trade_interval.HOUR[0])*3, n=100, pair=actual.get('pair'))['data']['data']
    start = datetime.utcnow().timestamp()
    d = constants.trade_interval.HOUR[0]
    # while True:
    #     bot_funds = get_balance_list(b1=bot_one, b2=bot_two)
    #     equalize_funds(bot_funds, bot_one, bot_two, fast=False)
    #     mine(bot1=bot_one, bot2=bot_two, bot_funds=bot_funds)
    #     check_my_orders(bot_one, bot_two, actual['last_price_m'])
    #     #sleep(1)
