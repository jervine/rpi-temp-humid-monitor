# rpi-temp-humid-monitor
Raspberry Pi temperature humidity monitor

This is my implementation of making a Raspberry Pi powered temperature and humidity monitor. The original instructions that I followed were created by wpnsmith at [the instructables website](http://www.instructables.com/id/Raspberry-Pi-Temperature-Humidity-Network-Monitor/)

In this repository are my copies of the th.c code, a thd init script, and two files for creating a Google Chart graph rather than the python based GraphTH.py using matplotlib that wpnsmith used.

The th.c code was modified so that a forth column in MySQL is used (an auto incrementing id - probably not strictly necessary as the ComputerTime entry is incrementing anyway), as well as having th detect if an incorrect temperature/humidity reading has been made (by checking against the previously recorded value) and silently not adding this to the MySQL database if it is seen to be a big change.

Using a thd init script means that we don't need to modify /etc/rc.local - which is useful for me as this file is used by other projects and can be overwritten at times.

## UPDATED - 19 June 2015
The updateMysql.py script has been updated to provide a method of retrying failed MySQL updates. Primarily this was added so that when the server is booted up, the daemon version of the code can retry a number of times before giving up, as the MySQL server will not necessarily have finished starting up.

An updated thMonitord init script has been added, and the temp-humid-read-loop and temp-humid-read-single scripts have been altered so that they are currently hardcoded to use a configuration file called /etc/thMonitor.conf


## UPDATED - 18 June 2015
There are now two python scripts (with logging added rather than printing to stdout)

 - temp-humid-read-loop.py - this code should loop and run the temperature/humidity readind every 60 seconds. I have tried to add code to ensure that this loops every 60 seconds regardless of how long the actual reading takes. Due to occasional reading errors, the function to read temperature and humidity can vary in length - dependent upon the timeout and number of retries conifgured. The code hsould time the length of the sensorRead function and subtract this time from the configured reading interval. Tests have shown this is reasonably accurate but some drift has still been observed.

 - temp-humid-python-single.py - this code is a simplified python script taken from the looping script. The looping logic has been removed, and a single pass is made reading the temperature and humidity readings. Any errors from a reading during this single pass are retried according to the timeout and retries configured though - so a single read should succeed. This script can be put into a cron job to run on a regularly scheduled basis, which might be less prone to drift than the looped version.

 - updateMysql.py - this code has been cleaned up so that it logs to the logfile rather than to stdout by default.


## UPDATED - 17 June 2015
Looking to replace the C code with a python script that takes a configuration file. Added here:

 - temp-humid-read-loop.py - python code to continuously loop and read the temperature and humidity settings

 - updateMysql.py - python code called by the loop script to update the MySQL database

 - temphumid.conf - sample configuration file to be used with the python script

 - dhtreader.so - binary shared object file. This has been created from [http://www.airspayce.com/mikem/bcm2835/](http://www.airspayce.com/mikem/bcm2835/)

###Please note this updated python code was heavily inspired by the work done by Adafruit here:###
[https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/tree/master/Adafruit_DHT_Driver_Python](https://github.com/adafruit/Adafruit-Raspberry-Pi-Python-Code/tree/master/Adafruit_DHT_Driver_Python)

