# -*- coding: utf-8 -*-
class trade_interval:
    ONE_MINUTE = 60000,
    FIVE_MINUTES = 300000,
    HALF_HOUR = 1800000,
    HOUR = 3600000,
    SIX_HOURS = 21600000,
    DAY = 86400000


class pricing:

    def __init__(self):
        self._current = None
        self._default = "center"

    @property
    def current_method(self):
        return self._current

    @current_method.setter
    def current_method(self, method):
        if not isinstance(method, str):
            msg = f'Unknown pricing method type: {type(method)}'
            print(msg)
            raise TypeError(msg)

        elif method != pricing_methods.CENTER:
            msg = f'Unknown pricing method value: {str(method)}'
            print(msg)
            raise ValueError(msg)

        else:
            self._current = str(method)
            print(f'Current pricing method: {self.current_method}')


class pricing_methods:
    CENTER = 'center'
    BID = 'bid'
    ASK = 'ask'
    BIDplus = 'bid+'
    ASKplus = 'ask+'
