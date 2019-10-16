#!/bin/bash

##########################################################################
# Name: show_peers.sh
# Author: Yousif.Aluzri@Cisco.COM
# Designed by: Rohit Jain (rohitja@Cisco.COM), Yousif.Aluzri@Cisco.COM
# Version: 1.0
# Date: Thu May  7 21:35:00 PDT 2015
# File Mode: 555
#
# Purpose: Report on diameter peering state for
#          lb0x qns processes.
#
# Summary: User specifies target lb0x node(s) and
#          script connects to target, to identify the
#          qns-x processes running, and determine their
#          corresponding osgi ports.
#
#          Script then connects to each osgi port of
#          each target VM, and runs the showPeers command
#          to list peer state. Script then processes
#          this output.
#
###################################################
# Change Log:
#############
# Version 2.2 (Wed Oct 12 2019)
#  -Author: yjuarezh@cisco.com
#  - Yeimi Juarez Hernandez
#  -Fixed for CPS 19.4
#  -
# Version 2.1 (Wed Nov 15 10:54:00 MST 2017)
#  -Author: lelee2@cisco.com
#  -Added support for Re interace (Relay) with application-id of 1
#  -Modified verbose mode to display the diameter network's IPv6 address
#
# Version 2.0 (Tues October 3 20:17:00 MST 2017)
#  -Author: lelee2@cisco.com
#  -Updated to include lb03 and lb04
#  -Replace Sy' with Sh
#  -Removed Sd interface
#  -Modified verbose mode to display the diameter network's IPv6 address
#
# Version 1.0 (Thu May  7 21:35:00 PDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Needs further refinements.
#  -IP addresses are only provided in verbose mode.
#  -Cleaned up some portions of the code.
#
# Version 0.9 (Tue May  5 23:02:16 PDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -We're still in Proof of concept mode, but now
#   have corrected a behavior so that if user
#   specified --all and then explicit interfaces,
#   the script only outputs data for those interfaces.
#
# Version 0.8 (Tue May  5 22:53:42 PDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Proof of concept, added instance-id data as the
#   local hostname column. -Need to clean this up.
#
# Version 0.7 (Tue May  5 13:43:00 PDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Updated the error messages for --count and --interval
#   flags.
#  -Implemented --summary mode, which just prints
#   connection summary, and not specific per-process
#   details.
#  -Updated formatting of SUMMARY table (less clutter).
#  -Moved SUMMARY table to its own function.
#  -Added support of 3GPP Sy flag.
#  -Differentiated --sy and --syp input flags.
#  -Peppered a bit of performance tweaks, here and there.
#  -Bug Fix: Sorting of lb output is now
#   alphabetical.
#  -Bug Fix: Sorting of interface data is now
#   unique and alphabetical.
#  -Bug Fix: The --interval flag was broken; works now.
#
# Version 0.6 (Thu Apr 23 17:14:08 EDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Added a summary table of interfaces in an OKAY state,
#   for each iteration of the loop.
#  -When loopking, the default interval is now 2s,
#   and can be overridded using the new --interval flag.
#  -Script needs to be overhauled in order to have a
#   better flow.
#  -Changed Diameter Endpoint column so it now prints
#   the qns-<x> process.
#
# Version 0.5 (Mon Apr 13 20:42:24 MDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Updated AppID for Sd interface.
#  -Intruduced __exitGracefully function
#   to clean up temp dir on unexpected exits.
#
# Version 0.4 (Sun Apr 12 23:41:48 MDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Removed the interactive diagnostic which I
#   had accidently left in.
#  -We now have a clusmy approach to dynamic
#   column widths for the realm and hostname
#   colums. The widest value returned determines
#   the column width for the entire output.
#  -Included an Example in the __printUsage
#   function.
#  -Color coded two usage errors, which were
#   previously uncolored.
#  -Still in proof of concept mode. If this passes
#   review, will update to make content simpler and
#   more scalable for other fields.
#  -Have been ignoring the Vendor Name field, so far!
#  -Net round needs to make this faster.
#
# Version 0.3 (Tue Jun 30 23:24:58 MDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Updated script so it can handle a single
#   osgi showPeers reporting multiple peers
#   for a given process.
#
# Version 0.2 (Mon Apr  6 02:33:58 MDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Still in proof of concept mode, and
#   need:
#     -Better error analysis.
#     -Cuurently too much repition of headers,
#      and independent definitions of column
#      widths.
#     -Report on iomanager process.
#  -Renamed to show_peers.sh
#  -Added date to output header.
#  -Range of ports is now dynamically generated
#   based on the number of monit qns-x processes
#   running.
#  -Added color coding: Red for errors, green for
#   OKAY state, red for all other states.
#  -Arguments '--lb01' and '--lb02' are now mutually
#   exclusive. To get data for both lb0x nodes, user
#   must specify '--all',
#  -Implemented looping: both indefinete ('--loop')
#   and limited ('--count <x>').
#  -Flags are no all in lower case.
#  -Impemented a (limited) verbose mode;
#   same data, but now prints Vendor ID.
#
# Version 0.1 (Wed Apr  1 01:53:37 MDT 2015)
#  -Author: Yousif.Aluzri@Cisco.COM
#  -Proof of concept for script.
#  -Major problems now are needing to ensure
#   lbHostList and interfaceList arrays
#   have elements which are unique.
#  -Missing a usage function.
#  -Missing a graceful exit function.
#  -Neet error handling: script can't tell if
#   host it tried to connect to is offline, or even
#   if it's a resolvable host name. -Should be able
#   to detect these scenarios, and report.
#  -Need better comments.
##########################################################################

