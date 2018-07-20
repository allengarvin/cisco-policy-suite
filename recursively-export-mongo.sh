#!/bin/bash

# Trying to find where something is in the admin DB. Anyone that needs this, use it freely
# Author: "Allen Garvin" <algarvin@cisco.com> 2018-05-15

for dbset in {1..5}; do
    grep -q ADMIN-SET${dbset}-END /etc/broadhop/mongoConfig.cfg || continue
    member=$(awk "/ADMIN-SET${dbset}.$/,/ADMIN-SET${dbset}-END/" /etc/broadhop/mongoConfig.cfg | grep MEMBER1 | awk -F= '{print $2}')
    master=$(echo "db.isMaster().primary" | mongo --quiet $member)
    for db in $(echo "show dbs" | mongo --quiet $master | awk '{print $1}'); do
        if [[ $db == local ]]; then continue; fi
        for table in $(echo "show tables" | mongo --quiet $master/$db); do
            mkdir -p admin$dbset/$db
            echo Dumping $master/$db/$table to admin$dbset/$db/$table.json
            mongoexport --host ${master%:*} --port ${master#*:} --db $db --collection $table > admin$dbset/$db/$table.json
        done
    done
done

