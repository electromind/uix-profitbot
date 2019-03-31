# -*- coding: utf-8 -*-

class PBProtocol:
    ONLINE = 'online#'
    AUTH = 'auth#'
    TX = 'tx_stat#'
    SYNC = 'sync#'


class Role:
    MINER = 1
    REVERSER = 2
    STANDBY = 0


class TradeInterval:
    MINUTE = 60000
    FIVE_MINUTES = MINUTE * 5
    HALF_HOUR = MINUTE * 30
    HOUR = MINUTE * 60
    SIX_HOURS = MINUTE * 60 * 6
    DAY = MINUTE * 60 * 24


class PricingMethods:
    CENTER = 'center'
    BUY = 'bid'
    SELL = 'ask'


class LoopState:
    RUN = 1
    PAUSE = 0
    STOP = -1


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
    def set_app_status(cls, status: LoopState):
        if isinstance(status, AppMode):
            cls.CURRENT = status

    @classmethod
    def get_address(cls):
        if cls.CURRENT == cls.RELEASE:
            return cls.mainnet, cls.port_main
        elif cls.CURRENT == cls.DEBUG:
            return cls.uixlab_local, cls.port_dev