##########################################################################
# BEGIN PREAMBLE
##########################################################################
declare -A         lbHostList
declare -A default_lbHostList=([lb01]=
                               [lb02]=
                               [lb03]=
                               [lb04]=)

declare -A         interfaceList
declare -A default_interfaceList=([Gx]=16777238
                                  [Rx]=16777236
                                  [Sy]=16777302
                                  [Sh]=16777217
                                  [Re]=1)


timestamp=$(date '+%Y%m%d_%H%M%S')
basename=$(basename $0 .sh)
tmpDir=/tmp/${basename}.${timestamp}.$$
sleepInterval=2
verboseMode=0
allMode=0
loopMode=0
loopCounter=1
loopCounterMax=1
fieldSep='#############################################################################'

# Output text formatting.
formatRed=$(echo -e '\e[31m')
formatGreen=$(echo -e '\e[32m')
formatReverse=$(echo -e '\e[7m')
formatBold=$(echo -e '\e[1m')
formatOff=$(echo -e '\e[0m')


# Function to clean up any clutter we create.
__exitGracefully () {
    # Clean up $tmpDir, if it exists.
    if [[ -d "$tmpDir" ]]
    then
        wait
        rm -rf $tmpDir 2>/dev/null
    fi

    echo -e "\n\n"
    stty sane

    return
}


# Give us a graceful exit if they interrupt or terminate us.
trap '__exitGracefully ; exit 1' INT TERM
##########################################################################
# END PREAMBLE
##########################################################################

##########################################################################
# BEGIN FUNCTIONS
##########################################################################

