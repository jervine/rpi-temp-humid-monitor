#!/usr/bin/python
##
## Script to import the temperature and humidity into a MySQL database
##
import sys
import MySQLdb

def main(temp, humid, host, db, user, passwd, logging, sql_retries, sql_timeout):
    logging.debug('Temp = {0} *C, Hum = {1} %'.format(temp, humid))
    logging.debug('Updating MySQL database next ...')
    connection = MySQLdb.connect(host,user,passwd,db)
    cursor=connection.cursor()
    sqltemp=format(temp, '5.1f')
    sqlhumid=format(humid, '5.1f')
    logging.info('Temperature: {0}*C Humidity: {1}% ... updating to MySQL database'.format(sqltemp, sqlhumid))
    sql = """INSERT INTO TempHumid (ComputerTime, Temperature, Humidity, id) VALUES (unix_timestamp(now()), %s, %s, NULL)""" 
    args = (sqltemp, sqlhumid)

    success = False
    attempts = 0
    while attempts < sql_retries and not success:
        try:
            cursor.execute(sql, args)
            connection.commit()
            cursor.close()
            success = True
            logging.debug('The MySQL database was successfully updated.')
        except MySQLdb.Error, e:
            logging.warn('The MySQL database could not be updated and returned the following error %d: %s', (e.args[0], e.args[1]))
            attempts += 1
            if attempts == sql_retries:
                logging.error('All configured attempts to update the MySQL database have failed. We are going to skip this attempt.')
            time.sleep(sql_interval)
    return 0
