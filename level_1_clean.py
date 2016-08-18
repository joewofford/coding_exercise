import requests
import random
import time

AUTH = {'X-Starfighter-Authorization': '7f1b969336002cf5f1dbf584276fa81b0f13880f'}

class BlockTrade(object):

    def __init__(self, account, ticker, qty, order_type='market', max_qty=300):
        self.account = account
        self.ticker = ticker
        self.qty = qty
        self.order_type = order_type
        self.max_qty = max_qty
        return

    def _get_tickers(self, venue):
        '''
        INPUT: Venue name as a string
        OUTPUT: List of ticker symbols
        Queries the stockfighter API to determine stocks traded on the inputted venue/exchange, and returns them as a list of ticker symbols.  Returns False if the venue does not exist.
        '''
        call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks'.format(venue), headers=AUTH)

        if not call.ok:
            return False

        return [d['symbol'] for d in call.json()['symbols']]


    def _get_venue(self):
        '''
        INPUT:
        OUTPUT: Sets the self.venue attribute to the venue where the self.ticker stock is traded
        Queries the stockfighter API to determine which venue/exchange the stock denoted by the inputed ticker is traded at.  Returns False if the ticker is not found in the currently active venues.
        '''
        call = requests.get('https://api.stockfighter.io/ob/api/venues', headers=AUTH)
        venues = [d['venue'] for d in call.json()['venues']]

        for venue in venues:
            if self.ticker in get_tickers(venue):
                self.venue = venue
                return True

        return False


    def _single_buy(q):
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
        'account': self.account,
        'venue': self.venue,
        'stock': self.ticker,
        'qty': q,
        'direction': 'buy',
        'orderType': self.order_type
        }

        call = requests.post('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders'.format(self.venue, self.ticker), headers=AUTH, json=order)
        return call