#################################################################
#
# Function: __printUsage
#
# Summary: A simple function to print command usage.
# Input:   <none>
# Output:  Command syntax.
#
#################################################################
__printUsage () {


    cat <<EOF

  USAGE: $0 --lb01|--lb02|--lb03|--lb04|--all [OPTIONS]


  SUMMARY: Report on Diameter interface peering for
           either lb01, lb02, lb03, or lb04.



  REQUIRED INPUT: Exactly one of the following three arguments is required.

    --all       :Report on all Diameter interfaces for both lb01 and lb02.
    --lb01      :Report on only lb01 peer states.
    --lb02      :Report on only lb02 peer states.
    --lb03      :Report on only lb03 peer states.
    --lb04      :Report on only lb04 peer states.

  OPTIONS:

    --gx        :Provide Gx peering state.
    --rx        :Provide Rx peering state.
    --sy        :Provide Sy peering state.
    --sh        :Provide Sh peering state.

    --count <x>     :Repeat <x> number of times.
    --interval <x>  :Wait <x> seconds bewteen sucessive tries.
    --loop          :Repeat indefinetly.
    --summary       :Just print summary of total connections.
    --verbose       :Verbose Mode: Provide IP local and remote host IP
                     addresses, and include additional information on
                     peer state.

   EXAMPLES:

     $0 --lb01 --gx

     =============================================================================
     lb01 Gx-Peers (AppID=16777238)
     ------------------------------
        Diameter  Remote              Remote         Peer
        Endpoint  Host                Realm          State
        --------  ------------------  -------------  -------
        1         sea.wa.pas.gx       sea.pas.gx     OKAY
        2         sea.wa.pas.gx       sea.pas.gx     OKAY

EOF
    return 0
}


#################################################################
#
# Function: __parseInput
#
# Summary: Go through the command line input.
# Input:   <none>
# Output:  <none>
#
#################################################################
# Parse through command line inputs.
__parseInput () {

    # Make sure we were given exactly one of our required input
    # arguments (--all, --lb01, --lb02, --lb03, or --lb04).
    if [[ "$(echo "$*" | grep -E -o "\-\-\<(lb0[1234]|all)\>" | wc -l)" != 1 ]]
    then
        echo -e "\n\t${formatRed}***ERROR: $0 needs exactly one \"REQUIRED INPUT\" argument.${formatOff}"
        __printUsage
        exit 1
    fi

    # Go through and process each option.
    while [[ "${#}" -ne '0' ]]
    do
        case $1 in
            --all)
                allMode=1
                shift 1
                ;;
            --count)
                if [[ ! $2 ]] || [[ "x$(echo $2 | tr -d '[:digit:]')" != 'x' ]]
                then
                    echo -e "\n\t${formatRed}***ERROR: '--count' requires an argument which is an integer${formatOff}."
                    __printUsage
                    exit 1
                else
                    loopCounterMax=$2
                fi
                shift 2
                ;;
            --interval)
                if [[ ! $2 ]] || [[ "x$(echo $2 | tr -d '[:digit:]')" != 'x' ]]
                then
                    echo -e "\n\t${formatRed}***ERROR: '--interval' requires an argument which is an integer${formatOff}."
                    __printUsage
                    exit 1
                else
                    sleepInterval=$2
                fi
                shift 2
                ;;
            --lb01)
                lbHostList[lb01]=
                shift 1
                ;;
            --lb02)
                lbHostList[lb02]=
                shift 1
                ;;
            --lb03)
                lbHostList[lb03]=
                shift 1
                ;;
            --lb04)
                lbHostList[lb04]=
                shift 1
                ;;
            --loop)
                loopMode=1
                shift 1
                ;;
            --gx)
                interfaceList[Gx]=16777238
                shift 1
                ;;
            --rx)
                interfaceList[Rx]=16777236
                shift 1
                ;;
            --sy)
                interfaceList[Sy]=16777302
                shift 1
                ;;
            --sh)
                interfaceList[Sh]=16777217
                shift 1
                ;;
            --summary)
                summaryMode=1
                shift 1
                ;;
            --verbose)
                verboseMode=1
                shift 1
                ;;
            *)
                echo -e "\n\t${formatRed}***ERROR: Unrecognized option: \"${1}\"${formatOff}\n"
                __printUsage
                exit 1
                ;;
        esac

    done

    # If we're in all mode, then select all lb0x hosts
    # and all Diameter interfaces.
    if [[ "$allMode" ==  '1' ]]
    then
       for i in ${!default_lbHostList[@]}
        do
            lbHostList[$i]=
        done
    fi

    # Give us a big number of iterations, if they
    # call loop mode.
    if [[ "$loopMode" ==  '1' ]]
    then
        loopCounterMax=4294967296
    fi

    # If we've made it this far and the user didn't
    # specify any hosts, then use ${default_lbHostList[@]}
    # (should be all hosts.
    if [[ "${#interfaceList[@]}" == 0 ]]
    then
        for i in "${!default_interfaceList[@]}"
        do
            interfaceList[$i]=${default_interfaceList[$i]}
        done
    fi



    return
}


