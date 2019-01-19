# -*- coding: utf-8 -*-
import random
import sys
from datetime import datetime
from time import sleep

from apscheduler.schedulers.background import BackgroundScheduler

from src.bitmax_api import Bitmax
from src.bot_utils import get_logger, time_prefix, read_config, tx_cross_side, create_list, clear_log, send_stat
from src.constants import pricing_methods

actual = dict()
takt = {}
logger = get_logger(''.join(['main', time_prefix()]))
last_price_buy = 0
last_price_sell = 0
last_price_middle = 0

def app_setup(config: dict):
    app_conf = config
    # trademining setting up
    try:
        time_prefix()
        print('Reading app settings from config.json ...')
        app_config = app_conf.get('app')
        actual['pair'] = app_config.get('pair')
        actual['left'], actual['right'] = actual.get('pair').split('/')
        actual['step'] = Bitmax.get_asset_info(actual.get('left')).get('step')
        actual['risk'] = int(app_config.get('price_tolerance'))
        actual['pricing_method'] = app_config['pricing_method']
        fees = Bitmax.get_current_fees()
        actual['rev_fee'] = float(fees.get('maker').get('rebate'))
        actual['mining_fee'] = float(fees.get('taker').get('mining'))
        actual['tx_size'] = (float(app_config.get('tx_size')) if float(app_config.get('tx_size')) > 0 else 1.0)
    except KeyError as e:
        print(f"Invalid key. Check config file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"app_setup: {e}")
        sys.exit(1)


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
            print(f'{key}: {value:.8f}')
        else:
            print(f'{key}: {value}')


def tik():
    actual_tik = Bitmax.get_tik(actual.get('pair'))
    takt['sell'] = actual_tik.get('sell')
    takt['buy'] = actual_tik.get('buy')
    takt['buy_size'] = actual_tik.get('buy_size')
    takt['sell_size'] = actual_tik.get('sell_size')
    takt['delta'] = int((takt['sell'] - takt['buy']) / actual.get('step'))
    takt['middle'] = round((actual_tik.get('buy') + actual_tik.get('sell')) / 2.0, 6)
    return takt


def is_safe_price(price: float, side):
    curr_p = tik()
    if curr_p.get(side) == price:
        return True
    else:
        return False


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
    #print(result)
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
                print(f"in is_filled >>>>> {bot.is_filled(txid)}")
                sleep(1)
                continue


def base_to_queue(bal_dic: dict, price2updte):
    for k, v in bal_dic.items():
        if str(k) == actual.get('right'):
            tmp = v / price2updte
            bal_dic.update({k: tmp})
            return bal_dic


def save_to_log(starttime, response_data: dict, price: float, amount: float):
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
        # user_id=b1.id,
        tx_id=response_data.get('coid'),
        create_date=datetime.utcnow().timestamp(),
        price=price,
        amount=amount,
        status='success'
    )


def clear(b1: Bitmax, b2: Bitmax):
    b1.cancel_open_orders_by_pair_or_all()
    b2.cancel_open_orders_by_pair_or_all()


