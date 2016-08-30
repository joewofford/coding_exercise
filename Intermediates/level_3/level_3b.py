from __future__ import division

import requests
import random
import time
import websocket
import json
import Queue
import threading

from selenium import webdriver
from datetime import datetime
from collections import defaultdict

#API key for the stockfighter website
AUTH = {'X-Starfighter-Authorization': '9bdfb2fc891821dabf7697fd40cd98e2365c02eb'}

#User information for login (user specific)
USERNAME = 'joewofford'
PS = 'givepeyton#18'

#path to the chromedriver for selenium to use (machine specific)
PATH_TO_CHROMEDRIVER = '/Users/joewofford/anaconda/chromedriver'

#Parameters related to how the market-making will be executed
#How deep into the spread we will bid/ask (larger number is deeper into spread).  The deeper into the spread the less likely profit is derived from each trade, but the more likely each bid/ask is to find a counter party (larger than .5...not such a good idea!)
TRADE_AGGRESSION = .1
#The multiple to use if there is a big ask/bid taking place which has exhausted the other trade direction, will be added/subtracted from the existing big ask/bid
NO_SPREAD_AGGRESSION = .01
#Ownership tollerance, the point at which to slow buying/selling as the account approaches maximum long/short position
OWNERSHIP_TOLLERANCE = .3
OWNERSHIP_MULTIPLE = .2
#The depth multiple at which regular market making will switch to adapt to big asks or buys (likely indicating the hedgefunds are actively trading)..
DEPTH_MULTIPLE = 3

