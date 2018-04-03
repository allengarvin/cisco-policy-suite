#!/usr/bin/python

# DB session finder.
# Author: "Allen Garvin <algarvin@cisco.com>
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

    session_dbs = {}
    for sec in cnf.sections():
        if "-END" in sec:
            continue
        if "SESSION" in sec:
            db_confs = dict((a,b) for a,b in cnf.items(sec))
            if "member1" not in db_confs:
                log_fatal("{0}: no member1 in section {1}".format(mongo_path, sec))
            member1 = db_confs["member1"]
            name = db_confs["setname"]
            session_dbs[name] = [ member1 ] 
    return session_dbs

def find_primary(host):
    try:
        c = MC(host)
    except:
        fatal("{0}: Unable to open mongo connection. Make sure this script is run from pcrfclient".format(host))
    master = None
    for m in c.admin.command("replSetGetStatus")["members"]:
        if m["stateStr"] == "PRIMARY":
            master = m["name"]

    if not master:
        fatal("{0}: Unable to find primary set member".format(host))
    log_debug("{0}: primary is {1}".format(host, master))
    return MC(master)

def build_connections(db_map):
    for k, v in db_map.iteritems():
        sess_primary = find_primary(v[0])
        db_map[k].append(sess_primary)

def sanitize(sess):
    for i in [ ":", ";" ]:
        sess = sess.replace(i, "%%%X" % ord(i))
    return sess

def reverse_sanitize(sess):
    for i in [ ":", ";" ]:
        sess = sess.replace("%%%X" % ord(i), i)
    return sess

def display_doc(session_doc, coll, setname):
    print("DB:          mongo://{host}:{port}/{db}/{collection}".format(host=coll.database.connection.host, 
        port=coll.database.connection.port, db=coll.database.name, collection=coll.name))
    print("Setname:     {0}".format(setname))
    print("Session key:    {0}".format(reverse_sanitize(session_doc["_id"]["diameterSessionKey"])))
    if "nextEvalTime" in session_doc:
        print("nextEvalTime:   {0}".format(session_doc["nextEvalTime"].strftime("%F %T")))
    if "expirationTime" in session_doc:
        print("expirationTime: {0}".format(session_doc["expirationTime"].strftime("%F %T")))
    if "tags" in session_doc:
        max = -1
        for t in session_doc["tags"]:
            parts = t.split(":")
            for p in parts:
                if len(p) > max:
                    max = len(p)
        max += 1
        print "%-*s" % (max, "TAGS")
        for t in session_doc["tags"]:
            print("".join(map(lambda x: "%-*s" % (max, x), t.split(":"))))
    print


def find_session(db_map, args):
    arg_count = 0

    if args.msisdn: 
        arg_count += 1
        query = { "tags" : "MsisdnKey:msisdn:{0}".format(args.msisdn) }
    if args.framed: 
        query = { "tags" : "FramedIpKey:framedIp:{0}".format(args.framed) }
        arg_count += 1
    if args.imsi:
        query = { "tags" : "ImsiKey:imsi:{0}".format(args.imsi) }
        arg_count += 1
    if args.session:
        query = { "_id" : {"diameterSessionKey" : sanitize(args.session)} }
        arg_count += 1

    if arg_count != 1:
        log_fatal("Must provide exactly one search term. Use -h for help")

    for setname, v in db_map.iteritems():
        host, db_conn = v
        for dbn in db_conn.database_names():
            if "session_cache" not in dbn or "session" not in db_conn[dbn].collection_names():
                continue
            collection = db_conn[dbn]["session"]
            log_debug("Searching {0} for {1}".format(collection, query))
            for doc in collection.find(query):
                display_doc(doc, collection, setname)

def main(args, ap):
    setup_logging(args.log, args.verbose)
    databases = read_mongo_config()
    build_connections(databases)
    find_session(databases, args)
    

if __name__ == "__main__":
    parser = AP.ArgumentParser(description="session finder (using mongo)")
    parser.add_argument("-l", "--log", help="Log output location (otherwise, stdout is used)")
    parser.add_argument("-v", "--verbose", help="Verbose debugging info", action="store_true")
    parser.add_argument("-m", "--msisdn", help="search by msisdn")
    parser.add_argument("-f", "--framed", help="search by framed IP")
    parser.add_argument("-i", "--imsi", help="search by imsi")
    parser.add_argument("-s", "--session", help="search by diameter session ID")

    args = parser.parse_args()
    main(args, parser)


