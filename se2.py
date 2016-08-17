import websocket
import time
import level_1 as l1
from multiprocessing import Process, Pipe

def sw_test(conn_out):
    u="wss://api.stockfighter.io/ob/api/ws/FJT68020032/venues/XXEUEX/tickertape/stocks/IDYN"
    t_start = time.time()
    while time.time() - t_start < 30:
        try:
            msg = ws.recv()
            #print(msg)
            conn_out.send(msg)
        except:
            print 'reconnecting...'
            ws = websocket.create_connection(u)
    return


def pipe_test(conn_in):
    t_start = time.time()
    while time.time() - t_start < 30:
        #print 'sending qty from pipe to ticker...'
        r = [conn_in.recv()]
        print r
    return r


if __name__ == '__main__':

    account = 'FJT68020032'
    venue = 'XXEUEX'
    ticker = 'IDYN'

    p_conn_1, c_conn_1 = Pipe()
    t1 = Process(target=sw_test, args=(p_conn_1,))
    t1.start()

    r = pipe_test(c_conn_1)

    print r
