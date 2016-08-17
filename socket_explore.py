import websocket
import time

def sw_test():
    u="wss://api.stockfighter.io/ob/api/ws/EXB123456/venues/TESTEX/tickertape/stocks/FOOBAR"
    while 1:
        try:
            msg = ws.recv()
            print(msg)
        except:
            ws = websocket.create_connection(u)






if __name__ == '__main__':
    url = 'wss://www.stockfighter.io/ob/api/ws/EXB123456/venues/TESTEX/tickertape/stocks/FOOBAR'

    sw_test()
