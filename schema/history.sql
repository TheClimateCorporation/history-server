----------------------------------------------------------------------
--- history.sql
--- schema for the history server.

CREATE TABLE IF NOT EXISTS schema_migrations(
    migration_key INTEGER,
CONSTRAINT migrations_uq UNIQUE(migration_key));

-- Increment this value in each migration file. Since it's unique,
-- dupeing or rerunning will generate an error.
INSERT INTO schema_migrations (migration_key) VALUES (0);


CREATE TYPE version_enum AS ENUM (
    'changeset',                    -- changeset for artifacts we create
    'package');                     -- debian packages, for example.

CREATE TABLE version(
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP WITH TIME ZONE,
    version_type VERSION_ENUM NOT NULL,
    version TEXT NOT NULL,
    CONSTRAINT version_uq UNIQUE (version));

CREATE TABLE servername(
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP WITH TIME ZONE,
    servername TEXT NOT NULL,
    CONSTRAINT servername_uq UNIQUE (servername));


CREATE TYPE thing_enum AS ENUM (
    'dockerimage',                  -- docker hex identifier
    'filename',                     -- deb, s3 source, etc
    'config',                      -- configuration change, etc.
    'git_repo'                     -- git repo
    );

CREATE TABLE thing(
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP WITH TIME ZONE,
    thing_type thing_enum NOT NULL,
    unique_thing_name TEXT NOT NULL,
    CONSTRAINT synthetic_pk_uq UNIQUE (thing_type, unique_thing_name));

CREATE TYPE environment_enum AS ENUM (
   'production',
   'qa',
   'system'
   );

CREATE TABLE build(
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP WITH TIME ZONE,
    version_id INTEGER NOT NULL REFERENCES version(id),
    job_url TEXT NOT NULL,
    job_description TEXT NOT NULL,
    duration INTEGER NOT NULL,
    result VARCHAR(16) NOT NULL,
    misc jsonb NOT NULL);

CREATE TABLE promote(
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP WITH TIME ZONE,
    thing_id INTEGER NOT NULL REFERENCES thing(id),
    environment environment_enum NOT NULL,
    misc jsonb NOT NULL);

CREATE TABLE versioned_thing(
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP WITH TIME ZONE NOT NULL,
    version_id INTEGER NOT NULL REFERENCES version(id),
    thing_id INTEGER NOT NULL REFERENCES thing(id),
    -- no point in dupes. Same thing.
    CONSTRAINT synthetic_versioned_thing_uq UNIQUE (version_id, thing_id));

-- a deploy is a versioned_thing
CREATE TABLE deploy(
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP WITH TIME ZONE,
    versioned_thing_id INTEGER NOT NULL REFERENCES versioned_thing(id),
    -- nullable: not everything is a server.
    -- FK, but not required.
    servername_id INTEGER,
    environment environment_enum NOT NULL,
    misc jsonb NOT NULL);

-- an artifact is a versioned thing and a build.
CREATE TABLE artifact(
    id SERIAL PRIMARY KEY,
    insertion_time TIMESTAMP WITH TIME ZONE,
    versioned_thing_id INTEGER NOT NULL REFERENCES versioned_thing(id),
    build_id INTEGER NOT NULL REFERENCES build(id),
    misc jsonb NOT NULL);

-- point of schema design:

-- indexing pretty much all the foreign keys here. Inserts may be
-- mildly slow at volume; we're optimizing for reading and performing
-- FK queries

CREATE INDEX ON version (id);
CREATE INDEX ON version (version);

CREATE INDEX ON servername (servername);
CREATE INDEX ON servername (id);

CREATE INDEX ON thing (id);
CREATE INDEX ON thing (unique_thing_name);

CREATE INDEX ON build (id);
CREATE INDEX ON build(version_id);
CREATE INDEX ON build (insertion_time);

CREATE INDEX ON promote (id);
CREATE INDEX ON promote(thing_id);
CREATE INDEX ON promote (insertion_time);

CREATE INDEX ON versioned_thing(id);
CREATE INDEX ON versioned_thing(thing_id);
CREATE INDEX ON versioned_thing(version_id);

CREATE INDEX ON deploy (id);
CREATE INDEX ON deploy(versioned_thing_id);
CREATE INDEX ON deploy (insertion_time);

CREATE INDEX ON artifact (id);
CREATE INDEX ON artifact(versioned_thing_id);
CREATE INDEX ON artifact (insertion_time);

