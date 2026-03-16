#!/usr/bin/python

# Script to print session masters of a particular type.
# Primary use of this is for writing shell scripts, when you need to cycle through primary members
# Author: "Allen Garvin" <algarvin@cisco.com> 2018-06-27
import ConfigParser, sys, argparse
from pymongo import MongoClient

def mconnect(host):
    c = MongoClient(host)
    for m in c.admin.command("replSetGetStatus")["members"]:
        if m["stateStr"] == "PRIMARY":
            master = m["name"]
    if host == master:
        return master, c
    else:
        return master, MongoClient(master)

def query(d):
    if "member1" in d:
        hostname, client = mconnect(d["member1"])
        print d["setname"], hostname
    else:
        print "ERROR: No MEMBER1 in {0}".format(d)

def main(cpar):
    cnf = ConfigParser.ConfigParser()
    cnf.read("/etc/broadhop/mongoConfig.cfg")

    for sec in cnf.sections():
        attr = dict( (a,b) for a,b in cnf.items(sec) )
        if "-END" in sec:
            continue

        if "{0}".format(cpar.settype.upper())  in sec:
            if "setname" in attr and not cpar.name or (cpar.name and cpar.name.lower() in attr["setname"].lower()):
                if cpar.ignore and cpar.ignore.lower() in attr["setname"].lower():
                    continue
                query(attr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="print mongo master of every set of a particular type")

    parser.add_argument("settype", help="set type, typically session, admin, spr, balance")
    parser.add_argument("-n", "--name", help="Additional string to check setname attribute (for instance, to look for udc)")
    parser.add_argument("-i", "--ignore", help="Additional string to ignore setname attribute (for instance, toss out udc session dbs)")
    args = parser.parse_args()
    main(args)

