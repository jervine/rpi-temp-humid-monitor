#!/usr/bin/python
##
## Script to import the temperature and humidity into a MySQL database
##
import sys
import MySQLdb
#import datetime
#import time

def main(temp, humid, host, db, user, passwd):
    print('Temp = {0} *C, Hum = {1} %'.format(temp, humid))
    print('Updating MySQL database next ...')
    connection = MySQLdb.connect(host,user,passwd,db)
    cursor=connection.cursor()
    sqltemp=format(temp, '5.1f')
    sqlhumid=format(humid, '5.1f')
    print(sqltemp, sqlhumid)
    sql = """INSERT INTO TempHumid (ComputerTime, Temperature, Humidity, id) VALUES (unix_timestamp(now()), %s, %s, NULL)""" 
    args = (sqltemp, sqlhumid)
    cursor.execute(sql, args)
    connection.commit()
    cursor.close()
    return 0
