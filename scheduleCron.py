from crontab import CronTab

trademiner_cron = CronTab(user='electromind')
job = trademiner_cron.new(command='~/trademiner/server.py', comment='uix_trademiner')
job.minute.every(5)
trademiner_cron.write(filename='trademiner.py')