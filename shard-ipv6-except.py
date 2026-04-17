#!/usr/bin/python3

# Decent script for investigating ShardingIpv6BindingExpiration exceptions
# With -s, all output is suppressed.
# This is for use with scripting. When used for scripting:
#       Bash return value: 0   at least one exception occurs
#       Bash return value: 1   ZERO sharding exceptions found

# Author: "Allen Garvin" <algarvin@cisco.com>
# Copyright: 2026 Cisco, Inc.

import argparse
import datetime as DT
import gzip
import sys

def debug(args: argparse.Namespace, msg: str):
    if not args.verbose:
        return
    print(f"DEBUG: {msg}", file=sys.stderr)

def error(args: argparse.Namespace, msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)

def info(args: argparse.Namespace, msg: str):
    if not args.quiet:
        print(msg)

def contiguous_blocks(times: list, step: int):
    if not times:
        return []

    times = sorted(set(times))
    values = sorted(set(times))
    blocks = []

    start = prev = values[0]

    for t in values[1:]:
        if t - prev <= step:
            prev = t
            continue

        blocks.append((start, prev))
        start = prev = t

    blocks.append((start, prev))
    return blocks

def main(args: argparse.Namespace):
    instances = {}

    # I don't do anything with container, but we can collect it: might be useful later
    for fn in args.files:
        warncnt, newinstcnt = 0, 0
        openf = gzip.open if fn.endswith(".gz") else open
        try:
            with open(fn, mode="rt", encoding="utf-8") as fd:
                for line in fd:
                    if "ShardingIpv6BindingExpiration" in line and "Session not found:" in line:
                        # "Session not found:" just a little sanity in case there are other error msg in this class
                        container, *_, session, _, ipv6 = line.split()

                        warncnt += 1
                        if ipv6 not in instances:
                            # potential bug but unlikely: ip gets reused with another session
                            try:
                                instances[ipv6] = [session, container, int(session.split(";")[1])]
                                newinstcnt += 1
                            except:
                                error(args, f"Unexpected line: {line}")
                            
        except:
            error(args, f"{fn}: unable to open for reading")
            continue
        debug(args, f"{fn}: parsed exceptions: {warncnt} uniq exceptions: {newinstcnt}")

    if len(instances) == 0:
        info(args, "No ShardingIpv6BindingExpiration exceptions found")
        sys.exit(1)

    if args.summarize or args.all:    
        sum_prefixes = {}
        for ip_pref in instances.keys():
            summarized = ip_pref[:-ip_pref[::-1].index(":")-1]
            sum_prefixes[summarized] = sum_prefixes.get(summarized, 0) + 1

        info(args, f"{'IP PREFIX':16} COUNT")
        for ip_pref in sorted(sum_prefixes.keys()):
            info(args, f"{ip_pref}   {sum_prefixes[ip_pref]:5}")
        info(args, "")

    if args.time or args.all:
        epochs = [v[2] for v in instances.values()]
        contiguous = contiguous_blocks(epochs, args.block)
        debug(args, f"contiguous blocks: {contiguous}")

        info(args, f"{'START':^19} - {'END':^19}   COUNT")
        for s, e in contiguous:
            in_range = [etime for etime in epochs if s <= etime <= e]
            
            def ftime(t: int):
                return DT.datetime.fromtimestamp(t).strftime("%Y-%m-%dT%H:%M:%S") 
            info(args, f"{ftime(s)} - {ftime(e)}   {len(in_range)}")

        info(args, "")
    if args.each or args.all:
        info(args, f"{'IP PREFIX':<24}  SESSION ID")
        for ip_pref in sorted(instances.keys()):
            info(args, f"{ip_pref:<24}   {instances[ip_pref][0]}")
        info(args, "")

    if args.host or args.all:
        hosts = [h[:h.index(";")] for h, *_ in instances.values() if ";" in h]
        uniq_hosts = sorted(set(hosts))
        longest = max([len(h) for h in uniq_hosts])
        info(args, f"{'ENDPOINT HOST':<{longest}}   COUNT")
        for uh in uniq_hosts:
            cnt = len([_ for h in hosts if h == uh]) 
            info(args, f"{uh:<{longest}}   {cnt}")
        info(args, "")
        
    if not args.host and not args.block and not args.each and not args.summarize:
        info(args, f"Unique ShardingIpv6BindingExpiration WARNs found: {len(instances)}")
    sys.exit(0)
        
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Parse ShardingIpv6BindingExpiration errors from con logs")
    ap.add_argument("-t", "--time", action="store_true", help="Provide analysis on epoch time in sessions")
    ap.add_argument("files", nargs = "+", help="consolidated log files [gzip'd or not is fine]")
    ap.add_argument("-v", "--verbose", action="store_true", help="Print some debugging messages to stderr")
    ap.add_argument("-s", "--summarize", action="store_true", help="Summarize IPv6 prefixes into /24 groups")
    ap.add_argument("-q", "--quiet", action="store_true", help="Suppress all output [for scripting]")
    ap.add_argument("-b", "--block", type=int, default=5, help="Seconds apart for determinining time blocks (default: 5)")
    ap.add_argument("-e", "--each", action="store_true", help="Print each individual prefix and the associated session")
    ap.add_argument("-H", "--host", action="store_true", help="Analysis on hosts in session IDs")
    ap.add_argument("-a", "--all", action="store_true", help="Equivalent to -sbeH")
    args = ap.parse_args()
    main(args)
