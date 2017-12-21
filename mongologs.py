#!/usr/bin/python

# Script to generate commands for gathering the logs of mongo instances
#   on CPS.
# Author: "Allen Garvin" <algarvin@cisco.com>
# v0.1 2017-10-31
# Note: This is not official Cisco software.

import sys, os
import ConfigParser as CP
import argparse as AP

def read_mongo_config():
    cnf_file = "/etc/broadhop/mongoConfig.cfg"

    if not os.path.isfile(cnf_file):
        print("Error: cannot find %s" % cnf_file)
        exit(1)

    cnf = CP.ConfigParser()
    cnf.read(cnf_file)
    return cnf
    
def find_logpaths(cnf, section):
    vm_map = dict()

    for (k, v) in cnf.items(section):
        if k == "setname":
            setname = v
        if k == "arbiter" or k[:6] == "member":
            vm_map[v.split(":")[0]] = v.split(":")[1]

    print("Copy and paste the following:\n")

    print("mkdir /var/tmp/mongo-logs-%s" % setname)
    print("cd /var/tmp/mongo-logs-%s" % setname)
    for k in vm_map.keys():
        print("scp %s:/var/log/mongodb-%s.log ./%s-%s.log" % (k, vm_map[k], k, vm_map[k]))


def main(args, parser):
    
    if not args.cfgset and not args.port and not args.set:
        print("Error: must give one of --port, --cfgset or --set\n")
        parser.print_help()
        sys.exit(1)

    a = 0
    if args.cfgset:
        a += 1
    if args.port:
        a += 1
    if args.set:
        a += 1
    if a > 1:
        print("Error: must give ONLY one of --port, --cfgset or --set\n")
        sys.exit(1)

    cnf = read_mongo_config()

    for sec in cnf.sections():
        if "-END" in sec:
            continue

        if args.cfgset and sec == args.cfgset:
            find_logpaths(cnf, sec)
            sys.exit(0)

        if args.port:
            for (k, v) in cnf.items(sec):
                # only pay attention to non-arbiters
                if "sessionmgr" in v and (":%d" % args.port) in v:
                    find_logpaths(cnf, sec)
                    sys.exit(0)

        if args.set:
            flag = False
            for (k, v) in cfg.items(sec):
                if k == "setname" and v == args.set:
                    find_logpaths(cnf, sec)
                    sys.exit(0)
    print("Found no mongo instances matching that query. Review /etc/broadhop/mongoConfig.cfg")
    sys.exit(1)

if __name__ == "__main__":
    parser = AP.ArgumentParser(description="Generate commands to capture Mongo logs")
    parser.add_argument("--cfgset", help="Example: SESSION-SET1")
    parser.add_argument("--port", type=int, help="The standard port for the mongo service (ie, 27718)")
    parser.add_argument("--set", help="The replica set name (ie, set01a)")
    args = parser.parse_args()
    main(args, parser)