#################################################################
#
# Function: __makeTmpDir
#
# Summary: Create temp dirs.
# Input:   List of target lb0x nodes.
# Output:  The directory $tmpDir/lb0x
#
#################################################################
__makeTmpDir () {

    # Create temporary working dirs.
    for i in $* header
    do
        mkdir -p $tmpDir/$i 2>/dev/null

        if [[ ! -d "$tmpDir/$i" ]]
        then
            echo -e "\n\t***ERROR: Could not create temp dir '$tmpDir/$i'\n"
            exit 1
       fi
    done

    return
}


#################################################################
#
# Function: __collectHostData
#
# Summary: ssh to target lb0x, and identify active osgi ports
# Input:   lb0x
# Output:  $tmpDir/lb0x/getPortData_out.txt
#          $tmpDir/lb0x/getPortData_err.txt
#
#################################################################
__collectHostData () {

    # Connect to the lb0x node and identify which diameter_endpoint
    # processes are running.
    for i in $*
    do
        ssh -o ConnectTimeout=1 $i 'monit summary 2>/dev/null ; ps -ef | grep java | grep diameter 2>/dev/null' >$tmpDir/${i}/collectHostData_out.txt 2>$tmpDir/${i}/collectHostData_err.txt
    done

    return
}


#################################################################
#
# Function: __collectPeerData
#
# Summary: Connect to an osgi port and pull peer state data.
# Input:   $1: lb0x
# Output:  $tmpDir/lb0x/collectPeerData.txt
#
#################################################################
__getPortData () {
    local port
    local lb

    # Our money maker: Connect to peers and get
    # process connectivity data.
    for lb in $*
    do
        >$tmpDir/${lb}/getPortData_out.txt
        ###validate the output, bcs seems "Process" is not being taken in account

		for port in $(grep 'qns-[2-9]' $tmpDir/${lb}/collectHostData_out.txt 2>/dev/null| sed 's/.*qns-\([2-9]\).*/909\1/' 2>/dev/null| sort -nu 2>/dev/null | paste -s -)
		do
		   echo -n "$port " >> $tmpDir/${lb}/getPortData_out.txt
		done
    done
}

__collectPeerData () {
    local port
    local lb
    for lb in $*
    do
        for port in $(cat $tmpDir/${lb}/getPortData_out.txt)
        do
            echo "showPeers" | nc -w 1 $lb $port 2>/dev/null | grep -v osgi 2>/dev/null | grep '[[:alpha:]]' 2>/dev/null >$tmpDir/${lb}/collectPeerData-nc_${port}.txt &
		done
    done
return
}


__getInstanceId () {
    local port
    local lb
    for lb in $*
    do
        for port in $(cat $tmpDir/${lb}/getPortData_out.txt)
        do
           grep "\-console " $tmpDir/${lb}/collectHostData_out.txt 2>/dev/null | grep $port 2>/dev/null |  sed 's/.*adhop.run.instanceId=\([^ ]\+\) .*/\1/'  2>/dev/null >$tmpDir/${lb}/collectPeerData-id_${port}.txt &
        done
    done
}