def find_maker(b1: Bitmax, b2: Bitmax, bal1, bal2, price):

    '''
    max_b1 = max(zip(bal1.values(), bal1.keys()))
    max_b2 = max(zip(bal2.values(), bal2.keys()))
    time_prefix()
    print(max_b1)
    time_prefix()
    print(max_b2)
    tx_data = dict()
    if max_b1[1] == max_b2[1] == actual.get('right'):
        if max_b1[0] >= max_b2[0]:
            if (max_b1[0] / max_b2[1]) * 100 > 1.25:
                tmp = max_b1[0] - max_b2[1]
                create_order(max_b1, 0.5, 'sell', 0.9)
        else:
            pass
            tx_data['maker'] = b2
            tx_data['taker'] = None
            tx_data['bal'] = bal2.get(actual.get('right'))
            tx_data['maker_side'] = 'buy'
            tx_data['type'] = 'single'
        else:
            tx_data['maker'] = b1
            tx_data['taker'] = None
            tx_data['bal'] = bal1.get(actual.get('right'))
            tx_data['maker_side'] = 'buy'
            tx_data['type'] = 'single'
    if max_b1[1] == max_b2[1] == actual.get('left'):
        if max_b1[0] >= max_b2[0]:
            tx_data['maker'] = b2
            tx_data['taker'] = b1
            tx_data['bal'] = bal2.get(actual.get('left'))
            tx_data['maker_side'] = 'sell'
            tx_data['type'] = 'single'
        else:
            tx_data['maker'] = b1
            tx_data['taker'] = b2
            tx_data['bal'] = bal1.get(actual.get('left'))
            tx_data['maker_side'] = 'sell'
            tx_data['type'] = 'single'
    if max_b2[1] != max_b1[1] == actual.get('right'):
        if max_b1[0] >= max_b2[0]:
            tx_data['maker'] = b2
            tx_data['taker'] = b1
            tx_data['bal'] = bal2.get(actual.get('left'))
            tx_data['maker_side'] = 'sell'
            tx_data['type'] = 'double'
        else:
            tx_data['maker'] = b1
            tx_data['taker'] = b2
            tx_data['bal'] = bal1.get(actual.get('left'))
            tx_data['maker_side'] = 'sell'
            tx_data['type'] = 'double'
        if max_b1[0] < max_b2[0]:
            if max_b1[1] == actual.get('left'):
                tx_data['maker'] = b1
                tx_data['taker'] = b2
                tx_data['bal'] = bal1.get(actual.get('left'))
                tx_data['maker_side'] = 'sell'
                tx_data['type'] = 'double'
            else:
                tx_data['maker'] = b2
                tx_data['taker'] = b1
                tx_data['bal'] = bal2.get(actual.get('left'))
                tx_data['maker_side'] = 'sell'
                tx_data['type'] = 'double'

    time_prefix()
    print(tx_data)
    return tx_data
'''


def pair_tx(maker: Bitmax, taker: Bitmax, bal: float, type: str, side: str):
    pr = tik().get(side)

    if type == 'single':
        tx = create_order(bot=maker, price=pr, side=side, amount=bal)
        return tx
    elif type == 'double':
        maker_txid = create_order(bot=maker, price=pr, side=side, amount=bal * 0.99)
        taker_txid = create_order(bot=taker, price=pr, side=tx_cross_side(side), amount=bal / (1 + actual.get('step') + actual.get('mining_fee')))
        return [maker_txid, taker_txid]


def send_trx(bot: Bitmax, logfile="hourly_stat.log"):
    tx_list = create_list()
    data = '{"user_id": "' + bot.id + '", "tx_list": [' + ','.join(tx_list) + ']}'
    if send_stat(stat_data=data):
        clear_log(logfile)
        time_prefix()
        print("Stat was successfully sended")
    else:
        time_prefix()
        print("Sending statistc error")


def get_price(method=pricing_methods.CENTER):
    t_tik = tik()
    if method == pricing_methods.ASK:
        return t_tik.get('sell')
    elif method == pricing_methods.BID:
        return t_tik.get('buy')
    elif method == pricing_methods.ASKplus:
        return t_tik.get('sell') - actual.get('step')
    elif method == pricing_methods.BIDplus:
        return t_tik.get('buy') + actual.get('step')
    else:
        return round(((t_tik.get('buy') + t_tik.get('sell')) / 2.0), 8)


def auth_start():
    conf = read_config()
    app_setup(conf)
    tradepair_setup(pair=actual.get('pair'))
    print_current_settings()
    b1 = Bitmax(conf.get('referals')[0], pair=actual.get('pair'))
    b2 = Bitmax(conf.get('referals')[1], pair=actual.get('pair'))
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(lambda: clear(b1, b2), 'interval', minutes=5)
    scheduler.start()
    if b1.auth() and b2.auth():
        clear(b1, b2)
        return b1, b2
    else:
        return False


def get_balance_list(b1: Bitmax, b2: Bitmax):
    balance_b1 = get_bot_balance(bot=b1, pair=actual.get('pair'))
    balance_b2 = get_bot_balance(bot=b2, pair=actual.get('pair'))
    return [balance_b1, balance_b2]


