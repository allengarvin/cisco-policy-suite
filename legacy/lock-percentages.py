#!/usr/bin/env python2

# Used mongostat by Kenny Gorman as starting place for this: https://github.com/kgorman/mongostat
# License: https://github.com/kgorman/mongostat/blob/master/LICENSE


from argparse import ArgumentParser
from pymongo import MongoClient
from time import sleep
from datetime import datetime
import sys, os, signal, pprint

class MongoLockStat:

    def __init__(self):
        parser = ArgumentParser(description="A script to monitor lock percentages of Mongo")

        parser.set_defaults(database="session", hostname="sessionmgr01", port=27717, count=-1, delay=2)
        parser.add_argument("mongourl", help="mongo url", nargs="?")
        parser.add_argument("--hostname", dest="chostname", help="server to connect to")
        parser.add_argument("--csv", help="output in csv format", action="store_true")
        parser.add_argument("-p", "--port", dest="cport", type=int, help="port to connect to")
        parser.add_argument("-v", "--verbose", help="increase verbosity (currently does nothing)", action="store_true")
        parser.add_argument("-d", "--delay", dest="delay", type=int, help="delay in seconds in between stat calls (default: 2)")
        parser.add_argument("-c", "--count", dest="count", type=int, help="number of iterations to run (default: indefinitely)")

        self.args = parser.parse_args()

        db_address = None

        if self.args.mongourl:
            db_address = self.args.mongourl

        if db_address:
            (hosts, database, username, password) = self._parse_uri(db_address)
            (chost, cport) = hosts[0]
            # To do: multiple hosts
        else:
            if ":" in self.args.hostname:
                (chost, cport) = args.hostname.split(":")
            else:
                chost = self.args.hostname
                cport = self.args.port

        if type(cport) is str:
            cport = int(cport)

        try:
            connection = MongoClient(host=chost, port=cport)
        except:
            print("Unable to connect to %s:%d" %(chost, cport))
            sys.exit(1)

        self.db = connection.admin
        self.setSignalHandler()
        self.printStats()

    def __partition(self, source, sub):
        i = source.find(sub)
        if i == -1:
            return (source, None)
        return (source[:i], source[i+len(sub):])

    def _parse_uri(self, uri):
        info = {}
 
        if uri.startswith("mongodb://"):
            uri = uri[len("mongodb://"):]
        elif "://" in uri:
            raise Exception("Invalid uri scheme: %s" % self.__partition(uri, "://")[0])
 
        (hosts, database) = self.__partition(uri, "/")
 
        if not database:
            database = None
 
        username = None
        password = None
        if "@" in hosts:
            (auth, hosts) = self.__partition(hosts, "@")
 
            if ":" not in auth:
                raise Exception("auth must be specified as 'username:password@'")
            (username, password) = self.__partition(auth, ":")
 
        host_list = []
        for host in hosts.split(","):
            if not host:
                raise Exception("empty host (or extra comma in host list)")
            (hostname, port) = self.__partition(host, ":")
            if port:
                port = int(port)
            else:
                port = 27017
            host_list.append((hostname, port))
 
        return (host_list, database, username, password)

    def setSignalHandler(self):
        def handler(signal, frame):
            sys.exit(0)

        signal.signal(signal.SIGINT, handler)

    def printStats(self):
        i=0
        global_lock = 0
        statistics = {}
        global_stats = {}
        longest_db = -1
        banner_print = False

        while self.args.count == -1 or i <= self.args.count:
            data = self.db.command({"serverStatus" : 1})
            i += 1 


            if "globalLock" in data:
                global_stats["stats"] = data["globalLock"].copy()

                if len(statistics):
                    old_global_lock = global_lock
                    global_lock = data["globalLock"]["lockTime"]
                else:
                    old_global_lock = global_lock = data["globalLock"]["lockTime"]
            

            if "locks" in data and isinstance(data["locks"], dict):
                for dbn, ldict in data["locks"].iteritems():
                    if len(dbn) > longest_db:
                        longest_db = len(dbn)
                    flag = False
                    
                    if "r" in ldict["timeAcquiringMicros"] and "w" in ldict["timeAcquiringMicros"]:
                        tamr = ldict["timeAcquiringMicros"]["r"]
                        tamw = ldict["timeAcquiringMicros"]["w"]
                        flag = True
                    if "r" in ldict["timeLockedMicros"] and "w" in ldict["timeLockedMicros"]:
                        tlmr = ldict["timeLockedMicros"]["r"]
                        tlmw = ldict["timeLockedMicros"]["w"]

                    if not flag:
                        continue    # The "." dbn

                    if not dbn in statistics:
                        statistics[dbn] = { "tamr" : tamr, "tamw" : tamw, "tlmr" : tlmr, "tlmw" : tlmw,
                                             "old_tamr" : tamr, "old_tamw" : tamw, "old_tlmr" : tlmr, "old_tlmw" : tlmw }
                        continue    # first run, no data
                    else:
                        statistics[dbn] = { "old_tamr" : statistics[dbn]["tamr"],
                                            "old_tamw" : statistics[dbn]["tamw"],
                                            "old_tlmr" : statistics[dbn]["tlmr"],
                                            "old_tlmw" : statistics[dbn]["tlmw"], 
                                            "tamr" : tamr, "tamw" : tamw, "tlmr" : tlmr, "tlmw" : tlmw }
                    tamrd = statistics[dbn]["tamr"] - statistics[dbn]["old_tamr"]
                    tamwd = statistics[dbn]["tamw"] - statistics[dbn]["old_tamw"]
                    tlmrd = statistics[dbn]["tlmr"] - statistics[dbn]["old_tlmr"]
                    tlmwd = statistics[dbn]["tlmw"] - statistics[dbn]["old_tlmw"]

                    tamrp = "%0.1f" % (tamrd / float(self.args.delay * 1000) * 100)
                    tamwp = "%0.1f" % (tamrd / float(self.args.delay * 1000) * 100)
                    tlmrp = "%0.1f" % (tamrd / float(self.args.delay * 1000) * 100)
                    tlmwp = "%0.1f" % (tamrd / float(self.args.delay * 1000) * 100)
                    if not banner_print:
                        banner_print = True
                        if self.args.csv:
                            print("Time,Database,ReadAcquisitionLock,WriteAcquisitionLock,ReadLock,WriteLock")
                        else:
                            print("%-12s %-*s %-*s %-*s  %-*s  %-*s" % 
                                ("Time", longest_db + 10, "Database", 12, "R-AcqLock", 12, "W-AcqLock", 12, "R-Lock", 12, "W-Lock"))
                    if self.args.csv:

                        print("%s,%s,%-s,%-s,%-s,%-s" % 
                            (datetime.now().strftime("%X"),dbn, tamrp, tamwp, tlmrp , tlmwp))
                    else:
                        print("%-12s %-*s    %-*s    %-*s    %-*s    %-*s" % 
                            (datetime.now().strftime("%X"), longest_db + 10, dbn, 9, tamrp + "%", 9, tamwp + "%", 9, tlmrp + "%", 9, tlmwp + "%"))
            sleep(self.args.delay)

            
if __name__ == "__main__":
    MongoLockStat()
