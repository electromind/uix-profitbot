# -*- coding: utf-8 -*-


class INTERVAL:
    one = 60000,
    five = 300000,
    half_hour = 1800000,
    hour = 3600000,
    six_hours = 21600000,
    day = 86400000


class PRICE_TACTICS:
    center =  "(ask + bid) / 2",
    bid_plus_one = "bid + step"
    asl_minus_one = "ask - step"