__resolveHostnames () {
    local lb
    for lb in $*
    do
       for file in $tmpDir/${lb}/collectPeerData-id_*.txt
       do
#Updated to display the lb's IPv6 diameter address instead of the internal IPv4 address
#host=$(cat $file 2>/dev/null); getent hosts $(echo $host | sed 's/-[0-9]$//' 2>/dev/null) | awk -v host=$host '{print host " [" $1"]"}' 2>/dev/null > ${file}&
           host=$(cat $file 2>/dev/null); grep -m2 $(echo $host | sed -r "s/.*(lb[0-9][0-9]).*/\1/" 2>/dev/null) /etc/hosts | tail -n1 | awk -v host=$host '{print host " [" $1"]"}' 2>/dev/null > ${file}
       done
        for file2 in $tmpDir/${lb}/collectPeerData-nc_*.txt
        do
            > ${file2}_TMP
            while read rrealm rhost rest
            do
			    echo "$rrealm $rhost $(grep $rhost /etc/hosts 2>/dev/null| awk '{print "["$1"]"}') $rest" >> ${file2}_TMP &
            done < <(grep '[[:alpha:]]' $file2 2>/dev/null)
            wait
            mv ${file2}_TMP ${file2}
        done
    done
    return
}
__getHeaderLengths () {
    ##    # We take note of the width of the realm and hostname data,
    ##    # so we can later format our output columns to match them.
    local lb
    for lb in $*
    do
        awk '{ print length($1)}'  $tmpDir/${lb}/collectPeerData-nc_*.txt 2>/dev/null  >> $tmpDir/header/realm_column.txt 2>/dev/null &
        awk '{ print length($2" "$3)}'  $tmpDir/${lb}/collectPeerData-nc_*.txt 2>/dev/null  >> $tmpDir/header/hostnameR_column.txt 2>/dev/null  &
        awk '{ print length($0)}'  $tmpDir/${lb}/collectPeerData-id_*.txt 2>/dev/null  >> $tmpDir/header/hostnameL_column.txt 2>/dev/null  &
        wait
    done

    return
}



#################################################################
#
# Function: __getHostErrors
#
# Summary: Determined if we had any errors when connecting to
#          lb0x nodes.
# Input:   $tmpDir/lb0x/getPortData_err.txt
# Output:  <none>
#
#################################################################
__getHostErrors () {
    # There are only three (likely) scenarios under which
    # we expect our $tmpDir/${lbHost}/getPortData_err.txt
    # file to be non-zero length:
    #   1. Name Resolution: We couldn't resolve the hostname $lbHost.
    #   2. Connectivity: We were not able to ssh to $lbHost.
    #   3. Bad command: The command we tried to run on $lbHost returned
    #      an error.
    # We'll try to identify which of these three scenarios came about:
    if   [[ "$(grep 'Connection timed out' $tmpDir/${1}/getPortData_err.txt 2>/dev/null)" ]]
    then
        echo -e "  ${formatRed}$lbHost: ERROR: Could not get data from $lbHost${formatOff}\n"
    elif [[ "$(grep 'Could not resolve hostname' $tmpDir/${1}/getPortData_err.txt 2>/dev/null)" ]]
    then
        echo -e "  ${formatRed}$lbHost: ERROR: Could not resolve hostname $1${formatOff}\n"
    else
        echo -e "  ${formatRed}$lbHost: ERROR: Could not get data from $1${formatOff}\n"
    fi

    return
}


#################################################################
#
# Function: __printInterfaceHeader
#
# Summary: Print headers
# Input:  $1: $lbHost
#         $2: $interface
#         $3: $lengthLocalHost
#         $4: $lengthRemoteHost
#         $5: $lengthRealm
# Output: Header.
#
#################################################################
__printInterfaceHeader () {
        # Set up a header for the interface
        interfaceHeader="$1 ${2}-Peers (AppID=${interfaceList[${2}]})"
        interfaceHeaderLength=$(echo -n "$interfaceHeader" | wc -c)
        echo -en "  ${formatBold}$interfaceHeader${formatOff}\n  "

        for i in $(seq 1 $interfaceHeaderLength); do echo -n '-'; done; echo

        if [[ "$verboseMode" == '1' ]]
        then
            printf "     %-8s  %-${3}s  %-${4}s  %-${5}s  %-6s  %-7s\n" 'QNS ID' 'Local Host' 'Remote Host' 'Remote Realm' Vendor 'Peer State'
            echo -n '   '; for m in 8 $3 $4 $5 6 7 ; do echo -n '  '; printf '%0.s-' $(seq 1 $m); done
        else
            printf "     %-8s  %-${3}s  %-${4}s  %-${5}s  %-7s\n" 'QNS ID' 'Local Host' 'Remote Host' 'Remote Realm' 'Peer State'
            echo -n '   '; for m in 8 $3 $4 $5   7 ; do echo -n '  '; printf '%0.s-' $(seq 1 $m); done
        fi
            echo

        return
}


