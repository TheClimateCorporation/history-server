#!/bin/bash

cd $(dirname $(dirname $(readlink -f $0)))/scripts

# This script will fully seed an empty PG database with the current
# schema. It expects PGHOST  to be set
psql -U postgres -c 'create database historyserverdb'
psql -U postgres -c "create user historyserverrole with password 'mysecretpassword'"
psql -U postgres -c 'grant all privileges on database historyserverdb to historyserverrole'

export PGPASSWORD="mysecretpassword"
# initialize the
psql -U historyserverrole historyserverdb -f ../schema/history.sql

./migrate-db
