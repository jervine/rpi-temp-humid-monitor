#!/usr/bin/python
##
## Script to read the last temperature and humidity readings from a MySQL database
##
import time
import MySQLdb

NO_PREVIOUS = ('NULL', 'NULL')


def main(host, db, user, passwd, logging, sql_retries, sql_timeout):
    logging.debug('Reading MySQL database next ...')

    sql = (
        'SELECT Temperature, Humidity FROM TempHumid '
        'ORDER BY ComputerTime DESC LIMIT 1'
    )

    for attempt in range(sql_retries):
        connection = None
        try:
            connection = MySQLdb.connect(host, user, passwd, db)
            cursor = connection.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            cursor.close()

            if row is None:
                logging.info('No previous readings found in database.')
                return NO_PREVIOUS

            oldtemp = float(row[0])
            oldhumid = float(row[1])
            logging.debug(
                'Previous temperature: %sC, previous humidity: %s%%',
                oldtemp, oldhumid,
            )
            return oldtemp, oldhumid
        except MySQLdb.Error as e:
            logging.warn(
                'MySQL read failed (attempt %d/%d): %d: %s',
                attempt + 1, sql_retries, e.args[0], e.args[1],
            )
            if attempt + 1 >= sql_retries:
                logging.error(
                    'All configured attempts to read the MySQL database have failed.'
                )
                return NO_PREVIOUS
            time.sleep(sql_timeout)
        finally:
            if connection is not None:
                connection.close()

    return NO_PREVIOUS