------------------------------
-- Views denormalizing the above tables for typical queries.  It is
-- expected that these will be the normal interface into the database
-- for queries.

CREATE OR REPLACE VIEW versioned_things_view AS
SELECT
    versioned_thing.id  AS versioned_id,
    versioned_thing.insertion_time as insertion_time,
    version.id AS version_id,
    version.version_type AS version_type,
    version.version AS version,
    thing.id AS thing_id,
    thing.thing_type AS thing_type,
    thing.unique_thing_name AS unique_thing_name
FROM versioned_thing
INNER JOIN version ON version.id = versioned_thing.version_id
INNER JOIN thing ON thing.id = versioned_thing.thing_id
ORDER by versioned_thing.insertion_time DESC;




-- So. Here we cope with a foreign key that can be null. Note
-- that we have to essentially run two queries: one is for the
-- nulled FK, one is for the non-nulled FK. These get UNION'd
-- together with a CASE/END shim to handle the non-existant
-- column.

CREATE OR REPLACE VIEW deploys_view AS
SELECT *
FROM
(SELECT
    deploy.id AS deploy_id,
    deploy.insertion_time AS insertion_time,
    versioned_things_view.thing_id AS thing_id,
    -- has dependency on the versioned_things view from above.
    versioned_things_view.thing_type AS thing_type,
    versioned_things_view.unique_thing_name AS thing_name,
    versioned_things_view.version_id AS version_id,
    versioned_things_view.version_type AS version_type,
    versioned_things_view.version AS version,
    deploy.environment AS environment,
    CASE
        WHEN deploy.servername_id IS NULL THEN 'null'
        END as servername,
    deploy.misc AS misc
FROM deploy
INNER JOIN versioned_things_view
      ON versioned_things_view.versioned_id = deploy.versioned_thing_id
WHERE deploy.servername_id IS NULL
UNION
SELECT
        deploy.id AS deploy_id,
        deploy.insertion_time AS insertion_time,
        versioned_things_view.thing_id AS thing_id,
        versioned_things_view.thing_type AS thing_type,
        versioned_things_view.unique_thing_name AS thing_name,
        versioned_things_view.version_id AS version_id,
        versioned_things_view.version_type AS version_type,
        versioned_things_view.version AS version,
        deploy.environment AS environment,
        servername.servername AS servername,
        deploy.misc AS misc
FROM deploy
INNER JOIN versioned_things_view
      ON versioned_things_view.versioned_id = deploy.versioned_thing_id
INNER JOIN servername
      ON servername.id = deploy.servername_id) AS source
ORDER BY source.insertion_time DESC;


CREATE OR REPLACE VIEW artifacts_view AS
SELECT
            artifact.id AS artifact_id,
            artifact.insertion_time AS insertion_time,
            versioned_things_view.thing_id AS thing_id,
            versioned_things_view.thing_type AS thing_type,
            versioned_things_view.unique_thing_name AS unique_thing_name,
            versioned_things_view.version_id AS version_id,
            versioned_things_view.version_type AS version_type,
            versioned_things_view.version AS version,
            artifact.build_id AS build_id,
            build.job_url AS job_url,
            build.job_description AS job_description,
            build.duration AS duration,
            build.result AS result,
            artifact.misc AS misc
FROM artifact
INNER JOIN build
      ON build.id = artifact.build_id
INNER JOIN versioned_things_view
      ON versioned_things_view.versioned_id = artifact.versioned_thing_id
ORDER BY artifact.insertion_time DESC;


CREATE OR REPLACE VIEW builds_view AS
SELECT
        build.id AS build_id,
        build.insertion_time AS insertion_time,
        version.id as version_id,
        version.version_type as version_type,
        version.version as version,
        build.job_url as job_url,
        build.job_description as job_description,
        build.duration as duration,
        build.result as result,
        build.misc as misc
FROM build
INNER JOIN version
      ON version.id = build.version_id
ORDER BY build.insertion_time DESC;


CREATE OR REPLACE VIEW promotes_view AS
SELECT
            promote.id as promote_id,
            promote.insertion_time as insertion_time,
            thing.thing_type as thing_type,
            thing.unique_thing_name as thing_name,
            thing.insertion_time as thing_time,
            promote.environment as environment,
            promote.misc as misc
FROM promote
INNER JOIN thing
      ON thing.id = promote.thing_id
ORDER BY promote.insertion_time DESC;
