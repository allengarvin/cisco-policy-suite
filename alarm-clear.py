#!/usr/bin/python

# Author: "Allen Garvin" <algarvin@cisco.com>
# The default component_alarm_reports.py is clumsy to use.
# This is easy to use!
# To do: use the mongo authentication when it's in place.

# Version: 0.2 2019-08-14

import sys
import os
import argparse
import time

try:
    import pymongo
    from  pymongo import *
except ImportError:
    print "pymongo module is not found. Run from pcrfclient?"
    sys.exit(1)

sys.path.append('/var/qps/bin/support/mongo')
sys.path.append('/var/qps/bin/install/current/scripts/modules/')

from check_mongodb import *
import mongo_repl_set
from mongo_repl_set import ParseMongoCfg
from mongo_auth import mongoAuthenticate

def get_cluster_name():
    try:
        fd = open("/etc/broadhop/qns.conf")
    except:
        print("/etc/broadhop/qns.conf: unable to open. Is this a CPS VM?")
        sys.exit(1)
    cluster = False
    for line in fd:
        # Yeah, there's a new line in this, because they didn't do a strip().
        # I filed https://bst.cloudapps.cisco.com/bugsearch/bug/CSCvq23148/ but it got junked.
        if "com.broadhop.run.clusterId" in line:
            cluster = line.split("=")[1]

    if not cluster:
       cluster = "cluster-1\n"

    return cluster

def get_admin_db():
    mongo_cfg = ParseMongoCfg("/dev/null").parse_mongo_cfg()
    for repl_set in mongo_cfg:
        if repl_set.set_id == 'ADMIN':
            host = repl_set.members[0].split(":")[0]
            port = int(repl_set.members[0].split(":")[1])
            break
    return (host, port)

def connect_admin(admin_db_host, admin_db_port):
    return pymongo.MongoClient(host=admin_db_host, port=admin_db_port)

def main(args):
    cluster = get_cluster_name()
    if args.admin:
        if ":" not in args.admin or args.admin.count(":") != 1:
            print("Error: -m/--admin arg format: host:port")
            sys.exit(1)
        admin_db_host, admin_db_port = args.admin.split(":")
        if not admin_db_port.isdigit():
            print("Error: -m/--admin port is not an int ({0})".format(admin_db_port))
            sys.exit(1)
        admin_db_port = int(admin_db_port)
    else:
        admin_db_host, admin_db_port = get_admin_db()
    admin_db = connect_admin(admin_db_host, admin_db_port)

    if "cpsAlarms_{0}".format(cluster) not in admin_db.database_names():
        print("Unable to find alarming database (cpsAlarms_{0}) in Admin DB instance ({1}:{2})".format(cluster.rstrip(), admin_db_host, admin_db_port))
        sys.exit(1)
    admin_db = admin_db["cpsAlarms_{0}".format(cluster)]
    if "cpsComponentAlarms" not in admin_db.collection_names():
        print("Unable to find cpsComponentAlarms in Admin DB instance/cpsAlarms db")
        sys.exit(1)
    admin_db = admin_db["cpsComponentAlarms"]

    query = {}
    if args.info:
        query["info"] = args.info
    if args.facility:
        query["facility"] = args.facility
    if args.name:
        query["name"] = args.name
    if args.event_host:
        query["event_host"] = args.event_host
    if args.time:
        query["insertTime"] = args.time
    if args.date:
        query["date"] = args.date
    if args.severity:
        query["severity"] = args.severity
    if args.remove and len(query) == 0:
        print("To remove all alerts you must specify -a/--all")
        sys.exit(1)

    if not args.remove:
        flag = False
        for row in admin_db.find(query):
            flag = True
            row["time"] = int(row["insertTime"])
            del row["insertTime"]
            del row["_id"]

            components = list()
            for k in sorted(row.keys()):
                components.append("{0}={1}".format(k, row[k]))
            print(" ".join(components))
        if flag == False:
            print("No alerts found.")
    else:
        ret_value = admin_db.delete_many(query)
        print("{0} alert{1} deleted.".format(ret_value.deleted_count, "s" if ret_value.deleted_count != 1 else ""))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="List/Clear Platform alarms from CPS")
    ap.add_argument("-i", "--info", help="Filter on 'info' field")
    ap.add_argument("-e", "--event_host", help="Filter on 'event_host' field")
    ap.add_argument("-f", "--facility", help="Filter on 'facility' field")
    ap.add_argument("-n", "--name", help="Filter on 'name' field")
    ap.add_argument("-m", "--admin", help="Admin mongo instance to use (format: host:port)")
    ap.add_argument("-s", "--severity", help="Filter on 'severity' field")
    ap.add_argument("-t", "--time", help="Filter on 'time' (insertTime) field", type=int)
    ap.add_argument("-d", "--date", help="Filter on 'date' field")
    ap.add_argument("-a", "--all", help="No filter. Show or display all", action="store_true")
    ap.add_argument("-r", "--remove", help="Remove records [based on filter, or with --all]", action="store_true")

    args = ap.parse_args()

    main(args)

