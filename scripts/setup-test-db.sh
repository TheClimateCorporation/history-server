#!/bin/bash -ex
export PGPASSWORD=${PGPASSWORD:-"mysecretpassword"}
export PGHOST=${PGHOST:-"localhost"}
export PGROLE=${PGROLE:-"postgres"}

##
# these environment variables <service>_port_<port>_tcp_addr are set
# by Docker Compose.

if [[ "$POSTGRES_PORT_5432_TCP_ADDR" ]]; then
    export PGHOST=$POSTGRES_PORT_5432_TCP_ADDR
fi

# might already exist
set +e
psql -h $PGHOST -U ${PGROLE} -c 'create database historyserverdb'
psql -h $PGHOST -U ${PGROLE} -c "create user historyserverrole with password 'mysecretpassword'"
psql -h $PGHOST -U ${PGROLE} -c 'grant all privileges on database historyserverdb to historyserverrole'

# unwind any applied migrations
./unmigrate-db.sh

psql -h $PGHOST -U ${PGROLE} historyserverdb -f ../schema/drop.sql

set -e
# Load the schema into the db.

psql -h $PGHOST -U historyserverrole historyserverdb -f ../schema/history.sql

