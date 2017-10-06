"""
Backend for the history-server system; interacts with the SQL
database
"""

import logging
import os

import psycopg2
import psycopg2.extras
import pytoml


logging.basicConfig(format='%(asctime)-15s %(levelname)s: %(message)s')
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

class ThingType(object):
    """
    Enum of types of things; reflects enum in the SQL.
    """
    FILENAME = 'filename'
    CONFIG = 'config'
    DOCKERIMAGE = 'dockerimage'
    GIT_REPO = 'git_repo'

class VersionType(object):
    """
    Enum of types of versions; reflects enum in the SQL
    """
    PACKAGE = 'package'
    CHANGESET = 'changeset'

class SQLClauseFactory(object):

    @staticmethod
    def generate_where(query_args):
        wheres = []
        where_params = []
        if len(query_args) > 0:
            for k, val in query_args.iteritems():
                for v in val:
                    condition = '='
                    if v.get('condition'):
                        condition = v.get('condition')
                    if v.get('attr_alias'):
                        k = v.get('attr_alias')
                    wheres.append("{0} {1} %s".format(k, v.get('condition')))
                    where_params.append(v.get('value'))
        where = 'WHERE ' + 'AND '.join(wheres)
        return where, tuple(where_params)

class PgServer(object):
    """
    The "model" class in an MVC system. Provides an interface between
    semantic identifiers and the database schema.
    """
    # Implementation notes.
    #
    # SQL in Python. Tons of it. Some more interesting than
    # others. Somewhere, the inventor of ORMs is crying over a beer.
    #
    # Organization: each table gets a section in the class, delimited
    # by a comment.

    def __init__(self, filename='env.properties.toml'):
        """
        Pick out the required variables from the env.properties toml file.
        """
        data = pytoml.loads(open(filename).read())

        PGHOST = 'PGHOST'
        PGDATABASE = 'PGDATABASE'
        PGUSER = 'PGUSER'
        PGPASSWORD = 'PGPASSWORD'

        self._host = data['default'][PGHOST]
        self._dbname = data['default'][PGDATABASE]
        self._pguser = data['default'][PGUSER]
        self._pgpassword = data['default'][PGPASSWORD]

        # overlay the above settings with the local environment
        self._env = os.getenv('WEB_ENV', 'default')
        self._host = data[self._env].get(PGHOST, self._host)
        self._dbname = data[self._env].get(PGDATABASE, self._dbname)
        self._pguser = data[self._env].get(PGUSER, self._pguser)
        self._pgpassword = data[self._env].get(PGPASSWORD, self._pgpassword)

        # now overlay with any environment variables that are set.
        self._host = os.getenv(PGHOST, self._host)
        self._dbname = os.getenv(PGDATABASE, self._dbname)
        self._pguser = os.getenv(PGUSER, self._pguser)
        self._pgpassword = os.getenv(PGPASSWORD, self._pgpassword)

        self._connection_string = "host={0} dbname={1} user={2} password={3}".format(
            self._host, self._dbname, self._pguser, self._pgpassword)

        # SELECT strings - note the trailing space!!

        self._artifact_select = "SELECT {0} FROM artifacts_view ".format(
            ", ".join(self.wanted_artifact_columns))

        self._deploy_select =  "SELECT {0} FROM deploys_view ".format(
            ", ".join(self.wanted_deploy_columns))

        self._build_select = "SELECT {0} FROM builds_view ".format(
            ", ".join(self.wanted_build_columns))

        self._promote_select = "SELECT {0} FROM promotes_view ".format(
            ", ".join(self.wanted_promote_columns))

        self._versioned_select = "SELECT {0} from versioned_things_view".format(
            ", ".join(self.wanted_versioned_columns))

        # SQL connection
        self.conn = None
        # SQL cursor
        self.cur = None

    # Fodder for the context manager.
    def start(self):
        """
        Called by the context manager.

        Implicitly begins a database transaction.

        """

        # from Psycopg docs...
        # In Psycopg transactions are handled by the connection
        # class. By default, the first time a command is sent to the
        # database (using one of the cursors created by the
        # connection), a new transaction is created. The following
        # database commands will be executed in the context of the
        # same transaction - not only the commands issued by the first
        # cursor, but the ones issued by all the cursors created by
        # the same connection. Should any command fail, the
        # transaction will be aborted and no further command will be
        # executed until a call to the rollback() method.

        # The connection is responsible for terminating its
        # transaction, calling either the commit() or rollback()
        # method. Committed changes are immediately made persistent
        # into the database. Closing the connection using the close()
        # method or destroying the connection object (using del or
        # letting it fall out of scope) will result in an implicit
        # rollback.

        LOGGER.debug("host={0} dbname={1} user={2}".format(
            self._host, self._dbname, self._pguser))
        self.conn = psycopg2.connect(self._connection_string)
        self.cur = self.conn.cursor()
        LOGGER.debug("connecting to database")

    def end(self):
        """
        Called by the context manager.

        Implicitly commits, then ends a database transaction.
        """

        self.conn.commit()
        self.cur.close()
        LOGGER.debug("disconnected from  database")


    def __enter__(self):
        self.start()
        return self

    def __exit__(self, _1, _2, _3):
        self.end()

    def _process_getter(self, ordered_column_list):
        """
        Converts the cursor's results into a list of dicts indexed by the
        `ordered_column_list`. Further, if a key 'insertion_time'
        exists in the dict, we assume it's a postgres datetime object
        and convert it to ISO format.
        """
        results = []
        for result in self.cur.fetchall():
            temp = dict(zip(tuple(ordered_column_list), result))
            # courtesy DRY.
            if temp.has_key('insertion_time'):
                temp['insertion_time'] = temp['insertion_time'].isoformat()

            results.append(temp)
        return results

    ##############################
    # Version
    def find_version(self, version_id):
        self.cur.execute(
            """
            SELECT
            id
            insertion_time,
            version_type,
            version""", (version_id,))
        res = self.cur.fetchone()[0]
        return res

    def append_version(self, version_type, version):
        """
        Insert version into the table.  Postgres will error if
        version_type is wrong or if there is a duplicate.

        Returns version id
        """
        self.cur.execute(
            """INSERT INTO version (insertion_time, version_type, version)
            VALUES ('now()', %s, %s)
            RETURNING id""", (version_type, version))
        return self.cur.fetchone()[0]

    def ensure_version(self, version_type, version):
        self.cur.execute(
            """SELECT id FROM version
            WHERE version_type = %s AND version = %s""",
            (version_type, version))
        # contract via postgres schema: 0 or 1.
        results = self.cur.fetchone()
        if results:
            version_id = results[0]
        else:
            version_id = self.append_version(version_type, version)

        return version_id

    ##############################
    # Versioned thing

    wanted_versioned_columns =  (
        'versioned_id',
        'version_id',
        'version_type',
        'version',
        'thing_id',
        'thing_type',
        'unique_thing_name')


    def find_versioned_thing(self, versioned_thing_id):
        """
        Select the columns matching versioned_thing_id and return them or
        raise if unable to find.

        Note, versioned_thing_id is a primary key.
        """
        self.cur.execute(self._versioned_select +
                         "WHERE versioned_id = %s",
                         (versioned_thing_id,))
        res = self.cur.fetchone()[0]
        return res

    def append_versioned_thing(self, version_id, thing_id):
        """
        insert version_id, thing_id into the versioned_thing table,
        returning the primary key.
        """
        self.cur.execute(
            """INSERT INTO versioned_thing (insertion_time, version_id, thing_id)
            VALUES ('now()', %s, %s)
            RETURNING id""", (version_id, thing_id))
        return self.cur.fetchone()[0]

    def get_versioned_things_if_exists(self, version_type, version):
        """
        Gets the versioned_things if they exists.

        It is possible that there might be multiple of them.
        """
        self.cur.execute(self._versioned_select +
                         """
                         WHERE version_type = %s AND
                         version = %s
                         """,
                         (version_type, version))

        return self._process_getter(self.wanted_versioned_columns)




    def ensure_versioned_thing(self, version_type, version, thing_type, thing_name):
        """
        Ensures that (version_type, version, thing_type, thing_name) are in the
        database and returns a primary key representing their unique
        tuple.
        """
        version_id = self.ensure_version(version_type, version)
        thing_id = self.ensure_thing(thing_type, thing_name)

        self.cur.execute("""
        SELECT id
        FROM versioned_thing
        WHERE versioned_thing.version_id = %s
           AND versioned_thing.thing_id = %s
        """, (version_id, thing_id))
        results = self.cur.fetchone()
        if results:
            # n.b, this SQL is part of the schema - we only get 0 or 1
            # thing back:
            #
            # constraint synthetic_versioned_thing_uq unique (changeset_id, thing_id)
            #
            versioned_thing_id = results[0]
        else:
            versioned_thing_id = self.append_versioned_thing(version_id,
                                                             thing_id)

        return versioned_thing_id

    ##############################
    # Servernames

    def ensure_servername(self, servername):
        """
        Inserts if not present, and finds the id (primary key) of the
        `servername`.

        Returns id.
        """
        self.cur.execute("SELECT id FROM servername WHERE servername.servername = %s", (servername,))
        results = self.cur.fetchone()
        if results:
            servername_id = results[0]
        else:
            self.cur.execute(
                """
                INSERT INTO servername (insertion_time, servername)
                VALUES ('now()', %s)
                RETURNING id""", (servername,))
            servername_id = self.cur.fetchone()[0]
        return servername_id

    ##############################
    # Things

    def append_thing(self, thing_type, thing_name):

        """
        thingtype must be a member of the type ThingType.
        """
        self.cur.execute(
            """
            INSERT INTO thing (insertion_time, thing_type, unique_thing_name)
            VALUES ('now()', %s, %s)
            RETURNING id""", (thing_type, thing_name))
        return self.cur.fetchone()[0]


    def ensure_thing(self, thing_type, thing_name):
        """
        Returns thing id; if name linked with thingtype doesn't exist,
        inserts it.
        """
        self.cur.execute("""
SELECT id
FROM thing
WHERE thing.unique_thing_name = %s AND
thing.thing_type = %s""", (thing_name, thing_type))
        results = self.cur.fetchone()
        if results:
            row_id = results[0]
        else:
            row_id = self.append_thing(thing_type, thing_name)

        return row_id

    ##############################
    # Promotes

    wanted_promote_columns = (
        'promote_id',
        'insertion_time',
        'thing_type',
        'thing_name',
        'thing_time',
        'environment',
        'misc')

    def _process_promote_getter(self):
        """
        Assumes a SELECT has just taken place against the promotes;
        processes the results and returns them.
        """
        results = self._process_getter(
            ('promote_id',
             'promotion_time',
             'thing_type',
             'thing_name',
             'thing_time',
             'environment',
             'misc'))
        for result in results:
            result['promotion_time'] = result['promotion_time'].isoformat()
            result['thing_time'] = result['thing_time'].isoformat()

        return results

    def append_promote(self, thing_type, thing_name, environment, misc):
        """
        Appends the promote indicated by `thing_type`, `thing`,
        `environment`, and `misc`, looking up the foreign key
        relationships along the way.

        Returns the synthetic primary key.
        """
        self.cur.execute(
            """
            INSERT INTO promote (insertion_time, thing_id, environment, misc)
            VALUES ('now()', %s, %s, %s)
            RETURNING id""",
            (self.ensure_thing(thing_type, thing_name),
             environment,
             psycopg2.extras.Json(misc)))
        return self.cur.fetchone()[0]

    def get_promote_by_attrs(self, promote_attrs):
        where, data = SQLClauseFactory.generate_where(promote_attrs)
        self.cur.execute(self._promote_select + where, data)
        return self._process_promote_getter()

    def get_promote_by_thing(self, thing_type, thing):
        """
        Gets all promotes related to (thing_type, thing) from the promote table.

        Returns a list of dicts.
        """
        self.cur.execute(
            """
SELECT
            promote.id as promote_id,
            promote.insertion_time as promotion_time,
            thing.thing_type as thing_type,
            thing.unique_thing_name as thing_name,
            thing.insertion_time as thing_time,
            promote.environment,
            promote.misc
FROM promote
INNER JOIN thing ON thing.id = promote.thing_id
WHERE promote.thing_id = %s
            """,
            (self.ensure_thing(thing_type, thing),))
        return self._process_promote_getter()

    def get_promote_by_promote_id(self, promote_id):
        """
        Gets the promotion denoted by promote_id or raises.

        `promote_id` is the primary key for the promote table.
        """
        self.cur.execute(
            """
SELECT
            promote.id as promote_id,
            promote.insertion_time as promotion_time,
            thing.thing_type as thing_type,
            thing.unique_thing_name as thing,
            thing.insertion_time as thing_time,
            promote.environment,
            promote.misc
FROM promote
INNER JOIN thing ON thing.id = promote.thing_id
WHERE promote.id = %s
            """,
            (promote_id,))
        return self._process_promote_getter()

    def get_promote_by_environment(self, env):
        """
        Get all promotes in the environment `env` and returns them as a
        list of dicts.
        """
        self.cur.execute(
            """
SELECT
            promote.id as promote_id,
            promote.insertion_time as promotion_time,
            thing.thing_type as thing_type,
            thing.unique_thing_name as thing,
            thing.insertion_time as thing_time,
            promote.environment,
            promote.misc
FROM promote
INNER JOIN thing ON thing.id = promote.thing_id
WHERE promote.environment = %s
            """,
            (env,))
        return self._process_promote_getter()

    def get_all_promotes(self):
        """
        Return list of all promotes the database knows about.
        """
        self.cur.execute(
            """
SELECT
            promote.id as promote_id,
            promote.insertion_time as promotion_time,
            thing.thing_type as thing_type,
            thing.unique_thing_name as thing,
            thing.insertion_time as thing_time,
            promote.environment,
            promote.misc
FROM promote
INNER JOIN thing ON thing.id = promote.thing_id
            """)
        return self._process_promote_getter()


    ##############################
    # Builds

    wanted_build_columns = ('build_id',
                            'insertion_time',
                            'version_type',
                            'version',
                            'version_id',
                            'job_url',
                            'job_description',
                            'duration',
                            'result',
                            'misc')

    def _process_build_getter(self):
        """
        Processes the database results and returns them as a list of
        Python dicts.
        """
        return self._process_getter(self.wanted_build_columns)

    def append_build(self,
                     version_type,
                     version,
                     job_url,
                     job_description,
                     duration,
                     result,
                     misc):
        """
        Appends the build described in the parameters, ensuring that
        the version is recorded in the database.
        """
        version_id = self.ensure_version(version_type, version)

        self.cur.execute(
            """
            INSERT INTO build (insertion_time, version_id, job_url, job_description, duration, result, misc)
            VALUES ('now()', %s, %s, %s, %s, %s, %s)
            RETURNING id""",
            (version_id,
             job_url,
             job_description,
             duration,
             result,
             psycopg2.extras.Json(misc)))
        return self.cur.fetchone()[0]

    def get_build_by_attrs(self, build_attrs):
        where, data = SQLClauseFactory.generate_where(build_attrs)
        self.cur.execute(self._build_select + where, data)
        return self._process_build_getter()

    def get_build_by_url(self, build_url):
        """
        Returns all builds matching `build_url`
        """
        self.cur.execute(
            self._build_select +
            "WHERE job_url = %s", (build_url,))
        return self._process_build_getter()

    def get_build_by_build_id(self, build_id):
        """
        Returns the build denoted by ``build_id` or fails; build_id is
        the primary key of the build table.
        """
        self.cur.execute(
            self._build_select +
            "WHERE build_id = %s", (build_id,))
        return self._process_build_getter()

    def get_all_builds(self):
        """
        Return a list of all builds that are known to the database.
        """
        self.cur.execute(self._build_select)
        return self._process_build_getter()

    def get_build_by_version(self, version_type, version ):
        """
        Returns list of all builds known to be associated with the
        version.
        """
        self.cur.execute(self._build_select +
                         "WHERE version_id = %s",
                         (self.ensure_version(version_type, version),))
        return self._process_build_getter()

    ##############################
    # Artifacts

    # columns for the artifact table that we return.
    #
    # These are fed into self._artifact_select to generate a SELECT
    # query programmatically.
    wanted_artifact_columns = ('artifact_id',
                               'insertion_time',
                               'thing_id',
                               'thing_type',
                               'unique_thing_name',
                               'version_type',
                               'version_id',
                               'version',
                               'build_id',
                               'job_url',
                               'job_description',
                               'duration',
                               'result',
                               'misc')

    def _process_artifact_getter(self):
        """
        Returns list of artifact results as dicts.
        """
        return self._process_getter(
            self.wanted_artifact_columns)

    def append_artifact(self, version_type, version, filename, build_id, misc):
        """
        Appends a new artifact to the records.

        - `version_type` := 'artifact' or 'changeset'
        - 'version' := 40 char hash or a string with a version
        - `filename` is a string
        - `build_id` must be an integer
        - `misc` is a Python object suitable to convert to JSON.

        Returns the artifact id, an integer serving as the primary key
        for the artifact.
        """
        versioned_thing_id = self.ensure_versioned_thing(version_type,
                                                         version,
                                                         ThingType.FILENAME,
                                                         filename)

        self.cur.execute(
            """
            INSERT INTO artifact (insertion_time, versioned_thing_id, build_id, misc)
            VALUES ('now()', %s, %s, %s)
            RETURNING id""",
            (versioned_thing_id,
             build_id,
             psycopg2.extras.Json(misc)))
        return self.cur.fetchone()[0]

    def get_artifact_by_attrs(self, artifact_attrs):
        where, data = SQLClauseFactory.generate_where(artifact_attrs)
        self.cur.execute(self._artifact_select + where, data)
        return self._process_artifact_getter()

    def get_artifact_by_filename(self, filename):
        """
        Gets an artifact by the string `filename`, assuming that
        `filename` exists.

        Does not return artifacts that aren't filenames.
        """
        query = self._artifact_select + "WHERE thing_id = %s"
        thing_id = (self.ensure_thing(ThingType.FILENAME, filename),)

        self.cur.execute(query, thing_id)

        return self._process_artifact_getter()

    def get_artifact_by_build_id(self, build_id):
        """
        Return all artifacts known to be associated with `build_id`.

        Note that build_id is the primary key for builds.
        """

        query = self._artifact_select + "WHERE build_id = %s"

        self.cur.execute(query, (build_id,))

        return self._process_artifact_getter()

    def get_artifact_by_version(self, version_type, version):
        """
        Gets all artifacts that relate to `version` and
        `version_type`. `version` must be the full 40-character hash,
        not a short form.
        """
        query = self._artifact_select + "WHERE version_id = %s"

        v_id = self.ensure_version(version_type, version)
        self.cur.execute(query, (v_id,))

        return self._process_artifact_getter()


    def get_artifact_by_artifact_id(self, artifact_id):
        """
        Gets the artifact identified by `artifact_id`.
        """
        query = self._artifact_select + "WHERE artifact_id = %s"

        self.cur.execute(query, (artifact_id,))

        return self._process_artifact_getter()

    def get_all_artifacts(self):
        """
        Gets all known artifacts. It is probable that this is not a call
        that should be made.
        """
        self.cur.execute(self._artifact_select)

        return self._process_artifact_getter()

    ##############################
    # Deploys

    wanted_deploy_columns = ("deploy_id",
                             "insertion_time",
                             # thing_id is also a column, but elided.
                             "thing_type",
                             "thing_name",
                             "version_type",
                             "version_id",
                             "version",
                             "environment",
                             "servername",
                             "misc")

    def _process_deploy_getter(self):
        """
        Return list of deploys as dicts.

        If servername is not recorded in the database, it is not
        present in the dict.
        """
        result = self._process_getter(
            self.wanted_deploy_columns)
        for r in result:
            if r['servername'] == 'null':
                del r['servername']
        return result


    def append_deploy(self,
                      thing_type,
                      thing_name,
                      version_type,
                      version,
                      environment,
                      servername,
                      misc):
        """
        thing_type: type of thing being deployed.
        thing_name: name of thing being deployed.
        version_type:
        version:
        environment: environment being deployed to.
        servername: if applicable...
        misc: arbitrary tags.

        returns deploy_id, the FK for deploys.
        """
        versioned_thing_id = self.ensure_versioned_thing(version_type,
                                                         version,
                                                         thing_type,
                                                         thing_name)

        # note, two separate and *similar* queries, not identical.
        if servername:
            servername_id = self.ensure_servername(servername)
            self.cur.execute(
                """
                INSERT INTO deploy (insertion_time,
                                    versioned_thing_id,
                                    servername_id,
                                    environment,
                                    misc)
                VALUES ('now()', %s, %s, %s, %s)
                RETURNING id""",
                (versioned_thing_id,
                 servername_id,
                 environment,
                 psycopg2.extras.Json(misc)))
        else:
            self.cur.execute(
                """
                INSERT INTO deploy (insertion_time, versioned_thing_id, environment, misc)
                VALUES ('now()', %s, %s, %s)
                RETURNING id""",
                (versioned_thing_id,
                 environment,
                 psycopg2.extras.Json(misc)))

        return self.cur.fetchone()[0]

    def get_deploy_by_attrs(self, deploy_attrs):
        where, data = SQLClauseFactory.generate_where(deploy_attrs)
        self.cur.execute(self._deploy_select + where, data)
        return self._process_deploy_getter()

    def get_deploys_by_deploy_id(self, deploy_id):
        """
        Get the deploy specified by deploy_id and returns it.
        """
        self.cur.execute(
            self._deploy_select + "WHERE deploy_id = %s",
            (deploy_id,))
        return self._process_deploy_getter()

    def get_deploys_by_environment(self, environment):
        """
        Get the deploys visible in environment and returns the list.
        """
        LOGGER.debug("getting deploys in env: %s", environment)
        self.cur.execute(
            self._deploy_select + "WHERE environment = %s",
            (environment,))
        return self._process_deploy_getter()

    def get_deploys_by_thing_name(self, thing_name, thingtype=None):
        """
        Get the deploys denoted by thing_name.

        If thingtype is set, then an additional limiting is done.
        """
        LOGGER.debug("getting deploys by name of: %s", thing_name)
        if not thingtype:
            self.cur.execute(
                self._deploy_select + "WHERE thing_name = %s",
                (thing_name,))
        else:
            self.cur.execute(
                self._deploy_select + "WHERE thing_name = %s AND thing_type = %s",
                (thing_name, thingtype))
        return self._process_deploy_getter()

    def get_deploys_by_version(self, version_type, version):
        """
        Gets all deploys associated with `version_type`, `version`.
        """
        versioned_things = self.get_versioned_things_if_exists(version_type, version)

        results = []

        for versioned_thing in versioned_things:
            version_id = versioned_thing['version_id']
            query = self._deploy_select + "WHERE version_id = %s"

            LOGGER.debug("q: %s, %s", query, version_id)
            self.cur.execute(
                query,
                (version_id, ))
            results.extend(self._process_deploy_getter())

        return results

    def get_all_deploys(self):
        """
        Return a list of all deploys known to the database.
        """
        self.cur.execute(self._deploy_select)

        return self._process_deploy_getter()

    ##############################
    # Misc first order queries
    # TODO - Implement them.
    def get_current_environment(self, environment):
        """
        Returns the list of artifacts in the current environment.
        """
        return None

    def get_artifact_history(self):
        """
        Returns all promotions associated with the artifact.
        """
        return None
