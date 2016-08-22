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
#How deep into the spread we will bid/ask (larger number is deeper into spread).  The deeper into the spread the less likely profit is derived from each trade, but the more likely each bid/ask is to find a counter party (larger than .5...not such a good idea!).
TRADE_AGGRESSION = .18
#The maximum age, in seconds, of a quote to use its information to initiate a trade
MAX_QUOTE_AGE = .75
#Ownership tollerance, the point at which to slow buying/selling as the account approaches maximum long/short position
OWNERSHIP_TOLLERANCE = .6
OWNERSHIP_MULTIPLE = .8

class MakeMarket(object):
    '''
    A class designed to execute market-making activity on the stockfighter website in the sell_side game.
    '''

    def __init__(self, target=12000, min_trade=20, max_trade=100, max_own=1000, owned=0):
        '''
        INPUT:
        target - The target total value of the account at the end of the task (int)
        min_trade - The minimum number of shares to include in any trade (int)
        max_trade - The maximum number of shares to include in any trade (int)
        max_own - The maximum number of shares the account is allowed to hold or short (int)
        owned - The number of shares the account starts with (int)
        OUTPUT: Instance of the MakeMarket class (object)
        '''
        self.target = target
        self.max_trade = max_trade
        self.min_trade = min_trade
        self.max_own = max_own
        self.owned = owned

    def make_market(self):
        '''
        INPUT:
        OUTPUT:
        The main method of the class.  First performs the web interfacing to log-in and launch the sell_side game, initiates the tickertape, then executes a series of trades (bids near the bottom of the spread, asks near the top) to perform "market-making" until the target value is reached.
        '''
        #Initializing various attributes needed for market making
        self.current_profit = 0
        self.last_share_price = 0
        self.cash = 0
        self.trade_count = 0
        self.trade_fills = defaultdict(set)

        #Performing pre-trading setup and parsing
        b_chrome = self._login()
        self._initiate_market(b_chrome)
        self._parse_trade_info(b_chrome)

        #Launching the tickertape through a websocket, which will communicate the quotes through the self.quote_queue attribute
        tickerqueue = Queue.Queue()
        tickertape = threading.Thread(target = self._launch_tickertape, args = (tickerqueue,))
        tickertape.start()

        #Testing to see if the tickertape has launched yet, if not then wait
        while tickerqueue.empty():
            time.sleep(1)

        #Launching the tradetape through a websocket, which will communicate executed trades through the self.trade_queue attribute
        tradequeue = Queue.Queue()
        tradetape = threading.Thread(target = self._launch_tradetape, args = (tradequeue,))
        tradetape.start()

        #Arbitrary pause to wait for tradetape to launch (can't test without trading)...
        time.sleep(10)

        #Launching the tabulate_trade_results method in a Thread to update the class attributes as each trade confirmation comes over the tradetame
        tabulatetrades = threading.Thread(target = self._tabulate_trade_results, args = (tradequeue,))
        tabulatetrades.start()

        print threading.enumerate()

        #Begin actual trading...
        self._start_trading(tickerqueue)

        print 'We have made {}, and currently own {} shares of {}.'.format(str(self.current_profit), str(self.owned), self.ticker)

        self._pause()

        return

    def _start_trading(self, tickerqueue):
        '''
        INPUT: Queue object containing the most recent quote from the websocket tickertape stream
        OUTPUT:
        Performs the actual trades comprising the market-making activities, buying and selling shares on the edge of the spread.
        '''
        print 'Trading started...'

        while self.current_profit < self.target:
            if not tickerqueue.empty():
                #Getting the newest quote
                quote = json.loads(tickerqueue.get())
                #print 'Quote pulled from queue.'

                #Checking if the quote is actually a quote, and not a websocket ping...
                if all(x in quote for x in ['ok', 'quote']):
                    #print 'It is a quote.'

                    #Trying to update our local value to the most recent trade price
                    if 'last' in quote['quote'].keys():
                        self.last_share_price = quote['quote']['last']/100
                        self.current_profit = self.cash + self.owned * self.last_share_price

                    #Checking the quote quality (has all the required fields to trade on it)
                    if all(x in quote['quote'] for x in ['bid', 'ask', 'quoteTime']):

                        #Strip the time the quote was generated
                        q_time = datetime.strptime(quote['quote']['quoteTime'].split('.')[0], '%Y-%m-%dT%H:%M:%S')

                        print 'Quote age is : {}'.format(str((datetime.utcnow() - q_time).total_seconds()))

                        #Checking to see if the quote isn't too old to trade on
                        if (datetime.utcnow() - q_time).total_seconds() < MAX_QUOTE_AGE:
                            ask = quote['quote']['ask']
                            bid = quote['quote']['bid']
                            print 'Sending trades.'

                            #Deciding how many shares to trade (random inside the range)
                            trade_size = min(random.randint(self.min_trade, self.max_trade), (self.max_own - abs(self.owned)))

                            if self.owned < self.max_own:
                                buy_size = trade_size
                                if self.owned > (self.max_own * OWNERSHIP_TOLLERANCE):
                                    buy_size = buy_size * OWNERSHIP_MULTIPLE
                                buy_price = int(str(bid + (ask - bid) * TRADE_AGGRESSION).split('.')[0])
                                buy = self._single_trade(buy_size, 'buy', buy_price, 'immediate-or-cancel')

                            if self.owned > (-1 * self.max_own):
                                sell_size = trade_size
                                if self.owned < (-1 * self.max_own * OWNERSHIP_TOLLERANCE):
                                    sell_size = sell_size * OWNERSHIP_MULTIPLE
                                sell_price = int(str(ask - (ask - bid) * TRADE_AGGRESSION).split('.')[0])
                                sell = self._single_trade(sell_size, 'sell', sell_price, 'immediate-or-cancel')
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

    def _tabulate_trade_results(self, tradequeue):
        '''
        INPUT: Queue object containing all of the trade confirmations recieved on the tradeticker stream that have yet to be accounted for
        OUTPUT:
        This method is responsible for accounting for the result of each trade sent, both in number of shares bought/sold, as well as their cost, and updated the class attributes accordingly. Is meant to be run inside a Thread object.
        '''
        print 'Launching the trade tabulator.'
        while 1:
            if not tradequeue.empty():
                trade = json.loads(tradequeue.get())
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
                    self.trade_count += 1

                    self.current_profit = self.cash + self.owned * self.last_share_price
                    print 'Total number of executed trades = {}'.format(str(self.trade_count))
                    print 'Total net current profit = {}'.format(str(self.current_profit))
                time.sleep(.01)
        return

    def _launch_tradetape(self, tradequeue):
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
                tradequeue.put(trade)
        return

    def _launch_tickertape(self, tickerqueue):
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
                with tickerqueue.mutex:
                    tickerqueue.queue.clear()
                tickerqueue.put(tick)
        return

    def _parse_trade_info(self, b_chrome):
        '''
        INPUT: Selenium webdriver for the chrome browser
        OUTPUT:
        Uses the webdriver to parse the opening page of the 'sell_side' game for the account to be traded on (self.account), the exchange where the trades will take place (self.venue), and the stock to be traded (self.ticker).  It then closes the pop-up window.
        '''
        self.account = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[1]/strong').text.split()[1]
        self.venue = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[1]/em[1]').text
        self.ticker = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[1]/em[2]').text
        time.sleep(2)
        b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[3]/button').click()
        print 'Account is: {}.'.format(self.account)
        print 'Ticker is: {}.'.format(self.ticker)
        print 'Venue is: {}.'.format(self.venue)
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
        b_chrome.find_element_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]/ul/li[2]/a/span[1]/b').click()
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
        programPause = raw_input("Press the <ENTER> key to continue...")



if __name__ == '__main__':
    market = MakeMarket()
    market.make_market()
