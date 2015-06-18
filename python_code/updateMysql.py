#!/usr/bin/python
##
## Script to import the temperature and humidity into a MySQL database
##
import sys
import MySQLdb

def main(temp, humid, host, db, user, passwd, logging):
    logging.debug('Temp = {0} *C, Hum = {1} %'.format(temp, humid))
    logging.debug('Updating MySQL database next ...')
    connection = MySQLdb.connect(host,user,passwd,db)
    cursor=connection.cursor()
    sqltemp=format(temp, '5.1f')
    sqlhumid=format(humid, '5.1f')
    logging.info('Temperature: {0}*C Humidity: {1}% ... updating to MySQL database'.format(sqltemp, sqlhumid))
    sql = """INSERT INTO TempHumid (ComputerTime, Temperature, Humidity, id) VALUES (unix_timestamp(now()), %s, %s, NULL)""" 
    args = (sqltemp, sqlhumid)
    cursor.execute(sql, args)
    connection.commit()
    cursor.close()
    return 0
