/*
 * th.c  capture Temperature and Humidity readings, write them to sql database
 *	https://projects.drogon.net/raspberry-pi/wiringpi/

rev 1.0 12/01/2013 WPNS built from Gordon Hendersen's rht03.c
rev 1.1 12/01/2013 WPNS don't retry, takes too long
rev 1.2 12/01/2013 WPNS allow one retry after 3-second delay
rev 1.3 12/01/2013 WPNS make cycle time variable
rev 1.4 12/01/2013 WPNS add mysql stuff in
rev 1.5 12/01/2013 WPNS do 60 second cycle, cleanup, trial run
rev 1.6 12/01/2013 WPNS clean up output format
rev 1.7 12/02/2013 WPNS allow more retries, minor cleanups
rev 1.79 12/04/2013 WPNS release to instructables
rev 1.80 03/06/2015 JDE Added code to drop entries if more than 10C difference calculated.

 */

#include <stdio.h>

#include <wiringPi.h>
#include <maxdetect.h>
#include <time.h>

#include <mysql/mysql.h>

#define	RHT03_PIN	7
#define CYCLETIME      60
#define RETRIES         3

void finish_with_error(MYSQL *con)
{
  fprintf(stderr, "%s\n", mysql_error(con));
  mysql_close(con);
  exit(1);
}

/*
 ***********************************************************************
 * The main program
 ***********************************************************************
 */

int main (void)
{
  int temp, rh, oldtemp, difftemp ;       // temperature and relative humidity readings
  int loop;                               // how many times through the loop?
  time_t oldtime,newtime;                 // when did we last take a reading?
  //  int deltime;                   // how many seconds ago was that?

  char SQLstring[64];                     // string to send to SQL engine
  char TimeString[64];                    // formatted time
  time_t rawtime;
  struct tm * timeinfo;

  int status;                             // how did the read go?

  temp = rh = loop = 0 ;
  oldtime = (int)time(NULL);

  wiringPiSetup () ;
  piHiPri       (55) ;

  printf("rh.c rev 1.79 12/04/2013 WPNS %sCycle time: %i seconds, %i retries\n",ctime(&oldtime),CYCLETIME,RETRIES);
  fflush(stdout);

  MYSQL *con = mysql_init(NULL);

  if (con == NULL) finish_with_error(con);

  if (mysql_real_connect(con, "localhost", "USERNAME", "PASSWORD", 
			 "Monitoring", 0, NULL, 0) == NULL) finish_with_error(con);

  // wait for an interval to start and end
  printf("Sync to cycletime...");
  fflush(stdout);
  while ((((int)time(NULL))%CYCLETIME)) delay(100);
  oldtime = (int)time(NULL);
  oldtemp = 500;
  while (!(((int)time(NULL))%CYCLETIME)) delay(100);
  printf("\n");
  fflush(stdout);

  for (;;)
    {
      // wait for an interval to start
      while ((((int)time(NULL))%CYCLETIME)) delay(100);

/*****************************************************************/

      // read new data
      temp = rh = -1;
      loop=RETRIES;

      status = readRHT03 (RHT03_PIN, &temp, &rh);
      while ((!status) && loop--)
	{
	  printf("-Retry-");
	  fflush(stdout);
	  delay(3000);
	  status = readRHT03 (RHT03_PIN, &temp, &rh);
	}

      newtime = (int)time(NULL);
      //      deltime = newtime-oldtime;
      time(&rawtime);
      timeinfo = localtime (&rawtime);
      strftime (TimeString,64,"%F %T",timeinfo);

      printf ("%s  Temp: %5.1f, RH: %5.1f%%\n", TimeString, temp / 10.0, rh / 10.0) ;
      fflush(stdout);
      oldtime = newtime;
      difftemp = temp - oldtemp;

      printf("Current Temp: %5.1f, Previous Temp: %5.1f, Temperature Difference: %5.1fC\n",(temp / 10.0),(oldtemp / 10.0),(difftemp / 10.0)) ;
      // The line above is really for debugging - it notes the temperature difference between the current and previous readings.
      // The readings are not added to the database if there is more than 10C between readings.
      if (temp > oldtemp && difftemp > 100) {
            printf("Damn ... the sensor returned a bad reading!\n");
      }
      else {
            sprintf(SQLstring,"INSERT INTO TempHumid VALUES(unix_timestamp(now()),%5.1f,%5.1f,NULL)",(temp / 10.0),(rh / 10.0));
            if (mysql_query(con, SQLstring)) finish_with_error(con);
            oldtemp = temp;
      }

/*****************************************************************/

      // wait for the rest of that interval to finish
      while (!(((int)time(NULL))%CYCLETIME)) delay(100);

    }
  
  return 0 ;
}
