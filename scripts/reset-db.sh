#!/bin/bash

./scripts/unmigrate-db.sh
psql -h localhost -U historyserverrole historyserverdb -f schema/drop.sql
psql -h localhost -U historyserverrole historyserverdb -f schema/history.sql
./scripts/migrate-db
