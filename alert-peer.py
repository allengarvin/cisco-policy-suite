#!/usr/bin/python3

# Version 1.2 20260316
# Author: "Allen Garvin" <algarvin@cisco.com>
# Copyright: 2026 Cisco, Inc

import argparse
import datetime as DT
import gzip
import os
import re
import stat
import sys

class peerDown:
    pattern = r'\S+::([^\s.=]+(?:\.\d+)?)\s*=\s*\S+:\s*(.*?)(?=\s+\S+::|$)'

    date, peer, status = None, None, None

    # ARRRRRRRRRG they switch month and day. It's SO close to ISO time!
    def parse_broadhop_time(self, s: str):
        return DT.datetime.strptime(s, "%Y-%d-%m,%H:%M:%S,%z")

    def zulu_delta(self, seconds):
        return (self.date + DT.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")

    def __str__(self):
        return "  %s" % ("DOWN: " if self.status == False else "UP: " ) + self.date.isoformat().replace("+00:00", "").replace("T", " ")

    def __repr__(self):
        return self.__str__()

    def __init__(self, line: str):
        try:
            matches = re.findall(self.pattern, line)
        except:
            print(line)
            sys.exit(1)
        result = {key.split('.')[0]: value.strip() for key, value in matches}
        if "broadhopComponentTime" in result:
            self.date = self.parse_broadhop_time(result["broadhopComponentTime"])
        else:
            print("NO TIME", line)

        if "broadhopComponentName" in result:
            self.peer = result["broadhopComponentName"]
            if "/" in self.peer:
                self.peer = self.peer[self.peer.index("/")+1:]
        else:
            print("NO PEER", line)

        if "broadhopNotificationSeverity" in result:
            sev = result["broadhopNotificationSeverity"]
            if "clear" in sev:
                self.status = True
            elif "critical" in sev or "error" in sev: # some are crits, some are just erros (like sy)
                self.status = False
            else:
                print("UNKNOWN SEV", sev)
                sys.exit(1)
        else:
            print("PROBLEM")
        # print(result)


def mk_peer_map(args):
    peers_map = {}
    last_date = None

    for fn in args.trapfiles:
        openf = gzip.open if fn.endswith(".gz") else open
        fd = openf(fn, mode="rt", encoding="utf-8")
        for line in fd:
            if f" {args.name}\t" in line:
                alert = peerDown(line)
                peer = alert.peer
                if peer not in peers_map:
                    peers_map[peer] = [alert]
                else:
                    peers_map[peer].append(alert)
                if last_date is None or alert.date > last_date:
                    last_date = alert.date
        fd.close()
    return peers_map, last_date

def check_time_args(args, secs):
    if args.least and not args.max:
        ret_value = True if secs >= args.least else False

    if args.least and args.max:
        ret_value = True if secs >= args.least and secs <= args.max else False

    if not args.least:
        ret_value = True if secs <= args.max else False

    if args.outside:
        return not ret_value
    else:
        return ret_value
    
def skipp(ignore, k):
    flag_skip = False
    for r in ignore:
        if r.search(k):
            flag_skip = True
            break

    return True if flag_skip else False

def main(args):
    ignore_expressions = [ re.compile("^sigm") ]
    if args.ignore:
        for r in args.ignore:
            ignore_expressions.append(re.compile(r))
    script_fd = None
    peers_map, last_date = mk_peer_map(args)

    if args.all and args.script:
        print("You probably shouldn't use --all with --script")
        sys.exit(1)

    if args.script:
        try:
            script_fd = open("alert-curl.sh", "w") 
        except:
            print("Unable to open alert-curl.sh for writing. Exiting")
            sys.exit(1)
        script_fd.write("#!/bin/bash\n\n")
        script_fd.write("""
if (( $# == 0 )); then
    echo "Give current high-res container. For instance: ./$0 s101"
    exit 1
fi

OUTFILE="/tmp/curl-report-$1.txt"


""")

    count = 0
    #print(peers_map)
    for k, v in peers_map.items():
        if skipp(ignore_expressions, k):
            continue

        v = sorted(v, key=lambda x: x.date)
        flag = False
        for i in range(len(v)):
            alert = v[i]
            prev = v[i-1]
            if alert.status == True:
                delta = alert.date - prev.date
                #print(prev, alert, delta.seconds)
                if args.all or check_time_args(args, delta.seconds):

                # old logic:
                # if (delta.seconds < args.time and not args.over) or (delta.seconds > args.time and args.over) or args.all:
                #
                    count += 1
                    if flag == False:
                        if not args.script:
                            print("Component Name:", k)
                        else:
                            script_fd.write(f"echo 'Component Name: {k}' >> $OUTFILE\n\n")
                        flag = True
                    if not args.script:
                        print(f"    Duration: {delta.seconds:5} sec  {prev} {alert}")
                    else:
                        msg = f"echo '{alert.date}: {delta.seconds:5} sec  {prev} {alert}' >> $OUTFILE"
                        command = f'curl -G "http://localhost:9090/api/v1/query_range" --data-urlencode \'query=peer_connection_status{{remote_peer="{k}"}}\' --data-urlencode "start={prev.zulu_delta(-60)}" --data-urlencode "end={alert.zulu_delta(60)}" --data-urlencode "step=1s" | python -m json.tool >> $OUTFILE'
                        script_fd.write(f"{msg}\n")
                        script_fd.write(f"{command}\n\n")
    if args.unresolved:
        cnt = 0
        for k, v in peers_map.items():
            if skipp(ignore_expressions, k):
                continue
            if len(v) and v[-1].status == True:
                if not cnt:
                    print("Unresolved alerts:")
                cnt += 1
                alert = v[-1]
                print(f"  {k:<35} fired: {alert.date} duration: {(last_date - alert.date).seconds} sec")
                
        print("Total unresolved alerts:", cnt)

    if args.script:
        script_fd.close()
        os.chmod("alert-curl.sh", os.stat("alert-curl.sh").st_mode | stat.S_IXUSR | stat.S_IXOTH)
        print("curl command for customer is in alert-curl.sh")
    else:
        print("TOTAL matching criteria", count)
    
 


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Analyze snmp trap alerts")
#   logic changed to least and max.
#     ap.add_argument("-t", "--time", default=deftime, type=float, help=f"time delta (float) in seconds between alert and clear (default={deftime:.1f})")
    ap.add_argument("-l", "--least", default=90.0, type=float, help="least time to recovery (default=90)")
    ap.add_argument("-m", "--max", default=0, type=float, help="max time to recovery (optional. It not present, no max)")
    ap.add_argument("-s", "--script", action="store_true", help="Generate bash script to check hi-res data")
    ap.add_argument("trapfiles", nargs="+", help="trap files")
    ap.add_argument("-a", "--all", action="store_true", help="Display ALL down alerts and durations")
    ap.add_argument("-o", "--outside", action="store_true", help="Use OUTSIDE the values")
    ap.add_argument("-i", "--ignore", nargs="*", help="ignore regexp (includes default ^sigm)")
    ap.add_argument("-n", "--name", type=str, default="DIAMETER_PEER_DOWN", help="Alert name (default: DIAMETER_PEER_DOWN)")
    ap.add_argument("-u", "--unresolved", action="store_true", help="Unresolved alerts (without a clear)")
    args = ap.parse_args()
    main(args)
