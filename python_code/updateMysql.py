#!/usr/bin/python
##
## Script to import the temperature and humidity into a MySQL database
##
import time
import MySQLdb


def main(temp, humid, host, db, user, passwd, logging, sql_retries, sql_timeout):
    logging.debug('Temp = %s *C, Hum = %s %%', temp, humid)
    logging.debug('Updating MySQL database next ...')

    sql = (
        'INSERT INTO TempHumid (ComputerTime, Temperature, Humidity, id) '
        'VALUES (unix_timestamp(now()), %s, %s, NULL)'
    )
    args = (format(temp, '5.1f'), format(humid, '5.1f'))
    logging.info(
        'Temperature: %s*C Humidity: %s%% ... updating to MySQL database',
        args[0], args[1],
    )

    for attempt in range(sql_retries):
        connection = None
        try:
            connection = MySQLdb.connect(host, user, passwd, db)
            cursor = connection.cursor()
            cursor.execute(sql, args)
            connection.commit()
            cursor.close()
            logging.debug('The MySQL database was successfully updated.')
            return 0
        except MySQLdb.Error as e:
            logging.warn(
                'MySQL update failed (attempt %d/%d): %d: %s',
                attempt + 1, sql_retries, e.args[0], e.args[1],
            )
            if attempt + 1 >= sql_retries:
                logging.error(
                    'All configured attempts to update the MySQL database have failed.'
                )
                return 1
            time.sleep(sql_timeout)
        finally:
            if connection is not None:
                connection.close()

    return 1
