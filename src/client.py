import socket
import json


def create_list(stat_object='example.txt'):
    if isinstance(stat_object, str):
        with open(stat_object) as file:
            tx_list = list()
            for line in file:
                tx_list.append(line)
            return tx_list
    else:
        return False


def send_data(data):
    try:
        validator = json.loads(data)
        fragment = (validator['user_id'])
        tx = (validator['tx_list'])
        conn = socket.socket()
        conn.connect(('109.104.178.163', 2511))
        conn.send(bytes(data, 'utf-8'))
        conn.close()
        del(validator)
        del(fragment)
        del(tx)
        return True
    except Exception as e:
        print(e)
        return False


def clear_log(filename='examples.txt'):
    try:
        desc = open(filename, 'w')
        desc.close()
    except Exception as e:
        print(e)


def send_trx(logfile="example.txt"):
    tx_list = create_list(stat_object=logfile)
    data = '{"user_id": "' + b1.id + '", "tx_list": [' + ','.join(tx_list) + ']}'
    if send_data(data=data):
        clear_log(logfile)
        print("Statistics send successfully")
    else:
        pass
