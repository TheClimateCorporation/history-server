# history server


The history server is essentially a create/read (no update, no delete)
system that is designed to hold the following metadata:

- source code (to the changeset granularity)
- builds
- artifacts
- promotions
- deployments

the end goal is to understand what happened at what point in time, in
relation to what other events.

## users

The intended supplier of information is an automated system that
annotates in a highly structured fashion to the history server what
has happened.  The intended consumer of information is someone
performing analysis on our system. It is expected that they will have
familiarity with SQL or have a SQL query engine.  Several initial
retrieval queries are specified as a demonstration

## user stories

As an employee interested in global system health, I want to be
able to see the following information:

- Number of builds, and promotions in each environment

- Top `n` services on a variety of metrics.

- Build and deployment failures

- Average build and deployment times

- Services deployments (by environment) pie chart

As someone interested in the current state of a particular service, I
want to be able to use the history server to drill into the history of
a given service; when this package got deployed, in what environments,
and the originating build.

As someone in QA, I want to know what builds (running tests) were
executed in relation to an artifact in an environment.

As someone in QA, I want to know what artifacts deployed into the qa
environment are newer than the ones in production.

As someone interested in the health of our code delivery system, I
want to be able to understand the timeline of a given changeset and
all builds that derive from the changeset, then all artifacts from the
changeset, then all deployments from the changeset.

As someone interested in promoting and rolling back services, I want
to be able to use the well structured metadata to determine an
appropriate previous working state.

## architecture


One server, located in production

Generally the method to communicate new information to this server is
to POST to appropriate routes using HTTP parameters.

Retrievals are performed using HTTP GET on appropriate routes, with
JSON being used as the interchange format.

In the backend, there is a relational database storing the relations
between different artifacts and events over time.

## api


### General semantics:

GET queries will return the entire input data, along with the
synthetic primary key (the table id column), and the datetime of
insert, as understood by the database.

GET queries with optional parameters will demand at least one of the
optional parameters filled, and will return HTTP 409 if not fulfilled.

Queries that are not implemented will return HTTP 501.

A POST is an assertion regarding the state of the world. In order for
this service to fulfil usefulness, all assertions must be true. That
is, the system is logically *correct*. It is likely that there will be
services, versions, and histories that are not recorded in this system
due to experimental or legacy reasons; that is, this system is *not
complete*. Regardless, infrastructure systems released for production
software delivery *should* provide assertions regarding their actions
to the history server.

### Assertions

Several key assertions rely on the definition of a **VERSION**. A
**version** is either a `changeset` (a hexadecimal number that should
correspond to a git hash) or a `package` (an arbitrary text field that
should identify the package of the **THING**). Several key assertions
also rely on the definition of a **THING**.

A **THING** can be a `dockerimage` - a docker hex identifier; this
should be used when the thing under discussion is a dockerfile. A
**THING** can also be a `filename`; this should be when the thing under
discussion is, for instance, a Debian package. A **THING** can be a
`config`, which would indicate that a `configuration` is under
discussion; somewhat more abstract and multi-system than a file, but
still affecting the world. A `git_repo` is a **THING** - the record
should be of the canonical git repository the **THING** is found at.

A **BUILD** assertion occurs after Jenkins (or other CI server) has
completed its execution. The actual state of the build is recorded,
along with other build-specific information. **ARTIFACT**s generated
by the **BUILD** should be asserted in the **ARTIFACT** table and
linked to the **BUILD**

An **ARTIFACT** asserts that there now exists a filename, with the
specified relations. If, perchance, an ARTIFACT is not created, or not
uploaded, the ARTIFACT does not exist in this database.

A **PROMOTE** asserts that a THING was promoted to environment. That
is to say, a THING is now ready to be DEPLOY'd into the
environment. This will generally entail metadata being updated
successfully prior to stating the PROMOTE assertion.

Similarly, the **DEPLOY** relates to the **ARTIFACT**, and environment, and a
server. A **DEPLOY** occurs when all artifacts have landed on specified
servers. A partial deployment attempt _does not_ result in a **DEPLOY**
assertion.

### Documentation

This document is the canonical document for the intention and specific
usage of the history serer.

Swagger docs for the API can be found at /api/v1/swagger

### Search UI

