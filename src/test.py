import src.bitmax_api as api



prices = api.Bitmax.get_tik('ETH/BTC')
for k, v in prices.items():
    print(f"{k}: {v}")