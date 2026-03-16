#!/usr/bin/python

# agg-stats work-around script for CSCva97068
# Rare issue only affecting CPS 7 through 10. Set this as a cron.

# The issue seems to be that collectd is not releasing its file descriptor during the nightly
# restart at 1am. It may happen during the rotation if that falls directly on the restart. So,
# collectd continues writing to the agg-stats.1.csv, which is rotated, while the main agg-stats
# file sits unappended. Because the logback.xml rotation threshold only depends on the agg-stats 0
# file, it never rotates. Furthermore, the load increases as the 5-minute script that parses all
# the agg-stats grows further and further behind (I filed a cdet on that as well, to get a lock
# added to prevent multiple runs.
#
# This just fills the agg-stats.0.csv with white space sufficient to force it to rotate. After that
# they will rotate fine and the file descriptors open the correct place. Make this a cron set to run
# maybe 30 minutes or an hour after the collectd restart.

# I dug through the logback rotation code a lot, can't figure out why this is occurring. 

# Author: Allen Garvin (algarvin@cisco.com)

import sys, os, datetime
import xml.etree.ElementTree as ET

LOGBACK="/etc/collectd.d/logback.xml"

LOGFILE="/var/tmp/aggstat.log"

dry_run = False

def log(mesg):
    global dry_run

    if dry_run:
        print(str(datetime.datetime.now()) + " " + mesg)
    else:
        if not "\n" in mesg:
            mesg += "\n"
        f = open(LOGFILE, "a")
        f.write(str(datetime.datetime.now()) + " " + mesg)
        f.close()

def get_logback_info(fn):
    logback = ET.parse(fn)
    root = logback.getroot()
    
    file_elem = root.find("appender/file")
    fn = file_elem.text
    
    max = root.find("appender/triggeringPolicy/maxFileSize")
    filesize = max.text
    units = filesize[-2:]
    value = int(filesize[:-2])

    if units == "KB":
        value *= 10**3
    elif units == "MB":
        value *= 10**6
    elif units == "GB":
        value *= 10**9
    elif units == "00":
        value *= 10**2

    return fn, value

def main(argv):
    global dry_run

    if len(argv) > 1:
        if argv[1] == "-d":
            dry_run = True
            print "** enabling dry run"
        else:
            print "Usage: %s [-d]" % argv[0]
            print "\t-d\tdry run (do not change anything)"
            print "\tGive no args to allow it to modify agg-stats.0.csv"
            sys.exit(1)

    if not os.path.exists(LOGBACK):
        print(LOGBACK + ": not found. Is this a pcrfclient?")
        sys.exit(1)
    
    aggstat, maxsize = get_logback_info(LOGBACK)
    if not os.path.exists(aggstat):
        print("Error: %s not found. Are aggstats being collected?" % aggstat)
        sys.exit(1)
        
    aggstat_rotated = aggstat.replace(".0.", ".1.")
    if not os.path.exists(aggstat_rotated):
        print("Error: rotated %s not found. Are aggstats being collected?" % aggstat_rotated)
        sys.exit(1)

    try:
        rot_stat = os.stat(aggstat_rotated)
    except:
        print("Error: stat() against %s failed." % aggstat_rotated)
        sys.exit(1)
    
    # normal for it to be slightly more than max size. Let's set threshold at 1.5 *
    threshold = maxsize + (maxsize / 2)
    if rot_stat.st_size < maxsize + (maxsize / 2):
        # Everything is fine
        if dry_run:
            print("** agg-stats.1.csv without normal parameters. Exiting.")
        sys.exit(0)
    
    log("================ agg-stat issue detected =====================")
    log("%s: size is %d [threshold: %d]" % (aggstat_rotated, rot_stat.st_size, maxsize))  

    # Collectd's logback is writing to agg-stat.1.csv, but it's watching the size of
    #   agg-stat.0.csv. Here we will open the latter and append maxsize's worth of whitespace
    #   to the end, to force it to rotate. 
    if dry_run:
        log("*DRY RUN*: at this point we otherwise would modify agg-stat.0.csv")
    else:
        f = open(aggstat, "a")
        f.write((" " * (maxsize + maxsize / 10)) + "\n")
        f.close()

        st = os.stat(aggstat)
        log("whitespace added to %s [it's size is now %d]" % (aggstat, st.st_size))
    log("==============================================================")
    
# To do:
# add dry run option
# dry run changes nothing, logs to the screen
if __name__ == "__main__":
    main(sys.argv)