def dep_equalizer(pair_balance: dict, owner: Bitmax):
    left_depo = pair_balance.get(actual.get('left'))
    right_depo = pair_balance.get(actual.get('right'))
    delta = round(left_depo - right_depo, 6)

    if delta >= 0:
        price = tik().get('sell')
        if delta > actual.get('minTx'):
            tmp_tx_sell = create_order(owner, price=price, amount=delta / 2.0, side='sell')
            #tmp_tx_buy = create_order(owner, price=price, amount=delta / 2.0 * 0.9, side='buy')
            return tmp_tx_sell
        else:
            return None

    elif delta < 0:
        delta = delta * -1
        price = tik().get('buy')
        if delta > actual.get('minTx'):
            tmp_tx_sell = create_order(owner, price=price, amount=delta / 2.0 / price, side='buy')
            return tmp_tx_sell
        else:
            return None
    else:
        return pair_balance


def equalize_funds(funds: list, bot1, bot2):
    res1 = dep_equalizer(funds[0], bot1)
    res2 = dep_equalizer(funds[1], bot2)
    return [res1, res2]


def mine(bot1: Bitmax, bot2: Bitmax, bot_funds: list):
    maker = None
    taker = None
    global last_price_middle
    # r_side = random.choice(['sell', 'buy'])
    # unit = 'left' if r_side == 'sell' else 'right'
    # c_unit = 'left' if unit == 'right' else 'right'
    r_side = 'buy'
    unit = 'right'
    c_unit = 'left'
    rand = random.randint(1, 100) % 2
    if rand == 0:
        maker = [bot1, bot_funds[0]]
        taker = [bot2, bot_funds[1]]
    else:
        maker = [bot2, bot_funds[1]]
        taker = [bot1, bot_funds[0]]
    tik_now = tik()
    price = tik_now.get('middle')
    am_maker_base = ((taker[1].get(actual.get(unit))) * price)
    am_maker = round(am_maker_base - (am_maker_base * actual.get('mining_fee')), 6) * 0.5
    # am_taker = taker[1].get(actual.get(c_unit)) * actual.get('mining_fee')
    am_taker = am_maker
    if price != last_price_middle:
        last_price_middle = price
    if tik_now.get('delta') <= 3:
        rev_tx = create_order(bot=maker[0], price=price, amount=am_maker, side=r_side)
        mine_tx = create_order(bot=taker[0], price=price, amount=am_taker, side=tx_cross_side(r_side))
        time_prefix()
        print(rev_tx)
        logger.info(rev_tx)
        time_prefix()
        print(mine_tx)
        logger.info(mine_tx)
    else:
        time_prefix()
        print(f"Delta: {tik_now.get('delta')} - too risky, waiting...")


def order_checker(order_list: dict, owner: Bitmax):
    for order in order_list:
        now = tik()
        # price_ratio = now.get('middle') / (float(order.get('orderPrice'))) * 100
        #if -1 * actual.get('risk') < price_ratio < actual.get('risk'):
        price_ratio = int((now.get('middle') - float(order.get('orderPrice'))) / (actual.get('step') / 10))
        time_prefix()
        print(f'Ratio: {price_ratio}')

        if -2 < price_ratio < 2:
            pass
        else:
            owner.cancel_order_by_id(order.get('coid'))

def check_my_orders(b1: Bitmax, b2: Bitmax):
    ol_1 = b1.get_open_orders().get('data')
    ol_2 = b2.get_open_orders().get('data')
    order_checker(ol_1, b1)
    order_checker(ol_2, b2)


if __name__ == '__main__':
    bot_one, bot_two = auth_start()

    # print(bot_funds)
    while True:
        bot_funds = get_balance_list(b1=bot_one, b2=bot_two)
        prepared1, prepared2 = equalize_funds(bot_funds, bot_one, bot_two)
        mine(bot1=bot_one, bot2=bot_two, bot_funds=bot_funds)
        check_my_orders(bot_one, bot_two)
        #sleep(1)
