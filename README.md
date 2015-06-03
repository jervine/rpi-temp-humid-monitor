# rpi-temp-humid-monitor
Raspberry Pi temperature humidity monitor

This is my implementation of making a Raspberry Pi powered temperature and humidity monitor. The original instructions that I followed were created by wpnsmith at (the instructables website)[http://www.instructables.com/id/Raspberry-Pi-Temperature-Humidity-Network-Monitor/]

In this repository are my copies of the th.c code, a thd init script, and two files for creating a Google Chart graph rather than the python based GraphTH.py using matplotlib that wpnsmith used.

The th.c code was modified so that a forth column in MySQL is used (an auto incrementing id - probably not strictly necessary as the ComputerTime entry is incrementing anyway), as well as having th detect if an incorrect temperature/humidity reading has been made (by checking against the previously recorded value) and silently not adding this to the MySQL database if it is seen to be a big change.

Using a thd init script means that we don't need to modify /etc/rc.local - which is useful for me as this file is used by other projects and can be overwritten at times.
