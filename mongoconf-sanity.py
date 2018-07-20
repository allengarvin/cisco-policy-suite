#!/usr/bin/python

# Customer requested sanity check for mongoConfig.cfg that should highlight
# a number of possible problems.
# Author: "Allen Garvin" <algarvin@cisco.com>
# Date: 2018-02-19
# NOTE: This is not official Cisco software, and is supposed by no one
#       except the author

import sys, argparse, re

try:
    import pymongo
except:
    print("Unable to import pymongo. Try running this from pcrfclient")
    sys.exit(1)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class mongo_set:
    values = dict()
    line_number_open = -1
    line_number_close = -1
    lines = []

    def __init__(self, name, lno):
        self.name = name
        self.line_number_open = lno

    def add_assignment(self, lv, rv):
        self.values[lv] = rv


def print_error(lno, line, msg):
    print("[{0}line #{1}{2}]".format(bcolors.FAIL, lno, bcolors.ENDC))
    print(">>>{0}".format(line))
    print("Error: {0}".format(msg))

def check_syntax(text):
    error_cnt = 0
    mongo_sets = []

    in_sec = False
    in_sec_obj = None

    open_re = re.compile("^\s*\\[([A-Za-z]+-SET\d+)\\]\s*$")
    close_re = re.compile("^\s*\\[([A-Za-z]+-SET\d+-END)\\]\s*$")
    white = re.compile("^\s*$")
    assign_re = re.compile("^\s*([A-Za-z_][A-Za-z0-9_]+)\s*=\s*([^\s]+)\s*$")

    for lno, l in enumerate(text.splitlines()):
        if "[" in l and "]" in l:
            if open_re.match(l):
                if in_sec:
                    print_error(lno, l, "New set open {0} when previous set {1} wasn't closed.".format(open_re.match(l).group(1), in_sec))
                    error_cnt += 1

                in_sec = open_re.match(l).group(1)
                in_sec_obj = mongo_set(in_sec, lno)
                in_sec_obj.lines.append(l)

            elif close_re.match(l):
                cl_sec = close_re.match(l).group(1)
                if cl_sec != in_sec + "-END":
                    print_error(lno, l, "Closing setname {0} does not match opening {1}".format(cl_sec, in_sec))
                    error_cnt += 1
                else:
                    in_sec_obj.line_number_close = lno
                    in_sec_obj.lines.append(l)
                    mongo_sets.append(in_sec_obj)

                in_sec = False
                in_sec_obj = None
            else:
                print_error(lno, l, "Invalid format for open/close label")
                error_cnt += 1
            continue
        if white.match(l):
            continue
        if not in_sec:
            print_error(lno, l, "Non-whitespace outside SET block")
            error_cnt += 1
            continue
        in_sec_obj.lines.append(l)

        if not assign_re.match(l):
            print_error(lno, l, "Non-assignment in {0} block".format(in_sec))
            error_cnt += 1
            continue
        av = assign_re.match(l)
        lvalue = av.group(1)
        rvalue = av.group(2)
        in_sec_obj.add_assignment(lvalue, rvalue)

    if error_cnt > 0:
        print("Parse summary: errors found: {0}     Sets found: {1}".format(error_cnt, len(mongo_sets)))
    else:
        print("Parse summary: no errors found.      Sets found: {0}".format(len(mongo_sets)))
    return mongo_sets

def check_sets(mongo_sets):
    for m_set in mongo_sets:
        print "\n".join(m_set.lines)

def main(args):
    with open(args.file) as fd:
        contents = fd.read()
    mongo_sets = check_syntax(contents)
    if len(mongo_sets) == 0:
        print("No mongo sets found. Aborting. Is this a mongoConfig?")
        sys.exit(1)
    check_sets(mongo_sets)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Examine mongoConfig.cfg for errors or problems")
    parser.add_argument("-f", "--file", default="/etc/broadhop/mongoConfig.cfg", help="mongoConfig.cfg file")
    args = parser.parse_args()
    main(args)

