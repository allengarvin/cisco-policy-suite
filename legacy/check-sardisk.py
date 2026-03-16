#!/usr/bin/python

# Check sar disk io waits for chances of failing disks
# Version 0.1 2017-06-03

# Note: not official Cisco software. Only the author is able to support this.


import sys, subprocess, argparse
from httplib import HTTPConnection as http
from datetime import datetime, date, timedelta

# millisecond threshold. Can be changed with -t option:
threshold = 100
count_limit = 20

# Nice elegant little solution from https://svn.blender.org/svnroot/bf-blender/trunk/blender/build_files/scons/tools/bcolors.py
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def red(str):
    return "[" + bcolors.FAIL + str + bcolors.ENDC + "]"

def green(str):
    return "[" + bcolors.OKGREEN + str + bcolors.ENDC + "]"

def display_ok(str):
    print("%-60s %s" % (str, green("OK")))

def display_error(str):
    print("%-60s %s" % (str, red("PROBLEM")))

def get_hosts():
    hosts = []

    flag = False
    with open("/etc/hosts", "r") as fd:
        for line in fd:
            if "BEGIN_QPS_LOCAL_HOSTS" in line:
                flag = True
                continue
            elif "END_QPS_LOCAL_HOSTS" in line:
                flag = False
            if flag:
                line = line.strip()
                if "qns" in line or "lb0" in line or "pcrfclient" in line or "sessionmgr" in line:
                    hosts.append(line.split())

    if len(hosts) == 0:
        display_error("Unable to read CPS hosts in /etc/hosts")
        sys.exit(2)
    return hosts
    
def hostname(h):
    if len(h) == 2:
        return h[1]
    if len(h) == 3:
        if h[1] == h[2]:
            return h[1]
        return "%s (%s)" % (h[2],h[1])
    return h[0]

def dev_name_query(await_times, server):
    nodes = subprocess.Popen("ssh %s 'stat -c %%t,%%T,%%n /dev/*'" % server[1], stdout=subprocess.PIPE, shell=True).stdout.read()
    lvm = subprocess.Popen("ssh %s 'stat -c %%n,%%N /dev/mapper/*'" % server[1], stdout=subprocess.PIPE, shell=True).stdout.read()
    n_mapping = dict()

    for n in nodes.splitlines():
        p = n.split(",")
        if len(p) != 3:
            continue
        major = int(p[0], 16)
        minor = int(p[1], 16)
        fn = p[2]
        if "dm-" in fn:
            for l in lvm.splitlines():
                if fn.split("/")[1] in l:
                    fn = l.split(",")[0]
        n_mapping[(major,minor)] = fn
    return n_mapping

def check_disk(await_times, server):
    global threshold, count_limit

    n_mapping = dev_name_query(await_times, server)

    flag = False
    for dev in await_times.keys():
        d_major = int(dev[3:].split("-")[0])
        d_minor = int(dev[3:].split("-")[1])
        if (d_major, d_minor) in n_mapping:
            dev_name = n_mapping[(d_major,d_minor)]
        else:
            dev_name = dev

        cnt = 0
        for i in await_times[dev]:
            if i > threshold:
                cnt += 1

        if cnt > count_limit:
            times = sorted(await_times[dev])

            display_error("Possible disk problem on %s with io access times > %d" % (hostname(server), threshold))
            print("    Device name: %s" % dev_name)
            print("    10-minute interval exception number: %d (out of %d)" % (cnt, len(times)))
            print("    Median await time: %d ms" % times[len(times)/2])
            print("    Average await time: %d ms" % ( sum(times) / len(times) ))
            print("    Max 10-minute average observed: %d ms" % times[-1])
            flag = True

    if flag:
        print("-----------------------------------------------------")
    return flag
    

def check_hosts(hosts, args):
    global quiet

    server = args.server
    flag = False

    for h in hosts:
        if server and not server in h:
            continue
        if len(h) >= 3:
            hn1 = h[1]
            hn2 = h[2]
        elif len(h) == 2:
            hn1 = h[1]
            hn2 = False
        elif len(h) == 1:
            hn1 = h[0]
            hn2 = False
        else:
            # don't think this should be possible
            continue
        try:
            yesterday = "/var/log/sa/sa" + (date.today() - timedelta(1)).strftime("%d")
            sar_data = subprocess.Popen("ssh %s 'sar -d; sar -f %s -d'" % (hn1, yesterday), stdout=subprocess.PIPE, shell=True).stdout.read()
        except:
            display_error("Unable to pull sar stats via ssh from %s" % hostname(hn1, hn2))
            continue

        await_index = False
        dev_index = False
        await_times = dict()

        for line in sar_data.splitlines():
            parts = line.split()
            if not await_index or "DEV" in parts:
                if "DEV" in parts:
                    await_index = parts.index("await")
                    dev_index = parts.index("DEV")
                continue
            if "AM" in parts or "PM" in parts:
                dev = parts[dev_index]
                await = int(float(parts[await_index]))
                if dev in await_times:
                    await_times[dev].append(await)
                else:
                    await_times[dev] = [await]
        if args.csv:
            for k in sorted(await_times.keys()):
                n_mapping = dev_name_query(await_times, h)
                d_major = int(k[3:].split("-")[0])
                d_minor = int(k[3:].split("-")[1])
                if (d_major, d_minor) in n_mapping:
                    dev_name = n_mapping[(d_major,d_minor)]
                else:
                    dev_name = dev

                times = sorted(await_times[k])
                median = times[len(times)/2]
                mean = sum(times) / len(times)
                max = times[-1]
                host = h[-1]
                print("%s,%s,%d,%d,%d" % (host, dev_name, median, mean, max))
                sys.stdout.flush()
        else:
            check_disk(await_times, h)

    return flag

def main(args):
    
    hosts = get_hosts()
    if check_hosts(hosts, args):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check sar statistics for signs of failing disks")
    parser.add_argument("-t", "--threshold", type=int, help="millisecond threshold (default: {0})".format(threshold))
    parser.add_argument("-c", "--count", type=int, help="Count limit (default: {0})".format(count_limit))
    parser.add_argument("-s", "--server", help="Check only a single server (default: every CPS VM)")
    parser.add_argument("--csv", action="store_true", help="CSV output for all hosts (unless --server specified). Format is: hostname,device,median access time,mean access time,max observed")
    args = parser.parse_args()
    if args.threshold:
        threshold = args.threshold
    if args.count:
        count_limit = args.count
    main(args)
