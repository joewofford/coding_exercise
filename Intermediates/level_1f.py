from __future__ import division

import requests
import random
import time
import websocket
import json
import Queue

from threading import Thread
from selenium import webdriver
from datetime import datetime

#API key for the stockfighter website
AUTH = {'X-Starfighter-Authorization': '0c758ac77e1595c23756812113e730df324730e4'}

#User information for login (user specific)
USERNAME = 'joewofford'
PS = 'givepeyton#18'

#path to the chromedriver for selenium to use (machine specific)
PATH_TO_CHROMEDRIVER = '/Users/joewofford/anaconda/chromedriver'

#Parameters related to how the bulk of the trades will be performed
#How far below the customer target price the ask has to be to initiate a trade
DELTA = .96
#How long a trade will be left active (seconds)
TRADE_WINDOW = 10
#The maximum age, in seconds, of a quote to use its information to initiate a trade
MAX_QUOTE_AGE = 1
#What price to bid, relative to the current market spread (>1 will be above ask in the most recent quote, <0 will be below most recent bid)
SPREAD_SPLIT = 1.03


class Account(object):
    '''
    A class designed to execute bulk-buys on the stockfighter website in the chock_a_block game.
    '''

    def __init__(self):
        '''
        INPUT:
        OUTPUT:
        Initiates an instance of the 'Account' class object, while setting the target_price attribute to 0.
        '''
        self.target_price = 0
        return

    def block_buy(self, qty=100000, max_buy=1000, owned=0):
        '''
        INPUT:
        qty - The final number of shares self.account wishes to own (ind)
        max_buy - The maximum number of shares to purchase in any single transaction (int)
        owned - Number of shares already owned
        OUTPUT:
        The main method of the class.  First performs the web interfacing to log-in and launch the game, initiates the tickertape, then executes a series of trades of different types, initially to gain information on the market/situation, then to accumulate shares.
        '''
        self.qty = qty
        self.max_buy = max_buy
        self.owned = owned

        #Performing pre-trade setup and parsing
        b_chrome = self._login()
        self._initiate_market(b_chrome)
        self._parse_trade_info(b_chrome)
        self._get_venue()

        #Launching the tickertape through a websocket, which will communicate the quotes through the queue
        q = Queue.Queue()
        tickertape = Thread(target=self._launch_tickertape, args=(q,))
        tickertape.start()

        #Testing to see if the ticker has launched yet, if not then wait
        while q.empty():
            time.sleep(1)

        #Get the target price our customer wants to guide our later, accumulative trading
        self._extract_target_price(b_chrome)

        #Purchase the remainder of the shares our customer wants
        self._iterative_buying(q)

        print 'We have now bought {} shares of {} on account {}.'.format(self.owned, self.ticker, self.account)

        return

    def _iterative_buying(self, q):
        '''
        INPUT: Queue object containing the most recent quote from the websocket tickertape stream
        OUTPUT:
        Performs the vast bulk of the share purchases for the block buy.
        '''
        print 'Starting iterative buying...'
        while self.qty > self.owned:
            if not q.empty():
                #Getting the most current quote, and checking its quality (has all the required information fields)
                quote = json.loads(q.get())
                if all(x in quote['quote'] for x in ['bid', 'ask', 'quoteTime']):
                    #Stripping the time the quote was generated
                    q_time = datetime.strptime(quote['quote']['quoteTime'].split('.')[0],'%Y-%m-%dT%H:%M:%S')
                    #Checking the age of the quote to check it isn't too old to be reasonably accurate using the MAX_QUOTE_AGE
                    if (datetime.utcnow() - q_time).total_seconds() < MAX_QUOTE_AGE:
                        ask = quote['quote']['ask']

                        #Checking if the 'current' ask price is lower than our target price, thus initiating a trade attempt
                        if ask < (self.target_price*100):
                            bid = quote['quote']['bid']
                            #Deciding how many shares to include in the trade attempt (random size, within range)
                            buy_size = min(random.randint(1, self.max_buy), (self.qty - self.owned))

                            #Determining what our bid price should be using the SPREAD_SPLIT value
                            buy_bid = int(str(bid + (ask - bid) * SPREAD_SPLIT).split('.')[0])

                            print 'Ordering {} shares of {} at a bid of {}, out of {} left to buy.'.format(str(buy_size), self.ticker, str(buy_bid/100), str(self.qty-self.owned))

                            #Making the initial buy attempt, and repeating until it goes through
                            buy = self._single_buy(buy_size, 'limit', buy_bid)

                            while buy.status_code != requests.codes.ok:
                                buy = self._single_buy(buy_size, 'limit', buy_bid)

                            t_sent = time.time()
                            print 'Trade sent.'
                            t_id = buy.json()['id']
                            bought = self._sum_fills(self._trade_status(t_id))

                            #Checking if the full order was filled, and monitoring the status for the duraction of TRADE_WINDOW, then close the trade and add the number of shares purchased to the class attribute
                            while bought < buy_size:
                                if time.time() - t_sent > TRADE_WINDOW:
                                    self._cancel_buy(t_id)
                                    print 'Trade cancelled.'
                                    bought = self._sum_fills(self._trade_status(t_id))
                                    break
                                time.sleep(.05)
                                bought = self._sum_fills(self._trade_status(t_id))

                            self.owned = self.owned + bought
                            print 'We just bought {} shares out of an intial request of {}, giving us a total of {} currently owned.'.format(str(bought), str(buy_size), str(self.owned))

            time.sleep(.05)
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

    def _get_venue(self):
        '''
        INPUT:
        OUTPUT: Sets the self.venue attribute to the venue where the self.ticker stock is traded
        Queries the stockfighter API to determine on which venue/exchange the stock denoted by the inputed ticker is traded.  Collects a list of all venues, then iterates through and examines the list of stocks on that venue.
        '''
        print 'Getting venue now.'
        call = requests.get('https://api.stockfighter.io/ob/api/venues', headers=AUTH)
        venues = [d['venue'] for d in call.json()['venues']]

        for venue in venues:
            if self.ticker in self._get_tickers(venue):
                self.venue = venue
        return

    def _single_buy(self, qty, order_type, price=0):
        '''
        INPUT:
        qty - The number of shares to be bought (int)
        order_type - The type of order (string)
        price - The share price for the bid, if appropriate (int)
        OUTPUT: Requests post response object (includes .json() method to access data)
        Executes a single buy order for self.ticker on the self.account, at self.venue, purchasing the designated quantity of shares using the order type.
        '''
        order = {
        'account': self.account,
        'venue': self.venue,
        'stock': self.ticker,
        'qty': qty,
        'direction': 'buy',
        'price': price,
        'orderType': order_type
        }

        call = requests.post('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders'.format(self.venue, self.ticker), headers=AUTH, json=order)
        return call

    def _trade_status(self, t_id):
        '''
        INPUT: Unique (by venue) identifier of the trade
        OUTPUT: Request response object (use .json() method to access data)
        Queries the stockfighter API for the status of the trade corresponding to t_id.
        '''
        call = requests.get('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders/{}'.format(self.venue, self.ticker, t_id), headers=AUTH)
        return call

    def _cancel_buy(self, t_id):
        '''
        INPUT: Unique (by venue) identifier of the trade
        OUTPUT: Request response object (use .json() method to access data)
        Queries the stockfighter API to cancel the trade corresponding to t_id.
        '''
        call = requests.post('https://api.stockfighter.io/ob/api/venues/{}/stocks/{}/orders/{}/cancel'.format(self.venue, self.ticker, t_id), headers=AUTH)
        return call

    def _launch_tickertape(self, q):
        '''
        INPUT: Queue object
        OUTPUT:
        Initiates a websocket connection to the stockfighter tickertape for the self.ticker stock on the self.venue exchange.  Recieves the quote objects and stores them in a queue (after deleting the quote currently in the queue).  Thus is designed to maintain the queue with only the most recent quote in it.  Is meant to be run inside a Thread object.
        '''
        url="wss://api.stockfighter.io/ob/api/ws/{}/venues/{}/tickertape/stocks/{}".format(self.account, self.venue, self.ticker)
        print 'Launching tickertape now.'
        while 1:
            try:
                tick = ws.recv()
                with q.mutex:
                    q.queue.clear()
                q.put(tick)
            except:
                ws = websocket.create_connection(url)
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

    def _initiate_market(self, b_chrome):
        '''
        INPUT: Selenium webdriver for the chrome browser
        OUTPUT:
        Uses the webdriver to navigate through the post-login stockfighter webpage to initiate a 'chock_a_block' game.
        '''
        b_chrome.find_element_by_xpath('//*[@id="app"]/div/div/div/div/div[1]/div[2]/ul/li[1]/b/a').click()
        time.sleep(3)
        b_chrome.find_element_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]').click()
        time.sleep(1)
        b_chrome.find_element_by_xpath('//*[@id="wrapping"]/nav/div/ul/li[2]/ul/li[1]/a/span[1]/b').click()
        time.sleep(10)
        return

    def _parse_trade_info(self, b_chrome):
        '''
        INPUT: Selenium webdriver for the chrome browser
        OUTPUT:
        Uses the webdriver to parse the opening page of the 'chock_a_block' game for the account to be traded on (self.account), and the stock to be traded (self.ticker). It then closes the pop-up window.
        '''
        self.account = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[2]/strong[2]').text.split()[1]
        self.ticker = b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[2]/span/p[2]/em').text
        time.sleep(2)
        b_chrome.find_element_by_xpath('/html/body/div[3]/div/div[2]/div/div/div[3]/button').click()
        return

    def _parse_target_price(self, b_chrome):
        '''
        INPUT: Selenium webdriver for the chrome browser
        OUTPUT: Boolean
        Uses the webdriver to parse the 'chock_a_block' game page for the 'customer target price'. If it is able to find the target price it returns true (will only succeed once the pop-up window with the information appears), otherwise returns false.
        '''
        temp = b_chrome.find_elements_by_xpath('//*[@id="wrapping"]/div/div[1]/div/div[1]/p')
        if len(temp) == 0:
            return False
        else:
            self.target_price = float(temp[0].text.split('$')[-1][:-1])
            return True

    def _sum_fills(self, trade):
        '''
        INPUT: Requests return item corresponding to a trade status query
        OUTPUT: The total number of shares purchased thus far (int)
        Aggregates all of the fills associated with the trade, resulting in the total number of shares bought at the time of query.
        '''
        return sum([x['qty'] for x in trade.json()['fills']])

    def _extract_target_price(self, b_chrome):
        '''
        INPUT: Selenium webdriver for the chrome browser
        OUTPUT:
        Initiates small trades to instigate the stockfighter website to open the pop-up window containing the customer target price, then parse this price using the webdriver and store it as the self.target_price attribute.
        '''
        print 'Starting to try to extract target price...'
        #Make small buys to get the target price to pop up, and checking if its there yet, parse and store as attribute
        while self.target_price == 0:
            buy = self._single_buy(5, 'market')
            while buy.status_code != requests.codes.ok:
                buy = self._single_buy(5, 'market')
            t_sent = time.time()
            t_id = buy.json()['id']
            bought = self._sum_fills(self._trade_status(t_id))

            #Checking if the full order was filled, and monitoring status if not until the trade has been open for TRADE_WINDOW, then close and add the number of shares purchased to the class attribute
            while bought < 5:
                if time.time() - t_sent > TRADE_WINDOW:
                    self._cancel_buy(t_id)
                    print 'Trade cancelled.'
                    bought = self._sum_fills(self._trade_status(t_id))
                    break
                time.sleep(.1)
                bought = self._sum_fills(self._trade_status(t_id))

            self.owned = self.owned + bought
            print 'We just bought {} shares out of an intial request of {}, giving us a total of {} currently owned.'.format(str(bought), '5', str(self.owned))

            #Now pause for a bit and check if the trade desk has revealed the target price, then iterate before trading again to prod it along.
            time.sleep(1)
            for x in xrange(3):
                if self._parse_target_price(b_chrome):
                    print 'Target price = {}, ending extraction function.'.format(str(self.target_price))
                    return
                else:
                    time.sleep(10)


if __name__ == '__main__':
    acc = Account()
    acc.block_buy()
