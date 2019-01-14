# -*- coding: utf-8 -*-
from datetime import datetime
import json
import sys
from bitmax_api import Bitmax
from bot_utils import read_config, get_logger, time_prefix
from client import send_data, clear_log, create_list
from apscheduler.schedulers.background import BackgroundScheduler


actual = dict()
takt = {}
logger = get_logger("MAIN")


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
        actual['risk'] = int(app_config.get('allowable_price_changing'))
        actual['pricing_method'] = app_config['pricing_method']
        fees = Bitmax.get_current_fees()
        actual['rev_fee'] = float(fees.get('maker').get('rebate'))
        actual['mining_fee'] = float(fees.get('taker').get('mining'))
    except KeyError as e:
        print(f"Invalid key. Check config file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"app_setup: {e}")
        sys.exit(1)

    for key, value in actual.items():
        time_prefix()
        if type(value) is float:
            print(f'{key}: {value:.8f}')
        else:
            print(f'{key}: {value}')


def tradepair_setup(pair):
    if isinstance(pair, str):
        tmp = Bitmax.pair_info(pair)
        actual['minTx'] = float(tmp.get('minQty'))
        actual['maxTx'] = float(tmp.get('maxQty'))
        if tmp.get('miningStatus') == 'Mining,ReverseMining':
            actual['mining'] = True
            actual['reverse'] = True
        elif tmp.get('miningStatus') == 'Mining':
            actual['reverse'] = False
            actual['mining'] = True


def tik():
    actual_tik = Bitmax.get_tik(actual.get('pair'))
    takt['sell'] = actual_tik.get('buyPrice')
    takt['buy'] = actual_tik.get('sell_price')
    takt['delta'] = int((takt['sell'] - takt['buy']) / actual.get('l_step'))
    return takt


def get_balances(bot: Bitmax, pair=None):
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

# def is_protected(pr, side):
#     t = tik(is_printable=True)
#     if side == 'buy':
#         check = ((pr - t.get(side)) / t.get(side)) * 100
#     else:
#         check = ((t.get(side) - pr) / t.get(side)) * 100
#     if check == 0:
#         return {'working': True, "data": {'price': t.get(side), 'side': side}}
#     # elif (-1 * v_risk) <= check < v_risk:
#     #     print_logtime()
#     #     print(f"|| PP ||:\tVolatility is low: {v_risk}% Mining: {True}")
#     #     return {'working': True, "data": {'price': pr, 'side': side}}
#     else:
#         return {'working': False, "data": None}
#     #     print_logtime()
#     #     print(f"|| WARN ||:\tVolatility is to high: {v_risk}% Mining: {False}")
#


def create_order(bot: Bitmax, price: float, side: str, amount: float, ):
    result = bot.create_order(
        order_type='limit',
        price=price,
        quantity=amount,
        side=side,
        symbol=actual.get('pair')
    )
    return result


def is_filled(bot: Bitmax, tx):
    if tx is None:
        return None
    else:
        while True:
            if bot.is_filled(tx.get('coid')):
                return True
            else:
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
        create_date=datetime.datetime.utcnow().timestamp(),
        price=price,
        amount=amount,
        status='success'
    )


def clear(b1: Bitmax, b2: Bitmax):
    b1.cancel_open_orders_by_pair_or_all()
    b2.cancel_open_orders_by_pair_or_all()


def find_maker(b1: Bitmax, b2: Bitmax, bal1, bal2, price):
    conv_b1 = base_to_queue(bal1, price2updte=price)
    conv_b2 = base_to_queue(bal2, price2updte=price)
    max_b1 = max(zip(conv_b1.values(), conv_b1.keys()))
    max_b2 = max(zip(conv_b2.values(), conv_b2.keys()))

    if max_b1[0] >= max_b2[0]:
        b1.is_maker = False
        b2.is_maker = True
        side = 'buy' if max_b2[1] == 'BTC' else 'sell'
        c_side = 'sell' if side == 'buy' else 'buy'
        return {'price': price, 'asset': 'BTC', 'amount': float(max_b2[0]), 'side': side, 'c_side': c_side}

    else:
        b1.is_maker = True
        b2.is_maker = False
        side = 'buy' if max_b1[1] == 'BTC' else 'sell'
        c_side = 'sell' if side == 'buy' else 'buy'
        return {'price': price, 'asset': 'BTC', 'amount': float(max_b1[0]), 'side': side, 'c_side': c_side}
    # else:
    #     if max_b1[0] == max_b2[0]:
    #         if max_b1[1] == 'BTC':
    #             b1.is_maker = True
    #             b2.is_maker = False
    #             return {'price': price, 'asset': 'BTC', 'amount': float(max_b2[0]), 'side': 'sell', 'c_side': 'buy'}
    #         if max_b1[1] == 'ETH':
    #             b1.is_maker = True
    #             b2.is_maker = False
    #             return {'price': price, 'asset': 'ETH', 'amount': float(max_b2[0]), 'side': 'sell', 'c_side': 'buy'}


