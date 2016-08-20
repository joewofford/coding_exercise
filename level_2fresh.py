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

#API key for the stockfighter website
AUTH = {'X-Starfighter-Authorization': '9bdfb2fc891821dabf7697fd40cd98e2365c02eb'}

#User information for login (user specific)
USERNAME = 'joewofford'
PS = 'givepeyton#18'

#path to the chromedriver for selenium to use (machine specific)
PATH_TO_CHROMEDRIVER = '/Users/joewofford/anaconda/chromedriver'

#Parameters related to how the market-making will be executed
#How deep into the spread we will big/ask (larger number is more aggressive)
TRADE_AGGRESSION = .01
#The maximum age, in seconds, of a quote to use its information to initiate a trade
MAX_QUOTE_AGE = .8

class MakeMarket(object):

    def __init__(self, target=10000, min_trade=5, max_trade=25, max_own=1000, owned=0):
        self.target = target
        self.max_trade = max_trade
        self.min_trade = min_trade
        self.max_own = 1000
        self.owned = 0

    def make_market(self):
        #Initializing various attributes needed for market making
        self.current_profit = 0
        self.last_share_price = 0
        self.cash = 0
        self.trade_count = 0
        self.trade_ids = set()
        self.quote_queue = Queue.Queue()
        self.trade_queue = Queue.Queue()

        #Performing pre-trading setup and parsing
        b_chrome = self._login()
        self._initiate_market(b_chrome)
        self._parse_trade_info(b_chrome)

        #Launching the tickertape through a websocket, which will communicate the quotes through the self.quote_queue attribute
        tickertape = threading.Thread(target = self._launch_tickertape)
        tickertape.start()

        #Testing to see if the tickertape has launched yet, if not then wait
        while self.quote_queue.empty():
            time.sleep(1)

        #Launching the tradetape through a websocket, which will communicate executed trades through the self.trade_queue attribute
        tradetape = threading.Thread(target = self._launch_tradetape)
        tradetape.start()

        #Arbitrary pause to wait for tradetape to launch (can't test without trading)...
        time.sleep(30)

        #Launching the tabulate_trade_results method in a Thread to update the class attributes as each trade confirmation comes over the tradetame
        tabulatetrades = threading.Thread(target = self._tabulate_trade_results)
        tabulatetrades.start()

        print threading.enumerate()

        #Begin actual trading...
        self._start_trading()

        print 'We have made {}, and currently own {} shares of {}.'.format(str(self.profit), str(self.owned), self.ticker)

        return

    def _start_trading(self):
        '''
        INPUT:
        OUTPUT:

        '''
        print 'Trading started...'

        while self.current_profit < self.target:
            if not self.quote_queue.empty():
                #Getting the newest quote
                quote = json.loads(self.quote_queue.get())

                #Trying to update our internal value to the most recent trade price
                if 'last' in quote['quote'].keys():
                    self.last_share_price = quote['quote']['last']

                #Checking the quote quality (has all the required fields to trade on it)
                if all(x in quote['quote'] for x in ['bid', 'ask', 'quoteTime']):



                    #Strip the time the quote was generated
                    q_time = datetime.strptime(quote['quote']['quoteTime'].split('.')[0], '%Y-%m-%dT%H:%M:%S')

                    #Checking to see if the quote isn't too old to trade on
                    if (datetime.utcnow() - q_time).total_seconds() < MAX_QUOTE_AGE:
                        ask = quote['quote']['ask']
                        bid = quote['quote']['bid']

                        # #Deciding how many shares to trade (random inside range)
                        # trade_size = min(random.randint(self.min_trade, self.max_trade), (self.max_own - abs(self.owned)))
                        #TEMPORARY!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        trade_size = 20

                        if self.owned < self.max_own:
                            buy = self._single_trade(trade_size, 'buy', int(str(bid * (1 + TRADE_AGGRESSION)).split('.')[0]), 'fill-or-kill')
                            self.trade_ids.add(buy.json()['id'])

                        if self.owned > (-1 * self.max_own):
                            sell = self._single_trade(trade_size, 'sell', int(str(ask * (1 - TRADE_AGGRESSION)).split('.')[0]), 'fill-or-kill')
                            self.trade_ids.add(sell.json()['id'])
        return

    def _single_trade(self, qty, direction, price, order_type='limit'):
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
        return sum([x['qty'] * x['price'] for x in trade['order']['fills']])/100

    def _sum_fills(self, trade):
        '''
        INPUT: Requests return item corresponding to a trade status query
        OUTPUT: The total number of shares filled (bought or sold) thus far (int)
        Aggregataes all of the fills associated with the trade, resulting in the total number of shares bought/sold at the time of query.
        '''
        return sum([x['qty'] for x in trade['order']['fills']])

    def _tabulate_trade_results(self):
        print 'Launching the trade tabulator.'
        while 1:
            if not self.trade_queue.empty():
                print 'The trade queue is not empty, hooray!!!'
                trade = json.loads(self.trade_queue.get())
                #TEMPORARY!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                print trade
                self.trade_ids.add(trade['order']['id'])
                self.number_of_trades += 1

                if trade.json()['order']['direction'] == 'buy':
                    self.owned = self.owned + self._sum_fills(trade)
                    self.cash = self.cash - self._sum_trade_value(trade)

                if trade.json()['order']['direction'] == 'sell':
                    self.owned = self.owned - self._sum_fills(trade)
                    self.cash = self.cash + self._sum_trade_value(trade)

                self.current_profit = self.cash + self.owned * self.last_share_price
                print 'Total number of executed trades = {}'.format(str(self.number_of_trades))
                print 'Total net current profit = {}'.format(str(self.profit))
        return

    def _launch_tradetape(self):
        '''
        INPUT:
        OUTPUT:
        Initiates a websocket connection to the stockfighter executed trades tape for the self.ticker stock on the self.venue exchange.  Recieves the trade and checks to see if it resulted from a self.account trade, if so add to the self.
        '''
        url = 'wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/executions/stocks/{}'.format(self.account, self.venue, self.ticker)

        print 'Launching tradetape now.'
        while 1:
            trade = 0
            try:
                trade = ws.recv()
                print trade.json()
                self.trade_queue.put(trade)
            except:
                ws = websocket.create_connection(url)
            print trade
        return

    def _launch_tickertape(self):
        '''
        INPUT:
        OUTPUT:
        Initiates a websocket connection to the stockfighter tickertape for the self.ticker stock on the self.venue exchange.  Recieves the quote objects and stores them in a queue (after deleting the quote currently in the queue).  Thus is designed to maintain the queue with only the most recent quote in it.  It is meant to be run inside a Thread object.
        '''
        url = 'wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/tickertape/stocks/{}'.format(self.account, self.venue, self.ticker)
        print 'Launching tickertape now.'
        while 1:
            try:
                tick = ws.recv()
                with self.quote_queue.mutex:
                    self.quote_queue.queue.clear()
                self.quote_queue.put(tick)
            except:
                ws = websocket.create_connection(url)
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


if __name__ == '__main__':
    market = MakeMarket()
    market.make_market()
