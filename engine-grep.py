#!/usr/bin/env python2

# This is for pulling complete records from the consolidated-engine.log based on patterns.
# This is also the first non-trivial python program I ever wrote, in 2015. It's very unpythonic.
# Someday I'll recode it.

import os, sys, errno, re, getopt, time, signal

final_return = False
grep_patterns = []
doc_start_re = re.compile("^[^ ]+ +\[[^]]+\] =+$")
doc_end_re = re.compile("^=+$")

def sig_handler(signal, frame):
    sys.exit(0)

def grep_doc(opts, doc):
    re_matches = dict(zip(grep_patterns, [False] * len(grep_patterns)))
    re_match = False

    for line in doc:
        if re_match == True and not opts["opt_and"]:
            break
        for pat in grep_patterns:
            if pat.search(line):
                re_match = True
                re_matches[pat] = True
                if not opts["opt_and"]:
                    break
    if opts["opt_invert"]:
        re_match = not re_match    
    if re_match and not opts["opt_and"]:
        final_return = True
        print '\n'.join(doc)
        if opts["opt_quit"]:
            sys.exit(0)
    if re_match and opts["opt_and"] and not False in re_matches.values():
        final_return = True
        print '\n'.join(doc)
        if opts["opt_quit"]:
            sys.exit(0)
        

def read_and_grep(opts, fn, fd):
    global doc_start_re, doc_end_re
    doc_start = False
    line = fd.readline()
    doc = False
    while line:
        line = line.rstrip('\r\n')
        if doc_start_re.match(line):
            doc_start = True
            doc = [line]
        elif doc_start == True:
            doc += [ line ]
            if doc_end_re.match(line):
                grep_doc(opts, doc)
                doc = False
                doc_start = False
        line = fd.readline()
        if doc and len(doc) > 3000:
            print("*** File %s doesn't appear to be consolidated-engine log." % fn)
            sys.exit(1)

def grep(opts, fn):
    try:
        fd = open(fn, "r")
    except:
        print("%s: Unable to read or access", fd)
        sys.exit(1)
    orig_stat = os.stat(fn)

    read_and_grep(opts, fn, fd)

    if opts["opt_tailf"]:
        current_pos = fd.tell()
        while True:
            time.sleep(0.1)
            if os.path.isfile(fn):
                f_stat = os.stat(fn)
            else:
                continue

            if orig_stat.st_ino != f_stat.st_ino:
                try:
                    fd = open(fn, "r")
                except:
                    continue
                orig_stat = f_stat
                current_pos = 0
            if f_stat.st_size < current_pos:
                fd.seek(0)

            if f_stat.st_size == current_pos:
                continue

            read_and_grep(opts, fn, fd)
        # tailf option end
            
        

def display_short_help(cmd):
    print("Usage: %s [options] PATTERN [file(s)]" % cmd)
    print("Try '%s --help' for more information." % cmd)
    sys.exit(1)

def display_help(cmd):
    print("Usage: %s [options] PATTERN [file(s)]" % cmd)
    print("  If no filenames are given, default will be to use consolidated-engine.log")
    print("Options:")
    print("  -e PATTERN, --regexp=PATTERN")
    print("        Use PATTERN as the pattern. This can be used to specify multiple")
    print("        search patterns")
    print("  -a, --and")
    print("        For multiple patterns, make them act as a logical 'and' (default: off)")
    print("        Warning: slower")
    print("  -F FILE, --file FILE")
    print("        Obtain patterns from FILE, one per line. [NOT YET IMPLEMENTED]")
    print("  -v, --invert-match")
    print("        Invert the sense of matching, to select non-matching documents")
    print("  -i, --ignore-case")
    print("        Ignore case distinctions in PATTERN")
    print("  -q, --quit")
    print("        Exit after the first match")
    print("  -f, --follow")
    print("        Follow in the manner of tail -f. If truncated, it will")
    print("        seek back to beginning")
    print("  -w FILE, --write FILE")
    print("        write output to FILE instead of to standard out.")
    print("        Instead, stdout will print a note every time a match is found")
    print("        NOT YET IMPLEMENTED")
    sys.exit(0)

def main(argc, argv):
    global grep_patterns, final_return
    if argc == 1:
        display_short_help(argv[0])

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGPIPE, sig_handler)

    options = { "opt_icase" : False, "opt_invert" : False, 
        "opt_ifile" : [], "opt_patterns" : [], "opt_quit" : False,
        "opt_follow" : False, "opt_outfile" : False, "opt_tailf" : False,
        "opt_and" : False,
        }

    try:
        opts, args = getopt.gnu_getopt(argv[1:], "F:h?ive:qw:fa", 
            ["file=", "help", "ignore-case", "invert-match", "regexp=", "quit",
             "write=", "follow", "and"])
    except getopt.GetoptError:
        display_short_help(argv[0])

    for opt, arg in opts:
        if opt in ("-h", "-?", "--help"):
            display_help(argv[0])
        elif opt in ("-v", "--invert-match"):
            options["opt_invert"] = True
        elif opt in ("-e", "--regexp"):
            options["opt_patterns"] += [ arg ]
        elif opt in ("-F", "--file"):
            options["opt_ifile"] += [ arg ]
        elif opt in ("-i", "--ignore-case"):
            options["opt_icase"] = True
        elif opt in ("-a", "--and"):
            options["opt_and"] = True
        elif opt in ("-q", "--quit"):
            options["opt_quit"] = True
        elif opt in ("-w", "--write"):
            options["opt_outfile"] = arg
        elif opt in ("-f", "--follow"):
            options["opt_tailf"] = True;
       

    if len(options["opt_ifile"]) == 0 and len(options["opt_patterns"]) == 0:
        if len(args) == 0:
            display_short_help(argv[0])
        else:
            options["opt_patterns"] = [ args[0] ]
            args = args[1:]

    if len(options["opt_ifile"]) > 0:
        for f in options["opt_ifile"]:
            try:
                fd = open(f, "r")
            except:
                print("%s: unable to open for reading" % f)
            line = fd.readline()
            while line:
                options["opt_patterns"] += [ line.rstrip('\r\n') ]
                line = fd.readline()

    for p in options["opt_patterns"]:
        try:
            if options["opt_icase"]:
                regex = re.compile(p, re.IGNORECASE)
            else:
                regex = re.compile(p)
        except:
            print("%s: invalid regexp" % p)
            sys.exit(1)
        grep_patterns += [ regex ]
            
    input_files = []
    if len(args) == 0:
        if os.path.isfile("/var/log/broadhop/consolidated-engine.log"):
            input_files = ["/var/log/broadhop/consolidated-engine.log"]
        elif os.path.isfile("./consolidated-engine.log"):
            input_files = ["./consolidated-engine.log"]
        else:
            print("Error: no files given, no consolidated-engine.log found")
            sys.exit(1)
    else:
        input_files = args
        if len(input_files) != 1 and options["opt_tailf"] == True:
            print("Error: -f option only works on exactly one file currently.");
            sys.exit(1);

    for fn in input_files:
        if os.path.isfile(fn) and os.access(fn, os.R_OK):
            grep(options, fn)
        else:
            print("%s: files does not exist or is not readable" % fn)

    if final_return:
        sys.exit(0)
    else:
        sys.exit(1)
if __name__ == "__main__":
    main(len(sys.argv), sys.argv)

