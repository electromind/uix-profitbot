# -*- coding: utf-8 -*-
class AppMode:
    RELEASE = 'release'
    DEBUG = 'debug'
    DEV = 'dev'
    CURRENT = DEV
    uixlab_local = '10.0.1.9'
    testnet_observer_local = '10.0.1.5'
    mainnet = '109.104.178.163'
    port_main = 2511
    port_dev = 2512

    @classmethod
    def get_app_status(cls):
        return cls.CURRENT

    @classmethod
    def set_app_status(cls, status):
        if isinstance(status, AppMode):
            cls.CURRENT = status

    @classmethod
    def setup_transport(cls):
        if cls.CURRENT == cls.RELEASE:
            return cls.mainnet, cls.port_main
        elif cls.CURRENT == cls.DEBUG:
            return cls.uixlab_local, cls.port_dev


class Role:
    MINER = 'taker'
    REVERSER = 'maker'


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