History Server Search can be found at /search and
provides a UI for querying against things and their
attributes.

The following is an example query:
build_id == 3 && version_type == changeset

The expected output will be JSON describing
things with attributes 'build_id' and 'version_type',
with respective values of '3' and 'changeset'.

* There are also API endpoints for search,
described further down in this document.


### Atomic queries (v1)

All queries are prefixed with the following route:

/api/v1

POST
/build
- version_type
- version
- job_url
- job_description
- duration
- success
- misc
RETURNS - database id ID

GET
/build
One of:
- (optional) job_url

- (optional) build_id

- (optional) version_type
- (optional) version

RETURNS - JSON list of build assertions

GET
/build/:id
RETURNS JSON list of the build at id or 404 if not found

GET
/build/all
RETURNS json list of builds

GET
/build/attributes
RETURNS list of attributes for builds

GET
/build/search
- attributes mapped to respective target values
RETURNS JSON of builds that fit the search params

POST
/artifact
- filename
- version_type
- version
- build_id
- misc
RETURNS - artifact_id

GET
/artifact/:id
RETURNS JSON list of the artifact at id or 404 if not found

GET
/artifact

One of:

- (optional) filename

- (optional) artifact_id

- (optional) version_type
- (optional) version

GET
/artifact/all

GET
/artifact/attributes
RETURNS list of attributes for artifacts

GET
/artifact/search
- attributes mapped to respective target values
RETURNS JSON of artifacts that fit the search params

POST
/promote
- thing_type
- thing_name
- environment
- misc
RETURNS promotion_id

GET
/promote/:id
RETURNS JSON list of the promote at id or 404 if not found


GET
/promote
one of:

- (optional) thing_type
- (optional) thing_name

- (optional) filename

- (optional) environment

RETURNS list of promotion assertions

/promote/all
RETURNS list of promotion assertions

GET
/promote/attributes
RETURNS list of attributes for promotes

GET
/promote/search
- attributes mapped to respective target values
RETURNS JSON of promotes that fit the search params

POST
/deploy
- thing_type
- thing_name
- version_type
- version
- (optional) servername
- environment
- misc
RETURNS deploy_id

GET
/deploy

One of:

- (optional) deploy_id

- (optional) environment

- (optional) thing_name

- (optional) version_type
- (optional) version
RETURNS either -
   the deploy corresponding to deploy_id OR
   the list of deploys corresponding with the environment OR
   the list of deploys corresponding with the thing_name OR
   the list of deploys corresponding with the changeset OR

GET
/deploy/:id
RETURNS JSON list of the deploy at id or 404 if not found

GET
/deploy/all
RETURNS - list of all deploys

GET
/deploy/attributes
RETURNS list of attributes for deploys

GET
/deploys/search
- attributes mapped to respective target values
RETURNS JSON of deploys that fit the search params

First-order queries
GET
/environment/current
- environment
RETURNS list of the most recent artifact_ids in environment-name

GET
/artifact/history
- artifact_id
RETURNS map of the environments this artifact_id was promoted into,
along with any deploys


GET
/thing_attributes
RETURNS JSON object of thing_types mapped to lists of
their respective attributes


## API versioning comments

Each /api/v<version> will be stable in semantics on general
availability. It will have no fields removed; it may have fields
added.

If a route needs to remove fields, it will be revised to
/api/v<version + 1> and an appropriate deprecation/obseletion notice
sent.

The intent is for consumers to be able to rely on this API without
having to regularly rewrite their code.


## internal schema design

Because of the event-driven nature of the data, and the choice to have
*immutable* data, consequently the schema is what I call a "sideways"
table.  This will serve as a journaling system, recording the events
as they are asserted. A conventional table might look like this (id,
update-time, data-element), and the convention is to use:

```
UPDATE tablename
WHERE id = id.
SET data-element = new-data
```


However, a "sideways" table will look like this (id, appended-time, key, op,
data-element). The convention to update data is to:

```
INSERT INTO tablename (appended-time, key, op, data-element)
VALUES (now(), "data-key", 'MODIFY', data-new-data)
```

This lets us query by

```
SELECT *
WHERE appended_time < TIME AND key = "sweet key"
ORDER BY appended-time DESC
LIMIT 1
```

in order to claim the latest value.
