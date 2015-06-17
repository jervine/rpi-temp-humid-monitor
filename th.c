/*
 * th.c  capture Temperature and Humidity readings, write them to sql database
 *      https://projects.drogon.net/raspberry-pi/wiringpi/

rev 1.0 12/01/2013 WPNS built from Gordon Hendersen's rht03.c
rev 1.1 12/01/2013 WPNS don't retry, takes too long
rev 1.2 12/01/2013 WPNS allow one retry after 3-second delay
rev 1.3 12/01/2013 WPNS make cycle time variable
rev 1.4 12/01/2013 WPNS add mysql stuff in
rev 1.5 12/01/2013 WPNS do 60 second cycle, cleanup, trial run
rev 1.6 12/01/2013 WPNS clean up output format
rev 1.7 12/02/2013 WPNS allow more retries, minor cleanups
rev 1.79 12/04/2013 WPNS release to instructables
rev 1.8 01/06/2015 JDE updated code to try and drop anomolous temperature humidity readings before hitting the database
rev 1.9 04/06/2015 JDE updated to try and read MySQL configuration from /etc/th.conf file rather than hard coding it
rev 1.10 11/06/2015 JDE updated to remove echoing the config options to the th.log file

 */

#include <stdio.h>

#include <wiringPi.h>
#include <maxdetect.h>
#include <time.h>

#include <libconfig.h>

#include <mysql/mysql.h>

#define RHT03_PIN       7
#define CYCLETIME      60
#define RETRIES         3

void finish_with_error(MYSQL *con)
{
  fprintf(stderr, "%s\n", mysql_error(con));
  mysql_close(con);
  exit(1);
}

int main()
{
    config_t cfg;               /*Returns all parameters in this structure */
    config_setting_t *setting;
    const char *str1, *sqlServer, *databaseName, *username, *password;

    char *config_file_name = "/etc/th.conf";

    int temp, rh, oldtemp, difftemp ;       // temperature and relative humidity readings
    int loop;                               // how many times through the loop?
    time_t oldtime,newtime;                 // when did we last take a reading?

    char SQLstring[64];                     // string to send to SQL engine
    char TimeString[64];                    // formatted time
    time_t rawtime;
    struct tm * timeinfo;

    int status;                             // how did the read go?

    /*Initialization */
    config_init(&cfg);

    /* Read the file. If there is an error, report it and exit. */
    if (!config_read_file(&cfg, config_file_name))
    {
        printf("\n%s:%d - %s", config_error_file(&cfg), config_error_line(&cfg), config_error_text(&cfg));
        config_destroy(&cfg);
        return -1;
    }

    /* Get the configuration file name. */
    if (config_lookup_string(&cfg, "filename", &str1))
        printf("\nFile Type: %s", str1);
    else
        printf("\nNo 'filename' setting in configuration file.");

    /*Read the parameter group*/
    setting = config_lookup(&cfg, "params");
    if (setting != NULL)
    {
        /*Read the server*/
        if (config_setting_lookup_string(setting, "sqlServer", &sqlServer));
        else
            printf("\nERROR: No 'sqlServer' setting in configuration file.");

        /*Read the database*/
        if (config_setting_lookup_string(setting, "databaseName", &databaseName));
        else
            printf("\nERROR: No 'databaseName' setting in configuration file.");

        /*Read the username*/
        if (config_setting_lookup_string(setting, "username", &username));
        else
            printf("\nERROR: No 'username' setting in configuration file.");

        /*Read the password*/
        if (config_setting_lookup_string(setting, "password", &password));
        else
            printf("\nERROR: No 'password' setting in configuration file.");

        printf("\n");
    }

/*    config_destroy(&cfg); */

    /*MYSQL *con = mysql_init(NULL);
    if (con == NULL) finish_with_error(con);
    if (mysql_real_connect(con, sqlServer, username, password, databaseName, 0, NULL, 0) == NULL) finish_with_error(con);
    sprintf(SQLstring,"SELECT ComputerTime, Temperature, Humidity FROM TempHumid ORDER BY id DESC LIMIT 1");
    if (mysql_query(con, SQLstring)) finish_with_error(con);
    MYSQL_RES *result = mysql_store_result(con);
    if (result == NULL)
    {
        finish_with_error(con);
    }

    int num_fields = mysql_num_fields(result);
    MYSQL_ROW row;

    row = mysql_fetch_row(result);
    for(int i = 0; i < num_fields; i++)
    {
          printf("%s ", row[i] ? row[i] : "NULL");
    }
    printf("\n"); */

    /* THIS IS WHERE THE Temperautre humidity monitoring Code starts - really untidy and needs tidying up */

    temp = rh = loop = 0 ;
    oldtime = (int)time(NULL);

    wiringPiSetup () ;
    piHiPri       (55) ;

    printf("th.c rev 1.10 11/06/2015 JDE %sCycle time: %i seconds, %i retries\n",ctime(&oldtime),CYCLETIME,RETRIES);
    fflush(stdout);

    MYSQL *con = mysql_init(NULL);

    if (con == NULL) finish_with_error(con);

    if (mysql_real_connect(con, sqlServer, username, password, databaseName, 0, NULL, 0) == NULL) finish_with_error(con);

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

        fflush(stdout);
        oldtime = newtime;
        difftemp = temp - oldtemp;

        printf("Current Temp: %5.1f, Previous Temp: %5.1f, Temperature Difference: %5.1fC\n",(temp / 10.0),(oldtemp / 10.0),(difftemp / 10.0)) ;
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

    config_destroy(&cfg);
}
