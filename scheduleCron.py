import bitmax_api
from bot_utils import read_config

# from crontab import CronTab
#
# trademiner_cron = CronTab(user='electromind')
# job = trademiner_cron.new(command='~/trademiner/server.py', comment='uix_trademiner')
# job.minute.every(5)
# trademiner_cron.write(filename='trademiner.py')


conf = read_config()
app_conf = conf.get('app')
pair = app_conf.get('pair')
b1 = bitmax_api.Bitmax(conf.get('referals')[0], pair=pair)
b2 = bitmax_api.Bitmax(conf.get('referals')[1], pair=pair)
b1.send_log_data('log/tx.log')
b2.send_log_data('log/tx.log')
