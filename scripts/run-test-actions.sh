#!/bin/bash -e

READLINK=${READLINK:-"readlink"}
cd $(dirname $(${READLINK} -f $0))

##
# these environment variables <service>_port_<port>_tcp_addr are set
# by Docker Compose.

if [[ "$POSTGRES_PORT_5432_TCP_ADDR" ]]; then
    export PGHOST=$POSTGRES_PORT_5432_TCP_ADDR
fi

./setup-test-db.sh

./migrate-db

./cli-tests.sh

# Set Host for backend.py to pick it up.
if [[ ! -z $WEB_PORT_5000_TCP_ADDR ]]; then
    export WEB_SERVER_HOST=$WEB_PORT_5000_TCP_ADDR
fi

./swagger-tests.sh

python ./ephemeral-tests.py

# if we are NOT running as an docker-compose test (i.e, we're probably
# in development) , reset the hostname.
if [[ -z "$POSTGRES_PORT_5432_TCP_ADDR" ]]; then
    # recreate the system for another iteration of the tests.
    psql -h $PGHOST -U ${PGROLE} historyserverdb -f ../schema/drop.sql
    ./unmigrate-db.sh
    psql -h $PGHOST -U ${PGROLE} historyserverdb -f ../schema/history.sql
    ./migrate-db
fi
