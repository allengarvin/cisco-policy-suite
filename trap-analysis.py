#!/usr/bin/python
# For now I need python2 & python3 support, as some older customers only have python2
#     this may not be true in 2026 anymore, but I will leave it for the time being

# This script analyzes trap files from CPS PCRF

import argparse
from datetime import datetime as DT
import glob
import gzip
import os
import platform
import re
import sys
import subprocess

def parse_details(det):
    int_re = re.compile("^\d+$")

    # I wish we had the parse library!
    if not re.search("id=[0-9]{4},values=\{", det):
        print("Alarm details fail expected ID pattern:")
        print(det)
        print("---")
        return None

    id = int(det[:det.index(",")].split("=")[1])

    values=det[det.index("{")+1:det.rfind("}", 0)]

    tokens = { 
        "id" : id 
    }
    for tok in values.split(", "):
        if "=" not in tok:
            continue
        a, b = tok.split("=")
        if int_re.match(b):
            b = int(b)
        if a == "msg":
            b = b[1:].rstrip('"')
        tokens[a] = b

    return tokens

def parse_alarm(alrm):
    dt_str = alrm.split()[0]
    if "." in dt_str:
        # ditch milliseconds + time zone. Not useful
        dt_str = dt_str[:dt_str.index(".")]

    if "[id=" not in alrm:
        print("Warning: no id in alarm log:")
        print(alrm)
        print("---")
        return None

    lstr = alrm[alrm.index("[id=")+1:]

    qflag = False
    for i, c in enumerate(lstr):
        if c == '"':
            qflag = not qflag
        if qflag:
            continue
        if c == "]":
            break;

    alarm_details = lstr[:i]
    try:
        alert = parse_details(alarm_details)
    except:
        alert = None
    if not alert:
        return None

    dt = DT.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
    alert["time"] = dt
    return alert

def nice_time_diff(delta):
    return str(delta)

def main(args):
    filec = []
    if not os.path.isdir(args.directory):
        print("{0}: does not exist or is not a directory".format(args.directory))
        sys.exit(1)
    for fn in glob.glob(args.directory + "/trap*"):
        if fn.endswith(".gz"):
            fd = gzip.open(fn)
            filec.append(fd.read())
            fd.close()
        else:
            fd = open(fn)
            filec.append(fd.read())
            fd.close()

    alerts = []
    for fc in filec:
        for lno, line in enumerate(fc.split("\n")):
            if "TRAP, SNMP v1" in line:
                a = parse_alarm(line)
                if a:
                    alerts.append(a)
    alerts = sorted(alerts, key=lambda s: s["time"])

    uncleared = []
    print("{0} alarms parsed. Beginning analysis".format(len(alerts)))
    for i, a in enumerate(alerts):
        if args.events:
            if "status" in a:
                continue        # this is an up/down alert
            print("{time} {host} {id}/{sub_id} {msg}".format(time=a["time"].strftime("%Y-%m-%dT%H:%M:%S"),
                id=a["id"], sub_id=a["sub_id"], msg=a["msg"], host=a["event_host"]))
            continue
        if "status" not in a:
            continue
        id, sub_id, host, status = a["id"], a["sub_id"], a["event_host"], a["status"]
        if status == "up":
            # an alert clear from an alarm that is no longer in the logs
            continue

        flag = False
        for b in alerts[i+1:]:
            if "status" not in b:
                continue
            if [id, sub_id, host, "up"] == [b["id"], b["sub_id"], b["event_host"], b["status"]]:
                flag = True
                break
        if flag == False:
            uncleared.append(a)
        elif args.cleared:
            t1=a["time"]
            t2=b["time"]
            print("{t1} <-> {t2} duration={duration}: {host} {id}/{sub_id} {msg}".format(
                t1=t1.strftime("%Y-%m-%dT%H:%M:%S"),
                t2=t2.strftime("%Y-%m-%dT%H:%M:%S"),
                duration=nice_time_diff(t2-t1), id=a["id"], sub_id=a["sub_id"], msg=a["msg"], 
                host=a["event_host"]))

    # TODO !!! rewrite this as a socket
    if args.listalarms:
        print("Diagnostics List Alarms")
        print("-----------------------")
        if platform.python_version() < "3.4":
            subprocess.call("echo listalarms | nc pcrfclient01 9091", shell=True)
        else:
            subprocess.run("echo listalarms | nc pcrfclient01 9091", shell=True)
        print("-----------------------")
    
    if args.cleared:
        return

    print("Uncleared alerts:")
    for a in uncleared:
        print("{time} {host} {id}/{sub_id} {msg}".format(time=a["time"].strftime("%Y-%m-%dT%H:%M:%S"),
            id=a["id"], sub_id=a["sub_id"], msg=a["msg"], host=a["event_host"]))




if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="analyze snmp traps")
    ap.add_argument("-d", "--directory", help="trap dir (default: /var/log/snmp/)", default="/var/log/snmp")
    ap.add_argument("-e", "--events", action="store_true", help="Show event alarms (that never have a clear)")
    ap.add_argument("-c", "--cleared", action="store_true", help="Show only alerts that later cleared")
    ap.add_argument("-l", "--listalarms", action="store_true", help="diagnostics list alarms")
    args = ap.parse_args()
    main(args)
