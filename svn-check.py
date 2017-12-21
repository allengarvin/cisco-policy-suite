#!/usr/bin/python

# Check if all SVN caches on qns-running servers are synced up
# Version 0.1 2017-06-03
# Author: "Allen Garvin" <algarvin@cisco.com>
# This should highlight issues in CSCuw78613, along with testing several other possible (rare) problems

import sys, subprocess, argparse
from httplib import HTTPConnection as http
import xml.etree.ElementTree as ET

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

def connect():
    c1 = http("pcrfclient01")
    c2 = http("pcrfclient02")

    return c1, c2

def make_query(conn, server):
    try:
        conn.request("GET", "/repos/run/.broadhopFileRepository")
    except:
        display_error("Unable to connect to http://%s:80" % server)
        return False

    resp = conn.getresponse()
    stat = resp.status
    if stat != 200:
        display_error("%s gave %d response for /repos/run/.broadhopFileRepository" % (server, stat))
        return False

    data = resp.read()
    conn.close()
    return data

def parse_xml(xml_str, server):
    try:
        root = ET.fromstring(xml_str)
    except:
        display_error("Bad XML on %s's .broadhopFileRepository" % (server))
        return False
    if root.tag != "{http://broadhop.com/runtime}BroadhopRepositoryData":
        display_error("Unexpected tag %s on %s" % (root.tag, server))

    if not "publishDate" in root.attrib:
        display_error("%s .broadhopFileRepository has no publishDate" % server)
        return False

    # TODO: parse using dateutil?

    publishDate = root.attrib["publishDate"]
    return publishDate

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
                if "qns" in line or "lb0" in line or "pcrfclient" in line:
                    hosts.append(line.split())

    if len(hosts) == 0:
        display_error("Unable to read CPS hosts in /etc/hosts")
        sys.exit(2)
    return hosts
    
def hostname(h1, h2):
    if h1 == h2 or h2 == False:
        return h1
    return "%s (%s)" % (h2,h1)

def check_hosts(hosts, match_time):
    global quiet

    flag = False

    for h in hosts:
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
            files = subprocess.Popen("ssh %s '/bin/echo /var/broadhop/checkout/*/.broadhopFileRepository'" % hn1, stdout=subprocess.PIPE, shell=True).stdout.read()
        except:
            display_error("No /var/broadhop/checkout/*/.broadhopFileRepository on %s" % hostname(hn1, hn2))
            continue
        if "*" in files: 
            display_error("No /var/broadhop/checkout/*/.broadhopFileRepository on %s" % hostname(hn1, hn2))
            continue
        for f in files.split():
            try:
                xml_str = subprocess.Popen("ssh %s 'cat %s'" % (hn1, f), stdout=subprocess.PIPE, shell=True).stdout.read()
            except:
                flag = True
                display_error("%s: unable to read %s" % (hostname(hn1, hn2), f))
                continue
            svn_time = parse_xml(xml_str, hostname(hn1,hn2))
            if svn_time != match_time:
                display_error("%s: SVN not synced. Has %s" % (hostname(hn1,hn2), svn_time)) 
                flag = True
                continue
            else:
                if not quiet:
                    display_ok("%s <%s>" % (hostname(hn1,hn2), f))
    return flag

def main(argv):
    global quiet

    c1, c2 = connect()
    c1_resp = make_query(c1, "pcrfclient01")
    c2_resp = make_query(c2, "pcrfclient02")

    if c1_resp:
        c1_time = parse_xml(c1_resp, "pcrfclient01")
    if c2_resp:
        c2_time = parse_xml(c2_resp, "pcrfclient02")
    if c1_time and c2_time and c1_time != c2_time:
        display_error("publishDate different on pcrfclient01 and 02")
        print("    pcrfclient01: %s\n    pcrfclient02: %s\n" % (c1_time, c2_time))
        print("    Using 01 as canonical")
        svn_time = c1_time
    elif c1_time:
        svn_time = c1_time
    elif c2_time:
        svn_time = c2_time
    else:
        print("No publishDate, unable to proceed")
        sys.exit(1)

    if not quiet:
        print("Reference time: %s" % svn_time)

    hosts = get_hosts()
    if check_hosts(hosts, svn_time):
        sys.exit(3)
    else:
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check CPS hosts for synchronized SVN checkouts")
    parser.add_argument("-q", "--quiet", help="Quiet (only print errors", action="store_true")
    args = parser.parse_args()
    quiet = args.quiet
    main(sys.argv)
