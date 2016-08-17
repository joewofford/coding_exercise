import websocket
import time
from multiprocessing import Process, Pipe

def sw_test():
    u="wss://api.stockfighter.io/ob/api/ws/EXB123456/venues/TESTEX/tickertape/stocks/FOOBAR"
    t_start = time.time()
    while time.time() - t_start < 300:
        try:
            msg = ws.recv()
            print(msg)
        except:
            ws = websocket.create_connection(u)



def est_ticker(account, venue, ticker, qty, conn_in, conn_out):
    url = 'wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/tickertape/stocks/{}'.format(account, venue, ticker)
    current_qty = 0
    while current_qty < qty:
        current_qty = conn_in.recv()
        print 'conn_in seemed to work, inside the while loop'
        try:
            quote = ws.recv()
            print quote
            conn_out.send(qoute)
        except:
            print 'Connecting ticker...'
            ws = websocket.create_connection(url, timeout=600)
    ws.close()
    return

def pipe_test(qty, conn_in, conn_out):
    t_start = time.time()
    while time.time() - t_start < 600:
        print 'sending qty from pipe to ticker...'
        conn_out.send(qty)
        print conn_in.recv()
    conn_out.set(100)
    return

def bar(conn_in, conn_out):
    l = [1, 2, 3]
    p=[]
    while len(l) > 0:
        conn_out.send(l.pop())
        p.append(conn_in.recv())
        print p
    return

def foo(conn_in, conn_out):
    l = []
    p = ['a', 'b', 'c']
    while len(l) < 3:
        l.append(conn_in.recv())
        conn_out.send(p.pop())
        print l
    return


if __name__ == '__main__':
    # url = 'wss://www.stockfighter.io/ob/api/ws/EXB123456/venues/TESTEX/tickertape/stocks/FOOBAR'

    # p_conn_t_p, c_conn_t_p = Pipe()
    # p_conn_p_t, c_conn_p_t = Pipe()
    #
    # p_test = Process(target=pipe_test, args=(50, c_conn_t_p, p_conn_p_t,))
    # t_test = Process(target=est_ticker, args=('EXB123456', 'TESTEX', 'FOOBAR', 50, c_conn_p_t, p_conn_t_p))
    #
    # p_test.start()
    # t_test.start()

    p_conn_1, c_conn_1 = Pipe()
    p_conn_2, c_conn_2 = Pipe()
    bar_test = Process(target=bar, args=(c_conn_2, p_conn_1,))
    foo_test = Process(target=foo, args=(c_conn_1, p_conn_2,))

    test = foo_test.start()
    bar = bar_test.start()
