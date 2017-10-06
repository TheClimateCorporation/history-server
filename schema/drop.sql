-- run this script to DROP the schema
drop table if exists schema_migrations;

drop table if exists artifact cascade;
drop table if exists deploy cascade;
drop table if exists build cascade;
drop table if exists promote cascade;

drop table if exists versioned_thing cascade;
drop table if exists thing cascade;
drop type if exists thing_type cascade;
drop type if exists thing_enum cascade;
drop type if exists environment_enum cascade;
drop type if exists version_enum cascade;
drop table if exists servername cascade;
drop table if exists version cascade;
