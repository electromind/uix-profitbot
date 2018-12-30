# -*- coding: utf-8 -*-
import sys
from utils import read_config, print_logtime, cross_side, uuid32
from bitmax_api import Bitmax
import time
import os
import json
import datetime
import random
from client import *
from constants import INTERVAL
from apscheduler.schedulers.background import BackgroundScheduler

actual = dict()
takt = dict()


def app_setup():
    try:
        app_config = read_config().get('settings')
        actual['pair'] = app_config.get('pair')
        actual['left'], actual['right'] = actual.get('pair').split('/')
        tmp_left_step = Bitmax.get_asset_info(actual.get('left'))
        tmp_right_step = Bitmax.get_asset_info(actual.get('right'))
        actual['l_step'] = tmp_left_step.get('step')
        actual['r_step'] = tmp_right_step.get('step')
        actual['risk'] = int(app_config.get('recheck_bounds'))
        actual['price_tactic'] = app_config['price_tactic']
        fees = Bitmax.get_current_fees()
        actual['rev_fee'] = float(fees.get('maker').get('rebate'))
        actual['mining_fee'] = float(fees.get('taker').get('mining'))
    except KeyError as err:
        print_logtime()
        print(f"Invalid key. Check config file: {err.args}")
        sys.exit(1)
    except Exception as err:
        print_logtime()
        print(f"Error: {err.args}")
        sys.exit(1)


def team_setup(b1_login=None, b2_login=None):
    config = read_config()
    bots = config.get('bots')
    if not b1_login and not b2_login:
        bt1 = Bitmax(user=bots[0])
        bt2 = Bitmax(user=bots[1])
        print_logtime()
        print(f'Bot #1 with login: {bt1.email} created.')
        print_logtime()
        print(f'Bot #2 with login: {bt2.email} created.')
        return [bt1, bt2]
    elif b1_login and b2_login:
        bot_list = []
        for bot in bots:
            if bot.get('login') == b1_login or b2_login:
                bot_list.append(Bitmax(user=bot))
            print_logtime()
            print(f'Bot #1 with login: {bt1.email} created.')
            print_logtime()
            print(f'Bot #2 with login: {bt2.email} created.')
    else:
        print('One of bots is not configured. Please check config file and try again.')
        sys.exit(1)


def pair_info(p: str) -> dict:
    info = Bitmax.get_pair_info(p)
    return info


def tradepair_setup(pair):
    if isinstance(pair, str):
        tmp = pair_info(pair)
        actual['minTx'] = float(tmp.get('minQty'))
        actual['maxTx'] = float(tmp.get('maxQty'))
        if tmp.get('miningStatus') == 'Mining,ReverseMining':
            actual['mining'] = True
            actual['reverse'] = True
        elif tmp.get('miningStatus') == 'Mining':
            actual['reverse'] = False
            actual['mining'] = True


def setup():
    app_setup()
    tradepair_setup(actual.get('pair'))
    for k, v in actual.items():
        print_logtime()
        if k == 'l_step':
            print(f"|| INFO ||:\t{actual.get('left')} step: {actual.get('l_step'):.8f}")
        elif k == 'r_step':
            print(f"|| INFO ||:\t{actual.get('right')} step: {actual.get('r_step'):.8f}")
        else:
            print(f"|| INFO ||:\t{k}: {v}")
    return team_setup()


def tik(is_printable=False):
    actual_tik = Bitmax.get_tik(actual.get('pair'))
    takt['sell'] = actual_tik.get('buyPrice')
    takt['buy'] = actual_tik.get('sellPrice')
    takt['delta'] = int((takt['sell'] - takt['buy']) / actual.get('l_step'))
    if is_printable:
        print_logtime()
        print(f"|| INFO ||: Ask / Sell: {actual_tik.get('sellPrice')}")
        print_logtime()
        print(f"|| INFO ||: Bid / Buy: {actual_tik.get('buyPrice')}")
        print_logtime()
        print(f"|| INFO ||: Spread: {takt['delta']}")
        return takt
    else:
        return takt


def get_balances(bot: Bitmax):
    bot_info = bot.get_balances(pair=actual.get('pair'))
    print_logtime()
    print(f"|| BALANCE ||:\tAccount: {str(bot.email)[:3]}*** ")
    print_logtime()
    print(f"|| BALANCE ||:\t{actual.get('left')}: {bot_info.get(actual.get('left')):.9f}")
    print_logtime()
    print(f"|| BALANCE ||:\t{actual.get('right')}: {bot_info.get(actual.get('right')):.9f}")
    return bot_info


def is_protected(pr, side):
    t = tik(is_printable=True)
    if side == 'buy':
        check = ((pr - t.get(side)) / t.get(side)) * 100
    else:
        check = ((t.get(side) - pr) / t.get(side)) * 100

    v_risk = actual['risk']

    print_logtime()
    print(f"<< PRICE PROTECT >>")
    print_logtime()
    print(f"|| PP ||:\tRisk: {check:.2f}%")
    print_logtime()
    print(f"|| PP ||:\tOrder price: {pr}")
    print_logtime()
    print(f"|| PP ||:\tNow price: {t.get(side)}")
    print_logtime()
    print(f"|| PP ||:\tSide: {side}")
    if check == 0:
        print_logtime()
        print(f"|| PP ||:\tPrice is stable... Risk: 0% ")
        return {'working': True, "data": {'price': t.get(side), 'side': side}}
    # elif (-1 * v_risk) <= check < v_risk:
    #     print_logtime()
    #     print(f"|| PP ||:\tVolatility is low: {v_risk}% Mining: {True}")
    #     return {'working': True, "data": {'price': pr, 'side': side}}
    else:
        return
    #     print_logtime()
    #     print(f"|| WARN ||:\tVolatility is to high: {v_risk}% Mining: {False}")
    #     return {'working': False, "data": None}


