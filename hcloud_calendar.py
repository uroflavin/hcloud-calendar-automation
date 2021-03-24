import datetime
from dateutil import tz
import icalendar
import recurring_ical_events
import urllib.request
from pathlib import Path
import logging

logging.basicConfig(filename='error.log',
                    level=logging.DEBUG,
                    format='[%(filename)s:%(lineno)s - %(funcName)20s() ] %(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Application")

def ceil(dt: datetime, interval: int) -> datetime:
    """
    Round UP the given dt-object to the given interval (in minutes)

    :param dt: datetime to round UP
    :param interval: full minutes
    :return: rounded datetime
    """
    if dt.minute % interval or dt.second:
        mod = interval - dt.minute % interval
        delta = datetime.timedelta(minutes=mod)
        e = dt + delta
        return e
    else:
        return dt


def get_datetime_and_timeslice_grid_for_now(ical_data: bytes = None, timezone_name: str = "Europe/Berlin",
                                            timeslice_grid_interval: int = 15, start_advanced_time: int = 15,
                                            end_lag_time: int = 30):
    """
    
    :param timezone_name:
    :param ical_data:
    :type timeslice_grid_interval: object
    :rtype: object
    """
    t = ""
    ''' timeslice_grid_interval is the size in minutes of the time-chunks your timeslice-grid has'''
    timezone = tz.gettz(timezone_name)
    # todo: fix static timezone to dynamic or based on config

    start_date = datetime.datetime.now(timezone).replace(second=0, microsecond=0)
    ''' start_date is always round down to nearest timeslice_grid_interval'''
    # round down to timeslice_grid_intervall
    discard_start = datetime.timedelta(minutes=start_date.minute % timeslice_grid_interval,
                                       seconds=start_date.second,
                                       microseconds=start_date.microsecond)
    start_date -= discard_start

    end_date = start_date + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    ''' end_date is: (start_date + 23 Hour + 59 Minutes + 59 Seconds)'''
    timedelta = datetime.timedelta(minutes=timeslice_grid_interval).total_seconds()
    ''' timedelta is used to init grid_datetime - it represents the number of secondes between each timeslice'''

    # Init all the grids
    grid_datetime = [x for x in range(int(start_date.timestamp()), int(end_date.timestamp()), int(timedelta))]
    ''' hold the timeinformation '''
    grid_timeslice = [False] * len(grid_datetime)
    ''' hold the run/not run information'''

    try:
        calendar = icalendar.Calendar.from_ical(ical_data)
        # todo: add timezone if calender has missing timezone info, for now, we raise an error

        events = recurring_ical_events.of(a_calendar=calendar).between(start=start_date, stop=end_date)
    except:
        raise Exception("Error during ical conversion - please check your calendar-source")

    # mark every start in timeslice
    for event in events:

        start = event["DTSTART"].dt
        if start_advanced_time > 0:
            discard = datetime.timedelta(minutes=start_advanced_time)
            start -= discard

        # Round start down to nearest grid_interval
        discard_start = datetime.timedelta(minutes=start.minute % timeslice_grid_interval,
                                           seconds=start.second,
                                           microseconds=start.microsecond)
        start -= discard_start

        end = event["DTEND"].dt
        if end_lag_time > 0:
            discard = datetime.timedelta(minutes=end_lag_time)
            end += discard

        # Round end up to nearest grid_interval
        end = ceil(end, timeslice_grid_interval)
        # find index for start
        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())
        if start_ts not in grid_datetime and end_ts not in grid_datetime:
            continue

        if start_ts in grid_datetime:
            idx_start = grid_datetime.index(start_ts)
        else:
            idx_start = 0

        # Ende bestimmen
        if end_ts in grid_datetime:
            idx_end = grid_datetime.index(end_ts)
        else:
            idx_end = len(grid_timeslice)

        # Fix for end of day, cause 00:00 is new day
        if idx_end >= len(grid_timeslice):
            idx_end = len(grid_timeslice) - 1

        # Mark event from start till end in timeslice grid
        idx = None
        for idx in range(idx_start, idx_end + 1, 1):
            grid_timeslice[idx] = True

    # TODO: write code to fix the grid in a way, if there is only one not-run-slot between two running-slots
    #   eg. 11011 -> 11111
    #   unshure if this is a good idea. adds too much complexity. if there is one fixed, maybe another is open and so on
    logger.debug("grid_datetime")
    logger.debug(grid_datetime)
    logger.debug("grid_timeslice")
    logger.debug(grid_timeslice)
    return grid_datetime, grid_timeslice


def check_should_run_now(grid_datetime, grid_timeslice, timezone_name: str = "Europe/Berlin",
                         timeslice_grid_interval: int = 15):
    """
    Check calender-grids if server should run now
    Default is False
    :raise error if grids are not or wrong initialised
    """
    if len(grid_timeslice) > 0 and len(grid_datetime) > 0:
        timezone = tz.gettz(timezone_name)
        now = datetime.datetime.now(timezone).replace(second=0, microsecond=0)
        ''' start_date is always round down to nearest timeslice_grid_interval'''
        # round down to timeslice_grid_intervall
        discard_start = datetime.timedelta(minutes=now.minute % timeslice_grid_interval)
        now -= discard_start
        now_ts = int(now.timestamp())

        if now_ts in grid_datetime:
            idx = grid_datetime.index(now_ts)
            return grid_timeslice[idx]
        else:
            return False
    else:
        logger.error("grids are not initialised or empty")
        raise Exception("Your grids are not initialised or empty")


def get_ical_data(url: str = "", token: str = None) -> bytes:
    """
    get ical data from given url

    :param url: url to the ical-data (must be public-accessable)
    :param token: some toke, to identify the cache file. should be the same as IMAGE_TOKEN
    :return: binary reprasentation of ical data
    """

    max_age = (60 * 60)  # 60 minutes * 60 seconds
    '''max_age is in seconds'''

    # Token is used to identify different cache_files
    if token == "" or token is None:
        try:
            return urllib.request.urlopen(url).read()
        except:
            logger.error("Error fetchong calendar-source")
            raise Exception("Error fetching calendar-source")
    else:
        cache_file = token + ".cache"
        ''' cache_file is stored in current directory, naming is: 'token.cache' '''
        try:
            # check if we have a local copy
            if Path(cache_file).exists():
                age = datetime.datetime.now().timestamp() - Path(cache_file).stat().st_mtime

                if age > max_age:
                    ical_string = urllib.request.urlopen(url).read()
                    Path(cache_file).write_bytes(ical_string)
                else:
                    ical_string = Path(cache_file).read_bytes()
            # no local copy
            else:
                ical_string = urllib.request.urlopen(url).read()
                Path(cache_file).write_bytes(ical_string)
            return ical_string
        except:
            logger.error("Error fetching-calendar-source")
            raise Exception("Error fetching calendar-source")

