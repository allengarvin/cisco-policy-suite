#!/usr/bin/python

# This requires python-suds library, typically installed only on the lbs.
# Not official Cisco software. Only supported by Allen Garvin <algarvin@cisco.com>

from suds.client import Client
from suds.sax.element import Element
import argparse
import sys

def make_connect():
    c = Client("https://lbvip01:8443/ua/wsdl/UnifiedApi.wsdl")
    test_req = c.service.KeepAlive()
    if test_req.errorCode != 0:
        print("Test KeepAlive connection received error:\n")
        print(test_req.errorMessage)
        exit(1)
    return c

def main(argv):
    quota_name = ''

    verbose = False

    client = make_connect()


    if args.framed:
        rcode = "FramedIp"
        what = args.framed
    elif args.usum:
        rcode = "USuMCredential"
        what = args.usum
    elif args.netid:
        rcode = "NetworkId"
        what = args.netid
    elif args.mac:
        rcode = "MacAddress"
        what = args.mac
    elif args.user:
        rcode = "UserId"
        what = args.user
    else:
        print("No searches give. Use -h for help")
        sys.exit(1)


    rkey = client.factory.create('ns0:SessionKeyType')
    rkey.code = rcode + "Key"    
    rkey.primary = "false"

    rkeyf = client.factory.create('ns0:KeyFieldType')
    rkeyf.code = rcode[0].lower() + rcode[1:]
    rkeyf.value = what
    rkey.keyField = rkeyf
    # rkey.keyField = k
    

    print("Running query: ")
    print(rkey)
    try:
        req = client.service.QuerySession(key=rkey)
    except:
        print("QuerySession call failed")
        sys.exit(1)

    if "errorCode" in "req" and req.errorCode > 0:
        print("API error: %s" % req.errorMessage)
        sys.exit(1)
    elif not "session" in req:
            print("No session info in response: ")
            print(req)
            sys.exit(0)
    for i in req.session:
        if "sessionObject" in i and isinstance(i.sessionObject, list):
            so = i.sessionObject[0]
            if not args.quiet:
                print(so)
            #print(type(so))
            for j in so:
                for k in list(j):
                    if isinstance(k, list):
                        for l in k:
                            if "string" in l and isinstance(l.string, list) and len(l.string) > 1:
                                key = l.string[0]
                                value = l.string[1]
                                if key == "credentialId":
                                    id = value
    d = dict(networkId = id)
    breq = None
    sreq = None
    if args.balance:
        try:
            breq = client.service.QueryBalance(**d);
        except:
            print("No balance found for user %s" % id)
    if args.spr:
        try:
            sreq = client.service.GetSubscriber(**d)
        except:
            print("No subscriber info for user %s" % id)
    if breq and not args.quiet:
        print("---- Balance ----")
        print(breq)
    if sreq and not args.quiet:
        print("---- SPR ----")
        print(sreq)
    if args.remove:
        try:
            ssreq = client.service.StopSession(key=rkey)
        except:
            print("StopSession failed")
            sys.exit(1)
        print("--- Session removal request completed ---")
        if not args.quiet:
            print(ssreq)

                    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find session info for subscriber")
    parser.add_argument("-f", "--framed", help="Search based on framed IP")
    parser.add_argument("-u", "--usum", help="Search based on USuM")
    parser.add_argument("-n", "--netid", help="Search based on network id")
    parser.add_argument("-m", "--mac", help="Search on MacAdress")
    parser.add_argument("-i", "--user", help="Search on username")
    parser.add_argument("-q", "--quiet", help="Quiet (no records printed)", action="store_true")
    parser.add_argument("-r", "--remove", help="Stop session", action="store_true")
    parser.add_argument("-s", "--spr", help="Print SPR info for returned user", action="store_true")
    parser.add_argument("-b", "--balance", help="Print Balance info for returned user", action="store_true")

    args = parser.parse_args()
    main(sys.argv[1:])

#        "tags" : [
#                "FramedIpKey:framedIp:190.197.3.139",
#                "MSBMSubscriberIdKey:msbmSubscriberId:spatnett",
#                "MacAddressKey:macAddress:spatnett",
#                "MsisdnKey:msisdn:spatnett",
#                "USuMSubscriberIdKey:usumSubscriberId:5272017d4108d8fb5e002005",
#                "UserIdKey:userId:spatnett",
#                "diameterSessionKey:557176%3B3200582539%3B1465070171"
#        ],
#
#