def send_trx(logfile="example.txt"):
    tx_list = create_list(stat_object=logfile)
    data = '{"user_id": "' + b1.id + '", "tx_list": [' + ','.join(tx_list) + ']}'
    if send_data(data=data):
        clear_log(logfile)
        print("Statistics send successfully")
    else:
        print("No send")


if __name__ == '__main__':
    conf = read_config()
    app_setup(conf)
    b1 = Bitmax(conf.get('referals')[0], pair=actual.get('pair'))
    b2 = Bitmax(conf.get('referals')[1], pair=actual.get('pair'))
    if b1.auth() and b2.auth():
        b1_bal = get_balances(b1, actual.get('pair'))
        b2_bal = get_balances(b2, actual.get('pair'))
        time_prefix()
        print(b1_bal)
        time_prefix()
        print(b2_bal)
    # b1_bal = get_balances(b1)
    # b2_bal = get_balances(b2)
    # takt = tik(is_printable=True)
    # print(takt)
    #
    #     if data and data.decode('utf-8') == 'True':
    #         first_tik = tik()
    #         if isinstance(b1, Bitmax):
    #             b1.lastBuyPrice = first_tik.get('buy')
    #             b1.lastSellPrice = first_tik.get('sell')
    #         if isinstance(b2, Bitmax):
    #             b2.lastBuyPrice = first_tik.get('buy')
    #             b2.lastSellPrice = first_tik.get('sell')
    #         print('\tSTART REVERSE MINING\t'.join(['*' * 40, '*' * 40]))
    #
    #         while True:
    #             global price
    #             b1_bal = get_balances(b1)
    #             b2_bal = get_balances(b2)
    #             takt = tik(is_printable=True)
    #             if takt.get('delta') > 20:
    #                 # miner tactics
    #                 if actual.get('price_tactic') == 'center':
    #                     price = (takt.get('buy') + takt.get('sell')) / 2.0
    #                     # price = takt.get('buy')
    #                     # price = takt.get('sell')
    #
    #                 elif actual.get('price_tactic') == 'bid_plus_one':
    #                     price = takt.get('buy') + actual.get('step')
    #
    #                 elif actual.get('price_tactic') == 'ask_minus_one':
    #                     price = takt.get('sell') - actual.get('step')
    #
    #                 else:
    #                     print_logtime()
    #                     print("|| ERROR ||: Invalid transaction amount")
    #                     continue
    #
    #                 data = find_maker(b1, b2, bal1=b1_bal, bal2=b2_bal, price=price)
    #                 # if b1.is_maker:
    #                 #     m = b1
    #                 #     t = b2
    #                 # else:
    #                 #     m = b2
    #                 #     t = b1
    #
    #                 choice = random.randint(1, 100) % 2
    #                 if choice == 0:
    #                     m = b1
    #                     t = b2
    #                 else:
    #                     m = b2
    #                     t = b1
    #                 amnt = round(data.get('amount') * 0.5, 6)
    #                 if amnt < actual['minTx']:
    #                     continue
    #                 maker = create_order(bot=m, pr=price, side=data.get('side'), am=amnt)
    #                 # time.sleep(1)
    #
    #                 taker = create_order(bot=t, pr=price, side=data.get('c_side'), am=amnt)
    #                 save_to_log(
    #                     starttime=time.time(),
    #                     response_data=taker if taker else {'coid': None, 'status': 'Fail'},
    #                     price=takt.get(data.get('side')),
    #                     amount=amnt
    #                 )
    #                 save_to_log(
    #                     starttime=time.time(),
    #                     response_data=maker if maker else {'coid': None, 'status': 'Fail'},
    #                     price=price,
    #                     amount=amnt
    #                 )
    #
    #     else:
    #         print(f"Invalid key from authorization {b1.id}. Please check your config.json")
    # except ConnectionError as e:
    #     print(f"Error to authorization: {e}")