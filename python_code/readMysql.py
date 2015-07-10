#!/usr/bin/python
##
## Script to read the last temperature and humidity readings from a MySQL database
##
import sys
import MySQLdb

def main(host, db, user, passwd, logging, sql_retries, sql_timeout):
    logging.debug('Reading MySQL database next ...')
    connection = MySQLdb.connect(host,user,passwd,db)
    cursor=connection.cursor()
    sql = """SELECT Temperature, Humidity FROM TempHumid ORDER BY ComputerTime DESC LIMIT 1""" 
    success = False
    attempts = 0
    while attempts < sql_retries and not success:
        try:
            cursor.execute(sql)
            data = cursor.fetchall()
            for row in data :
                temp = row[0]
                humid = row[1]
                oldtemp = float(temp)
                oldhumid = float(humid)
            logging.debug('The MySQL database was successfully read.')
            connection.commit()
            cursor.close()
            logging.debug('The previous temperature was: {0}C and the previous humidity was {1}%'.format(oldtemp, oldhumid))
            success = True
        except MySQLdb.Error, e:
            logging.warn('The MySQL database could not be read and returned the following error %d: %s', (e.args[0], e.args[1]))
            attempts += 1
            if attempts == sql_retries:
                logging.error('All configured attempts to read the MySQL database have failed. We are going to skip this attempt.')
            time.sleep(sql_interval)
    return oldtemp, oldhumid
