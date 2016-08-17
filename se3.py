import websocket
import time
import json
import Queue
from threading import Thread


def sw_test(account, venue, ticker, q):
    url="wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/tickertape/stocks/{}".format(account, venue, ticker)
    while 1:
        try:
            tick = ws.recv()
            with q.mutex:
                q.queue.clear()
            q.put(tick)
        except:
            ws = websocket.create_connection(url)
    return


def pipe_test(account, venue, ticker):
    q = Queue.Queue()

    sw = Thread(target=sw_test, args=(account, venue, ticker, q,))
    sw.start()

    t_start = time.time()
    while time.time() - t_start < 120:
        print q.get()
    return

if __name__ == '__main__':

    account = 'OFB36823187'
    venue = 'RYWEX'
    ticker = 'HFS'

    pipe_test(account, venue, ticker)
