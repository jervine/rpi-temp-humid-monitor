#/usr/bin/env python
# -*- coding:utf-8 -*-

import sys
import dhtreader
import updateMysql
import ConfigParser
import time
from time import strftime
from threading import Timer,Thread,Event
import logging
from datetime import datetime
from datetime import timedelta

oldtemp = "NULL"
oldhumid = "NULL"

def exec_every_n_seconds(n,f,*args):
    waitInterval = timedelta(seconds=n)
    logging.debug('We should read the sensor every {0} seconds'.format(waitInterval))
    duration=f(*args)
    offset = waitInterval - duration
    logging.debug('Running the loop again in {0} seconds (printed as datetime)'.format(offset))
    offset2 = offset.total_seconds()
    logging.debug('Running the loop again in {0} seconds (printed as float)'.format(offset2))
    while 1:
        logging.debug('We are in the loop now ...')
        initTime=time.time()
        logging.debug('Start time is {0}'.format(initTime))
        #time.sleep(offset2)
        logging.debug('We are about to run the sensor read again')
        duration=f(*args)
        offset2 = (60.0 - (time.time() - initTime))
        time.sleep(60.0 - ((time.time() - initTime) % 60.0))
        logging.debug('Duration of sequence was: {0}'.format(duration)) 
        offset = waitInterval - duration
        logging.debug('Running the loop again in {0} seconds (printed as dateime)'.format(offset))       
        #offset2 = offset.total_seconds()
        logging.debug('Running the loop again in {0} seconds (printed as float)'.format(offset2))

def sensorRead(hwtype, pin, retries, timeout, maxtemp, mintemp, tempdiff, maxhumid, minhumid, humiddiff):
    global oldtemp
    global oldhumid
    startTime=datetime.now()
    logging.debug('This round of results started at {0}'.format(startTime))
    for num in range(retries):
        try:
            t, h = dhtreader.read(dev_type, dhtpin)
        except:
            if ((num + 1) < retries):
                logging.warning('Exception detected! We will retry. Loop number: %d', num)
                time.sleep(timeout)
            else:
                logging.error('Exception detected - we are out of retries. Skipping the measurement in this cycle.')
        else:
            if t and h:
                logging.debug('Temperature and humidity read as {0} and {1}'.format(t, h))
                logging.debug('Temperature and Humidity differences allowed: {0} and {1}'.format(tempdiff, humiddiff))
                if (oldtemp != "NULL") and ((t - oldtemp < tempdiff) or (oldtemp - t < tempdiff)) and ((h - oldhumid < humiddiff) or (oldhumid - h < humiddiff)):
                    logging.debug('Current temperature close enough to previous temperature and previous temperature is not NULL, it is: %s', oldtemp)
                    logging.debug('Current humidity close enough to previous humidity and previous humidity is not NULL, it is: %s', oldhumid)
                if (t < maxtemp) and (t > mintemp) and (h < maxhumid) and (h > minhumid):
                    logging.debug('Temperature is less than {0} and greater than {1}, humidity is less than {2} and greater than {3}'.format(maxtemp,mintemp,maxhumid,minhumid))
                    updateMysql.main(t, h, host, db, username, password, logging, sql_retries, sql_timeout)
                    oldtemp=t
                    oldhumid=h
                    break
                else:
                    logging.error('Temperature {0} or humidity {1} is outside of allowable values - error! Check your configuration.'.format(t, h))
            else:
                    logging.warning('Failed to read from sensor, maybe try again?')
    endTime=datetime.now()
    logging.debug('This round of results ended at {0}'.format(endTime))
    duration = endTime - startTime
    logging.debug('This round of results took {0} to complete'.format(duration))
    return duration

DHT11 = 11
DHT22 = 22
AM2302 = 22

config = ConfigParser.ConfigParser()
config.read('/etc/thMonitor.conf')
hwtype=config.get('hardware', 'DHT')
pin=config.get('hardware', 'PIN')
retries=int(config.get('software', 'retries'))
timeout=int(config.get('software', 'timeout'))
interval=int(config.get('software', 'interval'))
maxtemp=int(config.get('software', 'maxtemp'))
mintemp=int(config.get('software', 'mintemp'))
tempdiff=int(config.get('software', 'tempdiff'))
maxhumid=int(config.get('software', 'maxhumid'))
minhumid=int(config.get('software', 'minhumid'))
humiddiff=int(config.get('software', 'humiddiff'))
logfile=(config.get('software', 'logfile'))
loglevel=(config.get('software', 'loglevel'))
host=(config.get('database', 'host'))
db=(config.get('database', 'db'))
username=(config.get('database', 'username'))
password=(config.get('database', 'password'))
sql_retries=int((config.get('database', 'sql_retries')))
sql_timeout=(config.get('database', 'sql_timeout'))


if loglevel == "debug":
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
elif loglevel == "info":    
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
elif loglevel == "warn":
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.WARNING)
elif loglevel == "error":
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.ERROR)
else:
    logging.basicConfig(filename = logfile, format='%(asctime)s %(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.CRITICAL)

dhtreader.init()

dev_type = None
if hwtype == "11":
    dev_type = DHT11
    logging.info('Configured to use DHT11 device')
elif hwtype == "22":
    dev_type = DHT22
    logging.info('Configured to use DHT22 device')
elif hwtype == "2302":
    dev_type = AM2302
    logging.info('Configured to use AM2303 device')
else:
    logging.warn('Invalid hardware type, only DHT11, DHT22 and AM 2302 are supported for now.!')
    sys.exit(3)

dhtpin = int(pin)
if dhtpin <= 0:
    logging.warn("Invalid GPIO pin#, correct your configuration file")
    sys.exit(3)

logging.info("using pin #{0}".format(dhtpin))
logging.info('Multiple (infinte looped)  run temperature and humidity reading. [version: 1.0, Jonathan Ervine, 2015-06-17]')

logging.debug("About to enter infinite loop")
exec_every_n_seconds(60,sensorRead,hwtype,pin,retries,timeout,maxtemp,mintemp,tempdiff,maxhumid,minhumid,humiddiff)
