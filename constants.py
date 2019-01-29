# -*- coding: utf-8 -*-
app_mode = 'debug'  # 'release', 'debug_no_auth', 'debug'
testnet = '10.0.1.9'
testnet2 = '10.0.1.5'
mainnet = '109.104.178.163'
port_main = 2511
port_test = 2512


def get_mode():
    return app_mode


def get_net():
    if app_mode == 'release':
        network = mainnet
        port = port_main
    else:
        network = testnet
        port = port_test
    return network, port


class TradeInterval:
    ONE_MINUTE = 60000,
    FIVE_MINUTES = 300000,
    HALF_HOUR = 1800000,
    HOUR = 3600000,
    SIX_HOURS = 21600000,
    DAY = 86400000


class PricingMethods:
    CENTER = 'center'
    BID = 'bid'
    ASK = 'ask'
    BIDplus = 'bid+'
    ASKplus = 'ask+'