def create_order(bot: Bitmax, pr, side, am):
    price_cr = is_protected(pr=pr, side=side)
    # if price_cr.get('price') and price_cr.get('side') == 'buy':
    #     am = price_cr.get('price') * (1 - actual.get('ref_fee'))
    # elif price_cr.get('price') and price_cr.get('side') == 'sell':
    #     am = price_cr.get('price') * (1 - actual.get('mining_fee'))
    # else:
    #     print_logtime()
    #     print('|| ERROR ||: Calculate amount fail. Exit.')
    result = bot.create_order(
        order_type='limit',
        price=pr,
        quantity=am,
        side=side,
        symbol=actual.get('pair')
    )
    print_logtime()
    print(f"{pr}")
    print_logtime()
    print(f"{am}")
    print_logtime()
    print(f"{side}")

    return result


def is_filled(bot: Bitmax, tx):
    if tx is None:
        print_logtime()
        print('!!!!!!!!!! checking fail !!!!!!!!!!!!!')
    else:
        while True:
            if bot.is_filled(tx.get('coid')):
                return True
            else:
                print_logtime()
                print(f'\t{tx}')
                continue


def base_to_queue(bal_dic: dict, price2updte):
    for k, v in bal_dic.items():
        if str(k) == actual.get('right'):
            tmp = v / price2updte
            bal_dic.update({k: tmp})
            return bal_dic


def save_to_log(starttime, response_data: dict, price: float, amount: float):
    print_logtime()
    log = dict(
        # user_id=b1.id,
        coid=response_data.get('coid'),
        create_date=datetime.datetime.utcnow().timestamp(),
        price=price,
        amount=amount,
        status='success'
    )
    if not os.path.exists('log'):
        os.makedirs('log')
    with open(f"log/{print_logtime(logging=True)[1:-1]}:00.log", 'a') as f:
        f.write(json.dumps(log) + '\n')
        f.close()
        if time.time() - starttime >= 3600:

            tx_list = create_list(stat_object=f"log/{print_logtime(logging=True)[1:-1]}:00.log")
            data = '{"user_id": "' + b1.id + '", "tx_list": [' + ','.join(tx_list) + ']}'
            if send_data(data=data):
                clear_log(f"log/{print_logtime(logging=True)[1:-1]}:00.log")
            else:
                pass


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
        max_b1[0] < max_b2[0]
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


if __name__ == '__main__':
    b1, b2 = setup()

    try:
        sock = socket.socket()
        sock.settimeout(10)
        sock.connect(('109.104.178.163', 2512))
        auth = f"auth_me:{b1.id}"
        sock.send(auth.encode('utf-8'))
        data = sock.recv(1024)
        sock.close()
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(lambda: clear(b1, b2), 'interval', minutes=3)
        scheduler.start()

        if data and data.decode('utf-8') == 'True':
            first_tik = tik()
            if isinstance(b1, Bitmax):
                b1.lastBuyPrice = first_tik.get('buy')
                b1.lastSellPrice = first_tik.get('sell')
            if isinstance(b2, Bitmax):
                b2.lastBuyPrice = first_tik.get('buy')
                b2.lastSellPrice = first_tik.get('sell')
            print('\tSTART REVERSE MINING\t'.join(['*' * 40, '*' * 40]))
            start_time = time.time()

            while True:
                global price
                b1_bal = get_balances(b1)
                b2_bal = get_balances(b2)
                takt = tik(is_printable=True)
                if takt.get('delta') > 20:
                    # miner tactics
                    if actual.get('price_tactic') == 'center':
                        price = (takt.get('buy') + takt.get('sell')) / 2.0
                        # price = takt.get('buy')
                        # price = takt.get('sell')

                    elif actual.get('price_tactic') == 'bid_plus_one':
                        price = takt.get('buy') + actual.get('step')

                    elif actual.get('price_tactic') == 'ask_minus_one':
                        price = takt.get('sell') - actual.get('step')

                    else:
                        print_logtime()
                        print("|| ERROR ||: Invalid transaction amount")
                        continue

                    data = find_maker(b1, b2, bal1=b1_bal, bal2=b2_bal, price=price)
                    # if b1.is_maker:
                    #     m = b1
                    #     t = b2
                    # else:
                    #     m = b2
                    #     t = b1

                    choice = random.randint(1, 100) % 2
                    if choice == 0:
                        m = b1
                        t = b2
                    else:
                        m = b2
                        t = b1
                    amnt = round(data.get('amount') * 0.5, 6)
                    if amnt < actual['minTx']:
                        continue
                    maker = create_order(bot=m, pr=price, side=data.get('side'), am=amnt)
                    # time.sleep(1)

                    taker = create_order(bot=t, pr=price, side=data.get('c_side'), am=amnt)
                    save_to_log(
                        starttime=time.time(),
                        response_data=taker if taker else {'coid': None, 'status': 'Fail'},
                        price=takt.get(data.get('side')),
                        amount=amnt
                    )
                    save_to_log(
                        starttime=time.time(),
                        response_data=maker if maker else {'coid': None, 'status': 'Fail'},
                        price=price,
                        amount=amnt
                    )

        else:
            print(f"Invalid key from authorization {b1.id}. Please check your config.json")
    except ConnectionError as e:
        print(f"Error to authorization: {e}")