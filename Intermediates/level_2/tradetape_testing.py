
import websocket

def tradetape(account, venue, ticker):
    url = 'wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/executions/stocks/{}'.format(account, venue, ticker)

    print 'Launching tradetape now.'
    while 1:
        trade = 'initial'
        try:
            trade = ws.recv()
        except:
            print 'Connecting websocket...'
            ws = websocket.create_connection(url)
            print 'Websocket connected...'
        print trade
    return

if __name__ == '__main__':
    account = 'EAH12527767'
    venue = 'TEIVEX'
    ticker = 'ORVU'

    tradetape(account, venue, ticker)