#################################################################
#
# Function: __printInterfaceData
#
# Summary: Print data
# Input:   $1: $lbHost
#          $2: qns-${interface}
#          $3: $endpointCounter
#          $4: $port
#          $5: $lengthLocalHost
#          $6: $lengthRemoteHost
#          $7: $lengthRealm
# Output:  The data we have all been waiting for!
#
#################################################################
__printInterfaceData () {
    local host
    local realm
    local vendorId
    local state
    local interfaceConnections

    if [[ ! -s "$tmpDir/${1}/collectPeerData-nc_${3}.txt" ]]
    then
        echo "${formatRed}ERROR: No data found for this endpoint (the $4)) process)!${formatOff}"
    else
        # See if this port contains any data for our target Diameter interface.
        connectionData=$(grep "\<${interfaceList[${2}]}\>"  $tmpDir/${1}/collectPeerData-nc_${3}.txt 2>/dev/null | sed 's/\r.*$//')
        if [[ -z "$connectionData" ]]; then echo "     $4     ${formatRed}WARNING: No connection found${formatOff}";else

            echo "$connectionData" | while read line
            do
                printf  "     %-8s  " $4

                read remoteHost remoteIP realm vendorId state <<< $(echo "$line" | awk '{print $2,$3,$1,$(NF-1),$NF}' 2>/dev/null )
                localHost=$(cat $tmpDir/${1}/collectPeerData-id_${3}.txt)

                if [[ "$verboseMode" == '1' ]]
                then
                     printLine="%-${5}s  %-${6}s  %-${7}s  %-6s  %-7s\n"
                else
                     vendorId=''
                     printLine="%-${5}s  %-${6}s  %-${7}s  %-7s\n"
                fi

                if [[ -z "$remoteHost" ]]
                then
                    echo "${formatRed}ERROR: $1 $2 interface not connected for this endpoint!${formatOff}"
                else
                    # Need to rethink this, it's a costly approach.
                    printf  "$printLine" "$localHost" "$remoteHost $remoteIP" $realm $vendorId $state \
                    | sed -e "s/OKAY/${formatGreen}OKAY${formatOff}/" \
                          -e "s/DOWN/${formatRed}DOWN${formatOff}/" \
                          -e "s/REOPEN/${formatRed}REOPEN${formatOff}/" \
                          -e "s/SUSPECT/${formatRed}SUSPECT${formatOff}/"
                fi
            done
        fi
    fi

    return
}



#################################################################
#
# Function: __printSummaryTable
#
# Summary: Print summary of data.
# Input:   <none>
# Output:  One row per lb, with one column per user specifed
#          interface.
#
#################################################################
__printSummaryTable () {
    # For each osgi port, retrieve peer data.
    echo -e "SUMMARY of Peers in ${formatGreen}OKAY${formatOff} State:\n"
    echo -n "                |"

    for interface in $(for i in "${!interfaceList[@]}"; do echo $i ; done | sort) ;  do printf "%-6s|"  "$(echo "  $interface" | sed "s/Prime/' /")" ; done
    echo -en "\n   -------------|" ;for interface in "${interfaceList[@]}" ;  do printf "%-6s|"  "------"   ;done

    for lbHost in $(for i in "${!lbHostList[@]}" ; do echo $i ; done | sort)
    do
        echo -en "\n     $lbHost peers |"
        for interface in $(for i in "${!interfaceList[@]}"; do echo $i ; done | sort)
        do
            count=$(($(grep -c "\<${interfaceList[$interface]}\>.*OKAY" $tmpDir/${lbHost}/collectPeerData-nc_*.txt 2>/dev/null| awk -F: '{print $2}' | paste -s - -d +)))
            printf "%-6s|" "  $count"
        done
        echo -en "\n   -------------|" ;for interface in "${interfaceList[@]}" ;  do printf "%-6s|"  "------"   ;done
    done
    echo -e "\n\n"

    return
}


