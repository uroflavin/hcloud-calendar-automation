from hcloud import Client
import hcloud_automation
import config
import hcloud_calendar
import time
import os

import logging

logging.basicConfig(filename='error.log',
                    level=logging.DEBUG,
                    format='[%(filename)s:%(lineno)s - %(funcName)20s() ] %(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Application")

logger.info("start processing...")
logger.info("working-directory is " + os.getcwd())

print("start processing...")
print("working-directory is " + os.getcwd())

client = Client(token=config.API_TOKEN, poll_interval=config.HCLOUD_POOL_INTERVAL)

# get server-state during Start
server_is_running, server_is_running_as = hcloud_automation.first_server_is_running_or_starting(client, snapshot_token=config.IMAGE_TOKEN)

try:
    while True:

        ical_data = hcloud_calendar.get_ical_data(url=config.ICAL_URL, token=config.IMAGE_TOKEN)

        grid_datetime, grid_timeslice, grid_server_type = hcloud_calendar.get_datetime_and_timeslice_grid_for_now(
            ical_data=ical_data,
            timeslice_grid_interval=config.TIMESLICE_GRID_INTERVAL,
            start_advanced_time=config.START_ADVANCED_TIME,
            end_lag_time=config.END_LAG_TIME,
            timezone_name=config.TIMEZONE_NAME)

        server_should_run, server_should_run_as = hcloud_calendar.check_should_run_now(grid_datetime=grid_datetime,
                                                                 grid_timeslice=grid_timeslice,
                                                                 grid_server_type=grid_server_type,
                                                                 timeslice_grid_interval=config.TIMESLICE_GRID_INTERVAL)

        logger.debug("server_should_run: " + str(server_should_run))
        logger.debug("server_is_running: " + str(server_is_running))
        logger.debug("server_should_run_as: " + str(server_should_run_as))
        logger.debug('server_is_running_as ' + server_is_running_as)

        if server_should_run:
            if not server_is_running:
                server_is_running, server_is_running_as = hcloud_automation.first_server_is_running_or_starting(client, snapshot_token=config.IMAGE_TOKEN)

                if server_is_running:
                    logger.debug("'" + config.IMAGE_TOKEN + "' should run now, and it IS running")
                    logger.debug("'" + config.IMAGE_TOKEN + "' Action: NONE")
                else:
                    logger.info("'" + config.IMAGE_TOKEN + "' should run now, but it IS NOT running")
                    logger.info("'" + config.IMAGE_TOKEN + "' Action: START Server...")
                    logger.info(hcloud_automation.create_server_from_snapshot(client, snapshot_token=config.IMAGE_TOKEN, override_server_type=server_should_run_as))
                    server_is_running, server_is_running_as = hcloud_automation.first_server_is_running_or_starting(
                        client, snapshot_token=config.IMAGE_TOKEN)
            else:
                logger.debug("'" + config.IMAGE_TOKEN + "' should run now, and it IS running")
                logger.debug("'" + config.IMAGE_TOKEN + "' Action: NONE")

        elif not server_should_run:
            if server_is_running:
                server_is_running, server_is_running_as = hcloud_automation.first_server_is_running_or_starting(client, snapshot_token=config.IMAGE_TOKEN)

                if server_is_running:
                    logger.info("'" + config.IMAGE_TOKEN + "' should NOT run now, but it IS running")
                    logger.info("'" + config.IMAGE_TOKEN + "' Action: DESTROY Server")

                    logger.info(hcloud_automation.destroy_first_server(client=client, snapshot_token=config.IMAGE_TOKEN))
                    server_is_running = False
                    server_is_running_as = ''

                else:
                    logger.debug("'" + config.IMAGE_TOKEN + "' should NOT run now and it IS NOT running")
                    logger.debug("'" + config.IMAGE_TOKEN + "' Action: NONE")
            else:
                logger.debug("'" + config.IMAGE_TOKEN + "' should NOT run now and it IS NOT running")
                logger.debug("'" + config.IMAGE_TOKEN + "' Action: NONE")
        else:
            logger.error("Panic")

        logger.debug("'" + config.IMAGE_TOKEN + "' wait 60 seconds...")
        time.sleep(60)

except SystemExit:
    logger.info("stopped processing")
    print("stopped.")

except KeyboardInterrupt:
    logger.info("stopped processing")
    print("stopped.")

except:
    logger.error("Something during processing went wrong")
