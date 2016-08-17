import requests
import random
import time
from bs4 import BeautifulSoup


AUTH = {'X-Starfighter-Authorization': '0d3cdd0cbdc4edb85093ec741b87a58f12d467a8'}

def check_venue(venue):
    '''
    INPUT: Venue name as a string
    OUTPUT: Boolean
    Queries the stockfighter API to test if the venue input is currently functioning.
    '''
    call = requests.get('https://api.stockfighter.io/ob/api/venues/' + venue, headers=AUTH)
    return call.ok


def get_tickers(venue):
    '''
    INPUT: Venue name as a string
    OUTPUT: List of ticker symbols
    Queries the stockfighter API to determine stocks traded on the inputted venue/exchange, and returns them as a list of ticker symbols.  Returns False if the venue does not exist.
    '''
    call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks'.format(venue), headers=AUTH)

    if not call.ok:
        return False

    return [d['symbol'] for d in call.json()['symbols']]


def get_venue(ticker):
    '''
    INPUT: Ticker symbol as a string
    OUTPUT: Venue name as a string
    Queries the stockfighter API to determine which venue/exchange the stock denoted by the inputed ticker is traded at.  Returns False if the ticker is not found in the currently active venues.
    '''
    call = requests.get('https://api.stockfighter.io/ob/api/venues', headers=AUTH)
    venues = [d['venue'] for d in call.json()['venues']]

    for venue in venues:
        if ticker in get_tickers(venue):
            return venue

    return False


def single_buy(account, venue, ticker, qty, order_type):
    '''
    INPUT:
    account - The account to be traded on (string)
    venue - The venue the where the ticker is listed (string)
    qty - The number of shares to be bought (int)
    order_type - The type of order (string)
    OUTPUT: Requests post response object
    Executes a single buy order on the given account, at the specified venue, purchasing the designated quantity of shares using the order type.
    '''
    order = {
    'account': account,
    'venue': venue,
    'stock': ticker,
    'qty': qty,
    'direction': 'buy',
    'orderType': order_type
    }

    call = requests.post('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders'.format(venue, ticker), headers=AUTH, json=order)
    return call


def trade_status(venue, ticker, t_id):
    '''
    INPUT:
    venue - Venue where the trade was initiated
    ticker - Symbol of the security
    t_id - Unique (by venue) identifier of the trade
    OUTPUT: Request response object

    '''
    call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders/{}'.format(venue, ticker, t_id), headers=AUTH)
    return call


def get_quote(venue, ticker):
    '''
    INPUT:
    OUTPUT:

    '''
    call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/quote'.format(venue, ticker), headers=AUTH)
    return call


def delete_trade(venue, ticker, t_id):
    '''
    INPUT:
    OUTPUT:

    '''
    call = requests.post('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders/{}/cancel'.format(venue, ticker, t_id), headers=AUTH)
    return call


def block_buy(account, ticker, qty, order_type='market', max_qty=1000):
    '''
    INPUT:
    OUTPUT:

    '''
    check = 0
    venue = get_venue(ticker)
    if not venue:
        return False

    while qty > 0:
        q = min(qty, random.randint(1, max_qty))
        print 'ordering {} shares of whatever'.format(str(q))
        print 'shares left to buy: {}'.format(str(qty))
        buy = single_buy(account, venue, ticker, q, order_type)

        while buy.status_code != requests.codes.ok:
            buy = single_buy(account, venue, ticker, q, order_type)
        t_sent = time.time()
        bought = buy.json()['qty']

        if bought < q:
            bought = trade_status(venue, ticker, buy.json()['id']).json()['totalFilled']
            while bought < q:

                if time.time() - t_sent > 5:
                    delete_trade(venue, ticker, buy.json()['id'])
                    break
                time.sleep(.1)
                bought = trade_status(venue, ticker, buy.json()['id']).json()['totalFilled']

        check = check + bought
        print 'so far we have: {}'.format(str(check))
        qty = qty - bought
        time.sleep(random.randint(3,6))

    return 'Well, that happened...'


def parse_target_price()




if __name__ == '__main__':
    account = 'SD30859062'
    ticker = 'ISOR'
    qty = 100000
    #call = get_tickers('TESTEX')
    #venue = get_venue('FOOBAR')
    #trade = single_trade('EXB123456', 'TESTEX', 'FOOBAR', 100, 10, 'buy', 'limit')
    #status = trade_status('TESTEX', 'FOOBAR', 859)
    #c = delete_trade('TESTEX', 'FOOBAR', 859)
    print block_buy(account, ticker, qty)