##########################################################################
# END FUNCTIONS
##########################################################################

##########################################################################
# BEGIN MAIN
##########################################################################

# Parse command line input
__parseInput $*

# Make working dirs.
__makeTmpDir "${!lbHostList[@]}"


# Loop through each iteration of looping, which user wanted.
while [[ "$loopCounter" -le "$loopCounterMax" ]]
do

    clear
    # Print an interation-level header.
    dateStart=$(date '+%s')
    echo -e "##${fieldSep}\n${formatReverse}[$(date -d @${dateStart})]${formatOff}"

    # For each lb0x node, connect and pull down the
    # list of osgi ports which are up.
    __collectHostData ${!lbHostList[@]} &
    wait

    __getPortData ${!lbHostList[@]} &
    wait

    __collectPeerData "${!lbHostList[@]}" &
    wait

    __getInstanceId "${!lbHostList[@]}" &
    wait

    if [[ $verboseMode == 1 ]]
    then
        __resolveHostnames "${!lbHostList[@]}" &
        wait
    fi

    __getHeaderLengths  "${!lbHostList[@]}" &
    wait

	# This is a clumsy way to figure out the appropriate width
    # for our remote hostname and remote realm columns. This
    # needs to be cleaned up.
    lengthLocalHost=$(sort -r $tmpDir/header/hostnameL_column.txt | head -1)
    lengthRemoteHost=$(sort -r $tmpDir/header/hostnameR_column.txt | head -1)
    lengthRealm=$(sort -r $tmpDir/header/realm_column.txt | head -1)

	# Cycle through each of our $lbHost nodes and print a block of output.
    # Low grade approach to sorting the hash.
    for lbHost in $(for i in "${!lbHostList[@]}"; do echo $i ;done| sort)
    do
        # First verify there were no errors for this particular
        # $lbHost
        if [[ -s "$tmpDir/${lbHost}/getPortData_err.txt" ]]
        then
            __getHostErrors $lbHost
            continue
        fi

        if [[ $summaryMode != 1 ]]
        then
        # For this $lbHost, cycle through each of its Diameter interfaces.
            for interface in $(for j in "${!interfaceList[@]}"; do echo $j; done | sort)
            do
                # Start with Diameter endpoint 1 (ie, the qns-2 process).
                endpointCounter=2

                # Print an interface-level field seperator for this section of data.
                # Then print the header for that interface.
                echo "  ${fieldSep}" | sed 's/#/=/g'
                __printInterfaceHeader $lbHost $interface $lengthLocalHost $lengthRemoteHost $lengthRealm

                # For each port in this $lbHost's list of ports,
                # print the data captured for that port.
                for port in $(cat $tmpDir/${lbHost}/getPortData_out.txt)
                do
                    __printInterfaceData $lbHost $interface $port qns-${endpointCounter} $lengthLocalHost $lengthRemoteHost $lengthRealm
                    ((endpointCounter++))
                done
                echo
           done
           echo
       fi
    done

	__printSummaryTable

	# If we have additional loop iterations to go, then sleep
    if [[ $(($loopCounterMax - $loopCounter))  -ge 1 ]]
    then
        duration=$(($(date '+%s') - ${dateStart}))
        if [[ $duration -lt $sleepInterval ]]
        then
            sleep $(( $sleepInterval - $duration))
        fi
    fi

    ((loopCounter++))
done

# Clean up temp dirs.
if [[ "$(echo "$tmpDir" | grep "${timestamp}.$$" 2>/dev/null)" ]]
then
    rm -rf $tmpDir 2>/dev/null
fi

exit
##########################################################################
# END MAIN
##########################################################################
