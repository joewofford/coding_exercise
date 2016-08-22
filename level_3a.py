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
#The maximum depth, in either asks or bids, at which the market making algorythm will stop submitting new trades, and cancel any existing open trades.
MAX_DEPTH = 10000

class MakeMarketCarefully(object):
    '''
    A class designed to execute market-making activity on the stockfighter website in the dueling_bulldozers game (i.e. two hedgefunders having a pissing contest over some equally sketchball company...).
    '''
    def __init__(self, target=250000, min_trade=20, max_trade=100, owned=0):
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
        self.max_trate = max_trade
        self.owned = owned

    def test(self):
        b_chrome = self._login()
        self._initiate_market(b_chrome)
        self._parse_trade_info(b_chrome)
        self._get_venue()
        return

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
    market = MakeMarketCarefully()
    market.test()
