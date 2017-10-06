#!/bin/bash -ex

export PGPASSWORD=${PGPASSWORD:-"mysecretpassword"}
export PGHOST=${PGHOST:-"localhost"}
export PGROLE=${PGROLE:-"postgres"}

READLINK=${READLINK:-"readlink"}
pushd $(dirname $(dirname $(${READLINK} -f $0)))/schema

for migration in $(ls -r -1 -v | grep -E '[0-9]{3}' | grep -E 'down.sql$'); do
    echo "Applying un-migration ..." $migration
   psql  -U historyserverrole historyserverdb < $migration
done

popd