class MakeMarketCarefully(object):
    '''
    A class designed to execute market-making activity on the stockfighter website in the dueling_bulldozers game (i.e. two hedgefunds fighting it out in the market).
    '''

    def __init__(self, target=280000, min_trade=50, max_trade=100, max_own=1000, owned=0):
        '''
        INPUT:
        target - The target total value of the account at the end of the task (int)
        min_trade - The minimum number of shares to include in any trade (int)
        max_trade - The maximum number of shares to include in any trade (int)
        owned - The number of shares the account starts with (int)
        OUTPUT: Instance of the MakeMarketCarefully class (object)
        '''
        self.target = target
        self.min_trade = min_trade
        self.max_trade = max_trade
        self.owned = owned
        self.max_own = max_own

    def make_money(self):

        #Initializing various attributes needed for trading
        self.current_profit = 0
        self.last_share_price = 0
        self.cash = 0
        self.fill_count = 0
        self.mean_quote_age = 0
        self.mean_bid_depth = 0
        self.mean_ask_depth = 0
        self.quote_count = 0
        self.trade_fills = defaultdict(set)
        self.ticker_queue = Queue.Queue()
        self.trade_queue = Queue.Queue()
        self.big_ask = False
        self.big_bid = False

        b_chrome = self._login()
        self._initiate_market(b_chrome)
        self._parse_trade_info(b_chrome)
        self._get_venue()

        #Launching the tickertape through a websocket, which will communicate the quotes through the self.quote_queue attribute
        tickertape = threading.Thread(target = self._launch_tickertape)
        tickertape.start()

        #Testing to see if the tickertape has launched yet, if not then wait
        while self.ticker_queue.empty():
            time.sleep(1)

        #Launching the tradetape through a websocket, which will communicate executed trades through the self.trade_queue attribute
        tradetape = threading.Thread(target = self._launch_tradetape)
        tradetape.start()

        #Arbitrary pause to wait for tradetape to launch (can't test without trading)...
        time.sleep(10)

        #Launching the tabulate_trade_results method in a Thread to update the class attributes as each trade confirmation comes over the tradetame
        tabulatetrades = threading.Thread(target = self._tabulate_trade_results)
        tabulatetrades.start()

        print threading.enumerate()

        #Begin actual trading...
        self._trade()

        print 'We have made {}, and currently own {} shares of {}.'.format(str(self.current_profit), str(self.owned), self.ticker)

        self._pause()

        return

    def _trade(self):
        '''
        INPUT:
        OUTPUT:

        '''
        print 'Trading started...'

        while self.current_profit < self.target:
            if not self.ticker_queue.empty():
                #Getting the newest quote
                quote = json.loads(self.ticker_queue.get())

                #Checking if the quote is actually a quote and not a websocket ping..
                if all(x in quote for x in ['ok', 'quote']):

                    #Update the local value to the most recent trade price
                    if 'last' in quote['quote'].keys():
                        self.last_share_price = quote['quote']['last']/100
                        self.current_profit = self.cash + self.owned * self.last_share_price

                    q_age, ask, ask_depth, bid, bid_depth = self._parse_quote(quote)

                    #Checking the quote isn't too old to trade on
                    if q_age < self.mean_quote_age and self.quote_count > 30:
                        #Checking for big bids or asks...
                        if ask_depth > (self.mean_ask_depth * DEPTH_MULTIPLE):
                            self.big_ask = True
                            print 'BIG ASK!!!'
                        if bid_depth > (self.mean_bid_depth * DEPTH_MULTIPLE):
                            self.big_bid = True
                            print 'BIG BID!!!'

                        #Executing trades of the appropriate type...
                        if self.big_ask and self.big_bid:
                            self._trade_normal(ask, bid)
                        elif self.big_ask:
                            self._trade_big_ask(ask, ask_depth, bid, bid_depth)
                        elif self.big_bid:
                            self._trade_big_bid(ask, ask_depth, bid, bid_depth)
                        else:
                            self._trade_normal(ask, bid)

                    self._update_means(q_age, bid_depth, ask_depth)
            time.sleep(.01)
        return

    def _trade_big_bid(self, ask, ask_depth, bid, bid_depth):
        #Executing buys just above the current bid to take advantage of the price floor established by the hedgefund trade
        if bid_depth > (self.mean_bid_depth * DEPTH_MULTIPLE):
            buy_size = min(self.max_trade, (self.max_own - abs(self.owned)))
            if ask > 0:
                buy_price = int(str(bid + (ask - bid) * TRADE_AGGRESSION).split('.')[0])
            else:
                buy_price = bid * (1 + NO_SPREAD_AGGRESSION)
            buy = self._single_trade(buy_size, 'buy', buy_price, 'immediate-or-cancel')

        #Unloading the shares once the big hendgefund trade has cleared and the market has stabalized
        if bid_depth < (self.mean_bid_depth * DEPTH_MULTIPLE):
            if ask > 0 and bid > 0:
                sell_size = min(self.max_trade, abs(self.owned))
                sell_price = int(str(ask - (ask - bid) * TRADE_AGGRESSION).split('.')[0])
                sell = self._single_trade(sell_size, 'sell', sell_price, 'immediate-or-cancel')

        #End 'big-bid' cycle, return to normal trading
        if bid_depth < (self.mean_bid_depth * DEPTH_MULTIPLE) and abs(self.owned) < 100:
            self.big_bid = False
        return

    def _trade_big_ask(self, ask, ask_depth, bid, bid_depth):
        #Executing sells just below the current ask to take advantage of the price ceiling established by the hedgefund trade
        if ask_depth > (self.mean_ask_depth *DEPTH_MULTIPLE):
            sell_size = min(self.max_trade, (self.max_own - abs(self.owned)))
            if bid > 0:
                sell_price = int(str(ask - (ask - bid) * TRADE_AGGRESSION).split('.')[0])
            else:
                sell_price = ask * (1 - NO_SPREAD_AGGRESSION)
            sell = self._single_trade(sell_size, 'sell', sell_price, 'immediate-or-cancel')

        #Re-buying shares once the big hedgefund trade has cleared and the market has stabalized
        if ask_depth < (self.mean_ask_depth * DEPTH_MULTIPLE):
            if ask > 0 and bid > 0:
                buy_size = min(self.max_trade, abs(self.owned))
                buy_price = int(str(bid + (ask - bid) * TRADE_AGGRESSION).split('.')[0])
                buy = self._single_trade(buy_size, 'buy', buy_price, 'immediate-or-cancel')

        #End 'big-ask' cycle, return to normal trading
        if ask_depth < (self.mean_ask_depth * DEPTH_MULTIPLE) and abs(self.owned) < 100:
            self.big_ask = False
        return

    def _trade_normal(self, ask, bid):
        trade_size = min(random.randint(self.min_trade, self.max_trade), (self.max_own - abs(self.owned)))

        if self.owned < self.max_own:
            #Resizing to account for ownership limit
            if self.owned > (self.max_own * OWNERSHIP_TOLLERANCE):
                buy_size = trade_size * OWNERSHIP_MULTIPLE
            else:
                buy_size = trade_size
            buy_price = int(str(bid + (ask - bid) * TRADE_AGGRESSION).split('.')[0])
            buy = self._single_trade(buy_size, 'buy', buy_price, 'immediate-or-cancel')

        if self.owned > (-1 * self.max_own):
            #Resizing to account for ownership limit
            if self.owned < (-1 * self.max_own * OWNERSHIP_TOLLERANCE):
                sell_size = trade_size * OWNERSHIP_MULTIPLE
            else:
                sell_size = trade_size
            sell_price = int(str(ask - (ask - bid) * TRADE_AGGRESSION).split('.')[0])
            sell = self._single_trade(sell_size, 'sell', sell_price, 'immediate-or-cancel')

        return

    def _parse_quote(self, quote):
        #Stripping the time the quote was generated
        q_time = datetime.strptime(quote['quote']['quoteTime'].split('.')[0], '%Y-%m-%dT%H:%M:%S')

        #Finding the age of the quote in seconds
        q_age = (datetime.utcnow() - q_time).total_seconds()

        if 'ask' in quote['quote'].keys():
            ask = quote['quote']['ask']
        else:
            ask = 0

        if 'askDepth' in quote['quote'].keys():
            ask_depth = quote['quote']['askDepth']
        else:
            ask_depth = 0

        if 'bid' in quote['quote'].keys():
            bid = quote['quote']['bid']
        else:
            bid = 0

        if 'bidDepth' in quote['quote'].keys():
            bid_depth = quote['quote']['bidDepth']
        else:
            bid_depth = 0

        return q_age, ask, ask_depth, bid, bid_depth

    def _update_means(self, q_age, bid_depth, ask_depth):
        self.mean_quote_age = ((self.mean_quote_age * self.quote_count) + q_age) / (self.quote_count + 1)

        self.mean_bid_depth = ((self.mean_bid_depth * self.quote_count) + bid_depth) / (self.quote_count + 1)

        self.mean_ask_depth = ((self.mean_ask_depth * self.quote_count) + ask_depth) / (self.quote_count + 1)

        self.quote_count += 1
        return

    def _tabulate_trade_results(self):
        '''
        INPUT: Queue object containing all of the trade confirmations recieved on the tradeticker stream that have yet to be accounted for
        OUTPUT:
        This method is responsible for accounting for the result of each trade sent, both in number of shares bought/sold, as well as their cost, and updated the class attributes accordingly. Is meant to be run inside a Thread object.
        '''
        print 'Launching the trade tabulator.'
        while 1:
            if not self.trade_queue.empty():
                trade = json.loads(self.trade_queue.get())
                #print 'Trade pulled from queue.'

                #Checking the 'trade' is actually a trade and not a websocket ping...
                if all(x in trade for x in ['ok', 'filled']):
                    #print 'It is a trade.'

                    if trade['order']['direction'] == 'buy':
                        self.owned = self.owned + self._sum_fills(trade)
                        self.cash = self.cash - self._sum_trade_value(trade)

                    if trade['order']['direction'] == 'sell':
                        self.owned = self.owned - self._sum_fills(trade)
                        self.cash = self.cash + self._sum_trade_value(trade)

                    #Setting each trade_id as a key, with the value as a set of the timestamps
                    self.trade_fills[str(trade['order']['id'])].update([x['ts'] for x in trade['order']['fills']])
                    self.fill_count += 1

                    self.current_profit = self.cash + self.owned * self.last_share_price
                    print 'Total number of executed trades = {}'.format(str(self.fill_count))
                    print 'Total net current profit = {}'.format(str(self.current_profit))
                    print 'Number of shares owned: {}.'.format(str(self.owned))
                time.sleep(.01)
        return

    def _single_trade(self, qty, direction, price, order_type):
        '''
        INPUT:
        qty - The number of shares to be bought/sold (int)
        direction - Whether the trade is a buy or sell (string)
        price - The price to bid/ask for the trade (int)
        order_type - The type of order to initiate, defaults to 'limit' (string)
        OUTPUT: Resests post response object (includes .json() method ot access data)
        Executes a single trade order for self.ticker on the self.account, at self.venue, initiating a trade for the designated quantity of shares using the order type.
        '''
        order = {
        'account': self.account,
        'venue': self.venue,
        'stock': self.ticker,
        'qty': qty,
        'direction': direction,
        'price': price,
        'orderType': order_type
        }
        call = requests.post('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders'.format(self.venue, self.ticker), headers=AUTH, json=order)
        return call

    def _sum_trade_value(self, trade):
        '''
        INPUT: Item corresponding to a trade execution ticker object (dict)
        OUTPUT: The total monetary exchange in the trade (ingoing or outgoing) (float)
        Aggregates the cost of all of the fills associated with the trade THAT HAVE NOT ALREADY BEEN ACCOUNTED FOR (see 'if' statement).
        '''
        return sum([x['qty'] * x['price'] for x in trade['order']['fills'] if x['ts'] not in self.trade_fills[str(trade['order']['id'])]])/100

    def _sum_fills(self, trade):
        '''
        INPUT: Item corresponding to a trade execution ticker object (dict)
        OUTPUT: The total number of shares filled (bought or sold) thus far (int)
        Aggregataes all of the fills associated with the trade after checking if each fill has already been account for.
        '''
        return sum([x['qty'] for x in trade['order']['fills'] if x['ts'] not in self.trade_fills[str(trade['order']['id'])]])

    def _launch_tradetape(self):
        '''
        INPUT: A Queue object to dump the tradetape information into
        OUTPUT:
        Initiates a websocket connection to the stockfighter executed trades tape for the self.ticker stock on the self.venue exchange.  Recieves the trade and adds it to the queue to be read by the tabulation method. Is meant to be run inside a Thread object.
        '''
        url = 'wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/executions/stocks/{}'.format(self.account, self.venue, self.ticker)

        print 'Launching tradetape now.'
        while 1:
            trade = False
            try:
                trade = ws.recv()
            except:
                ws = websocket.create_connection(url)

            if trade != False:
                self.trade_queue.put(trade)
        return

    def _launch_tickertape(self):
        '''
        INPUT: Queue object to dump the ticker quotes into
        OUTPUT:
        Initiates a websocket connection to the stockfighter tickertape for the self.ticker stock on the self.venue exchange.  Recieves the quote objects and stores them in a queue (after deleting the quote currently in the queue).  Thus is designed to maintain the queue with only the most recent quote in it.  It is meant to be run inside a Thread object.
        '''
        url = 'wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/tickertape/stocks/{}'.format(self.account, self.venue, self.ticker)
        print 'Launching tickertape now.'
        while 1:
            tick = False
            try:
                tick = ws.recv()
            except:
                ws = websocket.create_connection(url)

            if tick != False:
                with self.ticker_queue.mutex:
                    self.ticker_queue.queue.clear()
                self.ticker_queue.put(tick)
        return

    def _get_venue(self):
        '''
        INPUT:
        OUTPUT: Sets the self.venue attribute to the venue where the self.ticker stock is traded
        Queries the stockfighter API to determine on which venue/exchange the stock denoted by the inputed ticker is traded.  Collects a list of all venues, then iterates through and examines the list of stocks on that venue.
        '''
        call = requests.get('https://api.stockfighter.io/ob/api/venues', headers=AUTH)
        venues = [d['venue'] for d in call.json()['venues']]

        for venue in venues:
            if self.ticker in self._get_tickers(venue):
                self.venue = venue
        print 'Venue is: {}'.format(self.venue)
        return

    def _get_tickers(self, venue):
        '''
        INPUT: Venue name as a string
        OUTPUT: List of ticker symbols
        Queries the stockfighter API to determine stocks traded on the inputted venue/exchange, and returns them as a list of ticker symbols.
        '''
        call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks'.format(venue), headers=AUTH)

        if not call.ok:
            return []

        return [d['symbol'] for d in call.json()['symbols']]

    def _parse_trade_info(self, b_chrome):
        self.ticker = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[2]/em').text
        print 'Ticker is: {}.'.format(self.ticker)

        self.account = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[12]/strong').text.split()[1]
        print 'Account is: {}.'.format(self.account)

        b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[3]/button').click()
        return

    def _initiate_market(self, b_chrome):
        '''
        INPUT: Selenium webdriver for the chrome browser
        OUTPUT:
        Uses the webdriver to navigate through the post-login stockfighter webpage to initiate a 'sell_side' game.
        '''
        b_chrome.find_element_by_xpath('//*[@id="app"]/div/div/div/div/div[1]/div[2]/ul/li[1]/b/a').click()
        time.sleep(3)
        b_chrome.find_element_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]').click()
        time.sleep(1)
        b_chrome.find_element_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]/ul/li[2]/a').click()
        time.sleep(10)
        return

    def _login(self):
        '''
        INPUT:
        OUTPUT: Selenium webdriver for the chrome browser
        Launches a selenium webdriver and uses it to open a browser window and log into the stockfighter webpage.  It then returns the active webdriver.
        '''
        url = 'https://www.stockfighter.io'
        b_chrome = webdriver.Chrome(executable_path = PATH_TO_CHROMEDRIVER)
        b_chrome.get(url)
        b_chrome.find_element_by_name('session[username]').send_keys(USERNAME)
        b_chrome.find_element_by_name('session[password]').send_keys(PS)
        b_chrome.find_element_by_xpath('//*[@id="loginform"]/button').click()
        time.sleep(10)
        return b_chrome

    def _pause(self):
        programPause = raw_input('Press the <ENTER> key to continue...')

if __name__ == '__main__':
    funfun = MakeMarketCarefully()
    funfun.make_money()
