import websocket
import time
import json
from multiprocessing import Process, Pipe, Value

def sw_test(conn_in, conn_out, account, venue, ticker):
    u="wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/tickertape/stocks/{}".format(account, venue, ticker)
    t_start = time.time()
    duration = True
    while duration:
        try:
            msg = ws.recv()
            #print(msg)
            conn_out.send(msg)
        except:
            print 'reconnecting...'
            ws = websocket.create_connection(u)
        try:
            duration = conn_in.recv()
        except:
            duration = True
    return


def pipe_test(conn_in, conn_out):
    t_start = time.time()
    while time.time() - t_start < 10:
        #print 'sending qty from pipe to ticker...'
        r = conn_in.recv()
        print r
    conn_out.send(False)
    return r


if __name__ == '__main__':

    account = 'HS96668273'
    venue = 'YDRBEX'
    ticker = 'KUUE'

    p_conn_1, c_conn_1 = Pipe()
    p_conn_2, c_conn_2 = Pipe()
    t1 = Process(target=sw_test, args=(c_conn_1, p_conn_2, account, venue, ticker,))
    t1.start()

    r = pipe_test(c_conn_2, p_conn_1)
    d = json.loads(r)

    print r
