#!/usr/bin/python

# DB balance finder.
# Author: "Nate Harry <nharry@cisco.com>
# NOTE: NOT OFFICIAL CISCO SOFTWARE. No one supports this but me.

import sys, os
import argparse as AP
from datetime import datetime as DT
from pymongo import MongoClient as MC
from ConfigParser import ConfigParser as CP

log_fd = sys.stdout
debug_level = False

def timestamp():
    return DT.now().strftime("%F %T")

def log_info(msg):
    log_fd.write("{0}: INFO {1}\n".format(timestamp(), msg))

def log_warn(msg):
    log_fd.write("{0}: WARN {1}\n".format(timestamp(), msg))

def log_debug(msg):
    if debug_level:
        log_fd.write("{0}: DEBUG {1}\n".format(timestamp(), msg))

def log_fatal(msg):
    if log_fd != sys.stdout:
        log_fd.write("{0}: FATAL {1}\n".format(timestamp(), msg))
    sys.stderr.write("{0}: FATAL {1}\n".format(timestamp(), msg))
    sys.exit(1)

def setup_logging(logfile, debug):
    global debug_level, log_fd

    if debug:
        debug_level = True

    if logfile:
        try:
            log_fd = open(logfile, "w")
        except IOError as e:
            log_fatal("{0}: I/O errno {1}: {2}".format(logfile, e.errno, e.strerror))
        log_debug("{0}: opening for logging".format(logfile))

def read_mongo_config():
    cnf = CP()

    mongo_path = "/etc/broadhop/mongoConfig.cfg"
    if not os.path.isfile(mongo_path):
        log_fatal("{0}: unable to read".format(mongo_path))

    cnf.read(mongo_path)

    balance_dbs = {}
    for sec in cnf.sections():
        if "-END" in sec:
            continue
        if "BALANCE" in sec:
            db_confs = dict((a,b) for a,b in cnf.items(sec))
            if "member1" not in db_confs:
                log_fatal("{0}: no member1 in section {1}".format(mongo_path, sec))
            member1 = db_confs["member1"]
            name = db_confs["setname"]
            balance_dbs[name] = [ member1 ]
    return balance_dbs

def find_primary(host):
    try:
        c = MC(host)
    except:
        log_fatal("{0}: Unable to open mongo connection. Make sure this script is run from pcrfclient".format(host))
    master = None
    for m in c.admin.command("replSetGetStatus")["members"]:
        if m["stateStr"] == "PRIMARY":
            master = m["name"]

    if not master:
        log_fatal("{0}: Unable to find primary set member".format(host))
    log_debug("{0}: primary is {1}".format(host, master))
    return MC(master)

def build_connections(db_map):
    for k, v in db_map.iteritems():
        balance_primary = find_primary(v[0])
        db_map[k].append(balance_primary)

def sanitize(balance):
    for i in [ ":", ";" ]:
        balance = balance.replace(i, "%%%X" % ord(i))
    return balance

def reverse_sanitize(balance):
    for i in [ ":", ";" ]:
        balance = balance.replace("%%%X" % ord(i), i)
    return balance

def display_doc(balance_doc, coll, setname):
    print("DB:          mongo://{host}:{port}/{db}/{collection}".format(host=coll.database.connection.host,
        port=coll.database.connection.port, db=coll.database.name, collection=coll.name))
    print("Setname:     {0}".format(setname))
    print("Object id key:    {0}".format(balance_doc["_id"]))
    print("Subscriber Id:    {0}".format(balance_doc["subscriberId"]))
    if "accountBalances" in balance_doc:
        print("Balances:   {0}".format(balance_doc["accountBalances"]))
    if "billCycle" in balance_doc:
        print("billCycle: {0}".format(balance_doc["billCycle"]))
    if "tags" in balance_doc:
        max = -1
        for t in balance_doc["tags"]:
            parts = t.split(":")
            for p in parts:
                if len(p) > max:
                    max = len(p)
        max += 1
        print "%-*s" % (max, "TAGS")
        for t in balance_doc["tags"]:
            print("".join(map(lambda x: "%-*s" % (max, x), t.split(":"))))
    print

def find_balance(db_map, args):
    arg_count = 0

    if args.subscriberid:
        arg_count += 1
        query = { "subscriberId" : "{0}".format(args.subscriberid) }

    if arg_count != 1:
        log_fatal("Must provide exactly one search term. Use -h for help")

    foundDb = 0
    for setname, v in db_map.iteritems():
        host, db_conn = v
        for dbn in db_conn.database_names():
            if "balance_mgmt" not in dbn or "account" not in db_conn[dbn].collection_names():
                log_debug("no balance_mgmt db in {0} or no account collection in {1}".format(dbn,dbn))
                continue
            collection = db_conn[dbn]["account"]
            foundDb = 1
            log_debug("Searching {0} for {1}".format(collection, query))
            for doc in collection.find(query):
                display_doc(doc, collection, setname)
    if foundDb == 0:
        log_debug("no balance_mgmt db or no account collection found")

def main(args, ap):
    setup_logging(args.log, args.verbose)
    databases = read_mongo_config()
    build_connections(databases)
    find_balance(databases, args)


if __name__ == "__main__":
    parser = AP.ArgumentParser(description="balance finder (using mongo)")
    parser.add_argument("-l", "--log", help="Log output location (otherwise, stdout is used)")
    parser.add_argument("-v", "--verbose", help="Verbose debugging info", action="store_true")
    parser.add_argument("-su", "--subscriberid", help="search by subscriber ID")

    args = parser.parse_args()
    main(args, parser)
