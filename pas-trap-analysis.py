#!/usr/bin/python3

# This works against CPS vDRA. See trap-analysis.py for my script for the PCRF.
# This has been generalized for any alert type. I might rewrite it later

# Version 1.3 20260316
# Author: "Allen Garvin" <algarvin@cisco.com>
# Copyright: 2026 Cisco, Inc

import argparse
import datetime as DT
import gzip
import os
import re
import stat
import sys

class alertInstance:
    pattern = r'\S+::([^\s.=]+(?:\.\d+)?)\s*=\s*\S+:\s*(.*?)(?=\s+\S+::|$)'

    date, name, status, snmptype = None, None, None, None
    all_attributes = None

    # ARRRRRRRRRG they switch month and day. It's SO close to ISO time!
    def parse_broadhop_time(self, s: str):
        return DT.datetime.strptime(s, "%Y-%d-%m,%H:%M:%S,%z")

    def zulu_delta(self, seconds):
        return (self.date + DT.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")

    def __str__(self):
        return "  %s" % ("DOWN: " if self.status == False else "UP: " ) + self.date.isoformat().replace("+00:00", "").replace("T", " ")

    def __repr__(self):
        dt = self.date.isoformat().replace("+00:00", "").replace("T", " ")
        name = self.all_attributes["broadhopComponentNotificationName"]
        facility = self.all_attributes["broadhopNotificationFacility"]
        severity = self.all_attributes["broadhopNotificationSeverity"]
        info = self.all_attributes["broadhopComponentAdditionalInfo"]

        return f"{dt} | {name} | Fac={facility} | Sev={severity} | {info}"

    def __init__(self, line: str):
        try:
            matches = re.findall(self.pattern, line)
        except:
            print(line)
            sys.exit(1)
        result = { k.split('.')[0]: v.strip() for k, v in matches}

        self.snmptype = result["broadhopComponentNotificationName"]

        if "broadhopComponentTime" in result:
            self.date = self.parse_broadhop_time(result["broadhopComponentTime"])
            result["broadhopComponentTime"] = self.parse_broadhop_time(result["broadhopComponentTime"])
        else:
            print("NO TIME", line)

        if "broadhopComponentName" in result:
            self.name = result["broadhopComponentName"]
            if "/" in self.name:
                self.name = self.name[self.name.index("/")+1:]
            result["broadhopComponentName"] = self.name
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

#        for k, v in result.items():
#            print(k, v)
#            
#        sys.exit(1)
        self.all_attributes = result

        # print(result)

class alertMap:
    alerts_map = {}

    first, last = None, None
    script_fd = None

    def __init__(self, mapping: dict, first: DT.datetime, last: DT.datetime):
        for k, v in mapping.items():
            mapping[k] = sorted(v, key=lambda x: x.date)
        self.alerts_map = mapping
        self.first = first
        self.last = last
        
    def show_resolved_alerts(self, args):

        count = 0

        for k, v in self.alerts_map.items():
            flag = False
            for i in range(1, len(v)):
                alert = v[i]
                prev = v[i-1]
    
                if alert.status == True:
                    delta = alert.date - prev.date
                    if not args.least or check_time_args(args, delta.seconds):
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

        return count

    def show_unresolved_alerts(self, args):
        count = 0
        for k, v in self.alerts_map.items():
            if args.verbose:
                print("DEBUG: last alert:", repr(v[-1]), v[-1].status)
            if len(v) and v[-1].status == False:
                count += 1
                alert = v[-1]
                print(f"    {k:<35} Fired: {alert.date} | Duration: {(self.last - alert.date).seconds} sec")
                
        return count

def mk_alert_map(args, alerts):
    alerts_map = {}

    first_date, last_date, count = None, None, 0

    ignore_expressions = [ re.compile("^sigm") ]
    if args.ignore:
        for r in args.ignore:
            ignore_expressions.append(re.compile(r))

    for a in alerts:
        if a.snmptype != args.name:
            continue

        if skipp(ignore_expressions, a.name):
            continue

        if args.verbose:
            print("DEBUG", repr(a))
        if not first_date:
            first_date = a.date
        if not last_date:
            last_date = a.date

        if a.name in alerts_map:
            alerts_map[a.name].append(a)
        else:
            alerts_map[a.name] = [a]
    
        count += 1

        if a.date > last_date:
            last_date = a.date
        if a.date < first_date:
            first_date = a.date

    am_obj = alertMap(alerts_map, first_date, last_date)
    am_obj.count = count
    return am_obj

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

def list_alerts_present(args, alerts):
    notifications = {}
    length = -1

    for a in alerts:
        name = a.all_attributes["broadhopComponentNotificationName"]
        if len(name) > length:
            length = len(name)

        if name in notifications:
            notifications[name] += 1
        else:
            notifications[name] = 1
    for n in sorted(notifications.keys()):
        print("  ", n.ljust(length), notifications[n])
    print("# alert types:", len(notifications))


def read_alerts(args):
    alerts = []

    for fn in args.trapfiles:
        openf = gzip.open if fn.endswith(".gz") else open
        fd = openf(fn, mode="rt", encoding="utf-8")
        for line in fd:
            if "BROADHOP-MIB" not in line:
                continue
            alerts.append(alertInstance(line))
    
    print("# Alerts parsed:", len(alerts))
    return alerts
     
def initial_script(args):
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
    return script_fd

def main(args):
    all_alerts = read_alerts(args)
    list_alerts_present(args, all_alerts)

    if args.raw:
        for a in all_alerts:
            if a.snmptype == args.name:
                print(repr(a))
        sys.exit(0)

    if args.list:
        sys.exit(0)

    alert_map = mk_alert_map(args, all_alerts)
    if args.script:
        alert_map.script_fd = initial_script(args)

    print(f"== Report for {args.name} ({alert_map.count} snmp traps present) ==")
    print("  Resolved alerts:")
    rcnt = alert_map.show_resolved_alerts(args)
    print("------------------")
    print("  Unresolved alerts:")
    print("--------------------")
    ucnt = alert_map.show_unresolved_alerts(args)
    print("--------------------")
    print(f"  Total traps present: {alert_map.count}")
    print(f"  Resolved total: {rcnt} [{rcnt*2} traps]")
    print(f"  Unresolved total: {ucnt} traps")
    
    sys.exit(0)

    count = 0
    #print(peers_map)

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
    ap.add_argument("-i", "--ignore", nargs="*", help="ignore regexp (includes default ^sigm)")
    ap.add_argument("--list", action="store_true", help="List all alert names present in traps and immediately exit")
    ap.add_argument("-l", "--least", default=0.0, type=float, help="least time to recovery)")
    ap.add_argument("-m", "--max", default=0, type=float, help="max time to recovery (optional. It not present, no max)")
    ap.add_argument("-n", "--name", type=str, default="DIAMETER_PEER_DOWN", help="Alert name (default: DIAMETER_PEER_DOWN)")
    ap.add_argument("-o", "--outside", action="store_true", help="Use OUTSIDE the values")
    ap.add_argument("-r", "--raw", action="store_true", help="Raw list of alerts and immediately exit")
    ap.add_argument("-s", "--script", action="store_true", help="Generate bash script to check hi-res data")
    ap.add_argument("-u", "--unresolved", action="store_true", help="Unresolved alerts (without a clear)")
    ap.add_argument("-v", "--verbose", action="store_true", help="Debugging info")
    ap.add_argument("trapfiles", nargs="+", help="trap files")
    args = ap.parse_args()
    main(args)
