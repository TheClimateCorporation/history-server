# notes for maintainers and admins

## development

to do development:

```
docker-compose up -d postgres
./scripts/setup-test-db.sh
python ./src/web.py
```

Note that ./src/history.py is a client which connects directly to the
database directly.


*go ye and hack the good hack.*


## continuous integration

Execute `./scripts/run-ci-tests.sh` to build a sandboxed environment and
run tests within it.

## new cloud environment
As part of standing up a new environment, create a new Postgres
instance and run these commands:

```
create user historyserverrole with password 'somepassword';
```

Then connect with historyserverrole and create database historyserverdb;

Notice the difference in quotation marks.


Then, manually load schema/history.sql into the server.

`psql -1 -U historyserverrole historyserverdb -f ./schema/history.sql`

## upgrading

The history server is fed by an webapp cluster.  When making
*breaking* changes, ensure that the ingest cluster application count
is downsized to 0 and changes made on the ingest-side to conform to
the expectations.

Example migration:

`psql -1 -U  historyserverrole historyserverdb -f ./schema/000-migration.sql`

Note the `-1` - this performs the migration as a transaction.

## read only user
Production:

<Postgres Instance Name>

username: readonlyuser
password: hunter2

can only do SELECT

### howto SQL


create role readonlyuser with login password hunter2
nosuperuser inherit nocreatedb nocreaterole noreplication valid until 'infinity';


-- this needs to be run in with the historyserverrole user.

grant connect on database historyserverdb to readonlyuser;
grant usage on schema public to readonlyuser;
grant select on all tables in schema public to readonlyuser;
grant select on all sequences in schema public to readonlyuser;
