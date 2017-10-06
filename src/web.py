"""
Flask app connecting the web to the backend.
"""

# stdlib imports
import datetime
import dateutil.parser
import json
import os
import time
from collections import defaultdict

# third part imports
import flask
import prometheus_client
from flask_restplus import abort, Api, Resource, fields, apidoc
from flask_bootstrap import Bootstrap
from psycopg2 import IntegrityError

# internal imports
from backend import PgServer


##############################
# set up the main app
app = flask.Flask(__name__)
Bootstrap(app)
blueprint = flask.Blueprint('api', __name__, url_prefix='/api/v1')
api = Api(blueprint, validate=True)


# Swagger docs at /api/v1/swagger
@blueprint.route('/swagger/', endpoint='/swagger')
def swagger_ui():
    return apidoc.ui_for(api)

app.register_blueprint(blueprint)
app.register_blueprint(apidoc.apidoc)

# Clear out the default Flask logging.
app.logger.handlers = []

##############################
# set up the metrics


h = prometheus_client.Histogram('http_request_latency_seconds',
                                'HTTP Request latency',
                                ['method', 'route', 'code'])
e = prometheus_client.Counter('http_request_errors_total',
                              'HTTP Request errors',
                              ['method', 'route', 'code'])


@app.before_first_request
def stand_up_prometheus(*args, **kwargs):
    prometheus_client.start_http_server(5001)

##############################
# globals

ENVIRONMENT_PROPERTIES = 'env.properties.toml'

#############################
# utils


def parse_times(obj):
    for attr in obj:
        if attr.endswith('_time'):
            obj[attr] = dateutil.parser.parse(obj[attr])
    return obj


##############################
# flask_restplus models


class TYPES(object):

    """
    dumb lookup table to convert restplus
    model types to python types for reqparse
    """
    string = str
    integer = int


class ARGS(object):

    """
    enum to DRY up the repetitive typos in strings.
    """
    ARTIFACT_ID = 'artifact_id'
    BUILD_ID = 'build_id'
    DEPLOY_ID = 'deploy_id'
    DURATION = 'duration'
    ENVIRONMENT = 'environment'
    FILENAME = 'filename'
    INSERTION_TIME = 'insertion_time'
    JOB_DESCRIPTION = 'job_description'
    JOB_URL = 'job_url'
    MISC = 'misc'
    PROMOTE_ID = 'promote_id'
    PROMOTE_TIME = 'promotion_time'
    SERVER_NAME = 'servername'
    RESULT = 'result'
    THING_ID = 'thing_id'
    THING_NAME = 'thing_name'
    THING_TIME = 'thing_time'
    THING_TYPE = 'thing_type'
    VERSION = 'version'
    VERSION_ID = 'version_id'
    VERSION_TYPE = 'version_type'
    UNIQUE_THING_NAME = 'unique_thing_name'


class ENUMS(object):
    THING_TYPES = ['ARTIFACTS', 'BUILDS', 'DEPLOYS', 'PROMOTES']
    PATH_THING_TYPES = [x.lower().rstrip('s') for x in THING_TYPES]
    version_type = ('package', 'changeset')
    thing_type = ('dockerimage', 'filename', 'config', 'git_repo')
    environment = ('production',
                   'qa',
                   'system')

class NonuniformNested(fields.Raw):

    __schema_example__ = {'comment': 'test of artifact insertion'}

    def format(self, value):
        return value

build = api.model('Build', {
    ARGS.BUILD_ID: fields.Integer(),
    ARGS.VERSION: fields.String(),
    ARGS.VERSION_ID: fields.Integer(),
    ARGS.VERSION_TYPE: fields.String(),
    ARGS.INSERTION_TIME: fields.DateTime(),
    ARGS.JOB_URL: fields.String(),
    ARGS.JOB_DESCRIPTION: fields.String(),
    ARGS.DURATION: fields.Integer(),
    ARGS.RESULT: fields.String(),
    ARGS.MISC: NonuniformNested(),
})

build_post_parser = api.parser()
build_post_parser.add_argument(
    ARGS.DURATION, type=int, location='form', required=True)
build_post_parser.add_argument(
    ARGS.JOB_DESCRIPTION, type=str, location='form', required=True)
build_post_parser.add_argument(
    ARGS.JOB_URL, type=str, location='form', required=True)
build_post_parser.add_argument(
    ARGS.MISC, type=str, location='form', default='{}')
build_post_parser.add_argument(
    ARGS.RESULT, type=str, location='form', default='')
build_post_parser.add_argument(
    ARGS.VERSION, type=str, location='form', required=True)
build_post_parser.add_argument(
    ARGS.VERSION_TYPE, type=str, location='form', required=True,
    choices=ENUMS.version_type)

build_get_parser = api.parser()
build_get_parser.add_argument(ARGS.FILENAME, type=str)
build_get_parser.add_argument(ARGS.JOB_URL, type=str)
build_get_parser.add_argument(ARGS.BUILD_ID, type=int)
build_get_parser.add_argument(ARGS.VERSION_TYPE, type=str,
                              choices=ENUMS.version_type)
build_get_parser.add_argument(ARGS.VERSION, type=str)

artifact = api.model('Artifact', {
    ARGS.ARTIFACT_ID: fields.Integer(),
    ARGS.VERSION: fields.String(),
    ARGS.VERSION_ID: fields.Integer(),
    ARGS.VERSION_TYPE: fields.String(),
    ARGS.BUILD_ID: fields.Integer(),
    ARGS.JOB_URL: fields.String(),
    ARGS.JOB_DESCRIPTION: fields.String(),
    ARGS.DURATION: fields.Integer(),
    ARGS.RESULT: fields.String(),
    ARGS.INSERTION_TIME: fields.DateTime(),
    ARGS.UNIQUE_THING_NAME: fields.String(),
    ARGS.THING_TYPE: fields.String(),
    ARGS.THING_ID: fields.Integer(),
    ARGS.MISC: NonuniformNested(),
})
artifact_post_parser = api.parser()
artifact_post_parser.add_argument(
    ARGS.VERSION_TYPE, type=str, location='form', required=True,
    choices=ENUMS.version_type)
artifact_post_parser.add_argument(
    ARGS.VERSION, type=str, location='form', required=True)
artifact_post_parser.add_argument(
    ARGS.FILENAME, type=str, location='form', required=True)
artifact_post_parser.add_argument(
    ARGS.BUILD_ID, type=int, location='form', required=True)
artifact_post_parser.add_argument(
    ARGS.MISC, type=str, location='form', default='{}')
artifact_get_parser = api.parser()
artifact_get_parser.add_argument(ARGS.ARTIFACT_ID, type=int)
artifact_get_parser.add_argument(ARGS.BUILD_ID, type=int)
artifact_get_parser.add_argument(ARGS.VERSION, type=str)
artifact_get_parser.add_argument(ARGS.VERSION_TYPE, type=str,
                                 choices=ENUMS.version_type)
artifact_get_parser.add_argument(ARGS.FILENAME, type=str)

promote = api.model('Promote', {
    ARGS.PROMOTE_ID: fields.Integer(),
    ARGS.PROMOTE_TIME: fields.DateTime(),
    ARGS.THING_TYPE: fields.String(),
    ARGS.THING_NAME: fields.String(),
    ARGS.THING_TIME: fields.DateTime(),
    ARGS.ENVIRONMENT: fields.String(),
    ARGS.MISC: NonuniformNested(),
})

promote_post_parser = api.parser()
promote_post_parser.add_argument(
    ARGS.THING_TYPE, type=str, location='form', required=True,
    choices=ENUMS.thing_type)
promote_post_parser.add_argument(
    ARGS.THING_NAME, type=str, location='form', required=True)
promote_post_parser.add_argument(
    ARGS.ENVIRONMENT, type=str, location='form', required=True,
    choices=ENUMS.environment)
promote_post_parser.add_argument(
    ARGS.MISC, type=str, location='form', default='{}')
promote_get_parser = api.parser()
promote_get_parser.add_argument(ARGS.THING_NAME, type=str)
promote_get_parser.add_argument(
    ARGS.THING_TYPE, type=str, choices=ENUMS.thing_type)
promote_get_parser.add_argument(
    ARGS.ENVIRONMENT, type=str, choices=ENUMS.environment)
promote_get_parser.add_argument(ARGS.PROMOTE_ID, type=int)

deploy = api.model('Deploy', {
    ARGS.DEPLOY_ID: fields.Integer(),
    ARGS.ENVIRONMENT: fields.String(),
    ARGS.THING_NAME: fields.String(),
    ARGS.THING_TYPE: fields.String(),
    ARGS.INSERTION_TIME: fields.DateTime(),
    ARGS.VERSION_TYPE: fields.String(),
    ARGS.VERSION_ID: fields.Integer(),
    ARGS.VERSION: fields.String(),
    ARGS.SERVER_NAME: fields.String(),
    ARGS.MISC: NonuniformNested(),
})

deploy_post_parser = api.parser()
deploy_post_parser.add_argument(
    ARGS.THING_TYPE, type=str, location='form', required=True,
    choices=ENUMS.thing_type)
deploy_post_parser.add_argument(
    ARGS.THING_NAME, type=str, location='form', required=True)
deploy_post_parser.add_argument(
    ARGS.VERSION_TYPE, type=str, location='form', required=True,
    choices=ENUMS.version_type)
deploy_post_parser.add_argument(
    ARGS.VERSION, type=str, location='form', required=True)
deploy_post_parser.add_argument(
    ARGS.ENVIRONMENT, type=str, location='form', required=True,
    choices=ENUMS.environment)
deploy_post_parser.add_argument(
    ARGS.SERVER_NAME, type=str, location='form', default='')
deploy_post_parser.add_argument(
    ARGS.MISC, type=str, location='form', default='{}')
deploy_get_parser = api.parser()
deploy_get_parser.add_argument(ARGS.DEPLOY_ID, type=int)
deploy_get_parser.add_argument(ARGS.ENVIRONMENT, type=str,
                               choices=ENUMS.environment)
deploy_get_parser.add_argument(ARGS.VERSION_TYPE, type=str,
                               choices=ENUMS.version_type)
deploy_get_parser.add_argument(ARGS.VERSION, type=str)
deploy_get_parser.add_argument(ARGS.THING_NAME, type=str)


##############################
# Flask BEFORE/AFTER request modifiers.


@app.before_request
def pre_request_logging():
    flask.g.start = time.time()
    app.logger.debug('\t'.join([
        datetime.datetime.today().ctime(),
        "PRE",
        flask.request.method,
        flask.request.url,
        flask.request.data]))


# Add logging after every request
@app.after_request
def post_request_logging(response):
    flask.g.status_code = response.status_code
    app.logger.info('\t'.join([
        datetime.datetime.today().ctime(),
        flask.request.remote_addr,
        flask.request.method,
        str(response.status_code),
        flask.request.url,
        flask.request.data]))
    return response


@app.teardown_request
def teardown_request(exception):
    seconds = time.time() - flask.g.start
    code = getattr(flask.g, 'status_code', 500)
    h.labels(flask.request.method,
             flask.request.url_rule, code).observe(seconds)
    if exception:
        e.labels(flask.request.method,
                 flask.request.url_rule, code).inc()

##############################
# Service routes.


@app.route("/")
def hello():
    return flask.render_template('index.html')


# keys incoming: search query, things to search
@app.route("/search")
def search():
    search_results = {}
    things_to_search = []
    request_vars = flask.request.args
    query_filter_opts = request_vars.get('query_filter')
    query_string = request_vars.get('query_string')

    app.logger.debug(request_vars)
    if query_filter_opts and query_string:
        if query_filter_opts == 'ALL':
            things_to_search = ENUMS.THING_TYPES
        elif query_filter_opts in ENUMS.THING_TYPES:
            things_to_search = [query_filter_opts]

    # transform query string into query dict

        query_args = parse_query_string(query_string)

        if len(query_args) > 0:
            search_results = search_with_attrs(query_args, things_to_search)

    return flask.render_template(
        'search.html',
        query_string=query_string,
        input_json=json.dumps(search_results))


# Takes in dict of <column:value>'s and a thing type and
# returns subset of valid columns for the thing type
def filter_args(params_dict, thing_type):
    valid_keys = set()
    param_keys = set(params_dict.keys())

    if thing_type == 'BUILDS':
        valid_keys = set(PgServer.wanted_build_columns)
    elif thing_type == 'ARTIFACTS':
        valid_keys = set(PgServer.wanted_artifact_columns)
    elif thing_type == 'DEPLOYS':
        valid_keys = set(PgServer.wanted_deploy_columns)
    elif thing_type == 'PROMOTES':
        valid_keys = set(PgServer.wanted_promote_columns)
    filtered_keys = param_keys & valid_keys
    if (len(filtered_keys) == 0) or (len(filtered_keys) != len(param_keys)):
        return {}

    cleaned_params_dict = {
        param: params_dict[param] for param in filtered_keys}
    return cleaned_params_dict


# Convert input string from search UI into query_args
def parse_query_string(query_string):
    query_args = defaultdict(lambda: list())
    comparators = ['<=', '>=', '<', '>']
    # for each "attr == val" clause in the query string
    for query_condition in query_string.split('&&'):
        # strip whitespaces
        query_condition = query_condition.replace(' ', '')

        if len(query_condition) > 0:
            args = {}
            # deal with == cases
            if '==' in query_condition:
                attr, value = query_condition.split('==')

                # if contains glob characters
                if '*' in value:
                    args['attr_alias'] = attr + '::text'
                    args['value'] = value.replace('*', '%')
                    args['condition'] = 'LIKE'
                else:
                    args['value'] = value
                    args['condition'] = '='
                query_args[attr].append(args)
            # deal with special comparators
            else:
                for comparator in comparators:
                    if comparator in query_condition:
                        attr, value = query_condition.split(comparator)
                        args['value'] = value
                        args['condition'] = comparator
                        query_args[attr].append(args)
                        break

    return query_args


# Convert input params from api endpoints into query_args
def parse_api_args(request_args):
    query_args = defaultdict(lambda: list())
    comparators = ['<=', '>=', '<', '>']
    for k, v in request_args.iteritems():
        found = False
        v = v.replace(' ', '')
        for query_condition in v.split(","):
            args = {}
            for comparator in comparators:
                if comparator == query_condition[:len(comparator)]:
                    found = True
                    args['value'] = query_condition.replace(comparator, '')
                    args['condition'] = comparator
                    query_args[k].append(args)
                    break
            if not found:
                if '*' in v:
                    args['attr_alias'] = k + '::text'
                    args['value'] = query_condition.replace('*', '%')
                    args['condition'] = 'LIKE'
                else:
                    args['value'] = query_condition
                    args['condition'] = '='
                query_args[k].append(args)
    return query_args


def found_thing_attrs(thing, search_args):
    for k, v in search_args.iteritems():
        if thing.get(k) == v:
            continue
        return False
    return True


def search_with_attrs(query_args, types_of_things):
    results = {}
    matched_builds = []
    matched_artifacts = []
    matched_deploys = []
    matched_promotes = []

    with PgServer(ENVIRONMENT_PROPERTIES) as server:
        for type_of_thing in types_of_things:
            search_args = filter_args(query_args, type_of_thing)
            if len(search_args) > 0:
                if type_of_thing == 'BUILDS':
                    for build in server.get_build_by_attrs(search_args):
                        matched_builds.append(build)
                    if len(matched_builds) > 0:
                        results['builds'] = matched_builds

                elif type_of_thing == 'ARTIFACTS':
                    for artifact in server.get_artifact_by_attrs(search_args):
                        matched_artifacts.append(artifact)
                    if len(matched_artifacts) > 0:
                        results['artifacts'] = matched_artifacts

                elif type_of_thing == 'DEPLOYS':
                    for deploy in server.get_deploy_by_attrs(search_args):
                        matched_deploys.append(deploy)
                    if len(matched_deploys) > 0:
                        results['deploys'] = matched_deploys

                elif type_of_thing == 'PROMOTES':
                    for promote in server.get_promote_by_attrs(search_args):
                        matched_promotes.append(promote)
                    if len(matched_promotes) > 0:
                        results['promotes'] = matched_promotes
    return results


@app.route("/api/v1/thing_attributes")
def thing_attrs():
    request_vars = flask.request.args
    app.logger.debug(request_vars)
    result = {}
    with PgServer(ENVIRONMENT_PROPERTIES) as server:
        result['build'] = server.wanted_build_columns
        result['artifact'] = server.wanted_artifact_columns
        result['deploy'] = server.wanted_deploy_columns
        result['promote'] = server.wanted_promote_columns
    return to_json(result)


@app.route("/api/v1/<thing_type>/attributes")
def specific_thing_attrs(thing_type):
    request_vars = flask.request.args
    app.logger.debug(request_vars)
    result = []

    if thing_type not in ENUMS.PATH_THING_TYPES:
        abort(404)

    with PgServer(ENVIRONMENT_PROPERTIES) as server:
        if thing_type == 'build':
            result = server.wanted_build_columns
        elif thing_type == 'artifact':
            result = server.wanted_artifact_columns
        elif thing_type == 'deploy':
            result = server.wanted_deploy_columns
        elif thing_type == 'promote':
            result = server.wanted_promote_columns

    return to_json(result)


@app.route("/api/v1/search")
def search_all():
    request_vars = flask.request.args
    app.logger.debug(request_vars)
    things_to_search = ['BUILDS', 'PROMOTES', 'DEPLOYS', 'ARTIFACTS']
    query_args = parse_api_args(request_vars)
    search_results = search_with_attrs(query_args, things_to_search)
    return to_json(search_results)


@app.route("/api/v1/build/search")
def search_builds():
    request_vars = flask.request.args
    app.logger.debug(request_vars)
    query_args = parse_api_args(request_vars)
    search_results = search_with_attrs(query_args, ['BUILDS'])
    return to_json(search_results)


@app.route("/api/v1/artifact/search")
def search_artifacts():
    request_vars = flask.request.args
    app.logger.debug(request_vars)
    query_args = parse_api_args(request_vars)
    search_results = search_with_attrs(query_args, ['ARTIFACTS'])
    return to_json(search_results)


@app.route("/api/v1/promote/search")
def search_promotes():
    request_vars = flask.request.args
    app.logger.debug(request_vars)
    query_args = parse_api_args(request_vars)
    search_results = search_with_attrs(query_args, ['PROMOTES'])
    return to_json(search_results)


@app.route("/api/v1/deploy/search")
def search_deploys():
    request_vars = flask.request.args
    app.logger.debug(request_vars)
    query_args = parse_api_args(request_vars)
    search_results = search_with_attrs(query_args, ['DEPLOYS'])
    return to_json(search_results)


@app.route("/healthz")
def healthz():
    """should-stay-alive-p?"""
    # nothing this code does that looks upstream will be fixed by
    # reaping this node; if we can't return ok, this node has a
    # problem.
    return "ok"


@app.route("/propertiez")
def propertiez():
    app.logger.info("checking propertiez")
    version = open('git_hash').read()
    build_date = open('build_date').read()
    app.logger.debug(version)
    return to_json({'version': version,
                    'build_date': build_date})


@app.route('/favicon.ico')
def favicon():
    return flask.send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/x-icon')

##############################
# API routes.


def to_json(data, code=200):
    """
    Convert response to json; set mimetype, set code.
    """
    response = flask.Response(json.dumps(data), code)
    response.mimetype = 'text/json'
    return response


@api.route("/build")
class Build(Resource):

    @api.marshal_list_with(build, code=200)
    @api.doc(parser=build_post_parser,
             responses={409: 'wrong options in the GET'})
    def get(self):
        """
        retrieve build assertion details
        """
        args = build_get_parser.parse_args()
        app.logger.debug(args)
        result = None
        code = 200

        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            if args.get(ARGS.JOB_URL):
                app.logger.debug(ARGS.JOB_URL)
                result = server.get_build_by_url(args[ARGS.JOB_URL])
            elif args.get(ARGS.BUILD_ID):
                app.logger.debug(ARGS.BUILD_ID)
                result = server.get_build_by_build_id(args[ARGS.BUILD_ID])
            elif args.get(ARGS.VERSION_TYPE) and args.get(ARGS.VERSION):
                result = server.get_build_by_version(
                    args[ARGS.VERSION_TYPE],
                    args[ARGS.VERSION])
            else:
                code = 409
                result = []
        result = [parse_times(x) for x in result]
        app.logger.debug(result)
        return result, code

    @api.doc(parser=build_post_parser)
    def post(self):
        """
        create a new build assertion
        """
        args = build_post_parser.parse_args()
        args[ARGS.MISC] = json.loads(args[ARGS.MISC])
        app.logger.debug(args)
        result = None
        code = 200
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.append_build(**args)
            app.logger.debug('created new build id: %d', result)
        return result, code


@api.doc(responses={404: 'no data available',
                    200: 'ok'})
@api.route("/build/<int:build_id>")
class BuildRecord(Resource):

    @api.marshal_list_with(build, code=200)
    def get(self, **kwargs):
        """
        get build based on its id
        """
        id = kwargs['build_id']
        app.logger.info("Getting id  %s", id)
        code = 200
        result = 'No data visible'
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.get_build_by_build_id(id)

        if result == []:
            code = 404

        result = [parse_times(x) for x in result]

        return result, code


@api.route("/build/all")
class BuildList(Resource):

    @api.marshal_list_with(build, code=200)
    def get(self):
        """
        list all build assertions
        """
        result = None
        code = 200
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.get_all_builds()
        app.logger.debug(result)
        result = [parse_times(x) for x in result]
        return result, code


# artifact
@api.route("/artifact")
class Artifact(Resource):

    @api.marshal_list_with(artifact, code=200)
    @api.doc(
        parser=artifact_get_parser,
        responses={409: 'unable to process the request: bad parameter type'})
    def get(self):
        """
        retrieve artifact details
        """
        result = []
        code = 200
        args = artifact_get_parser.parse_args()
        app.logger.debug(args)
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            if args.get(ARGS.FILENAME):
                result = server.get_artifact_by_filename(args[ARGS.FILENAME])
            elif args.get(ARGS.VERSION) and ARGS.VERSION_TYPE:
                result = server.get_artifact_by_version(
                    args[ARGS.VERSION_TYPE],
                    args[ARGS.VERSION])
            elif args.get(ARGS.BUILD_ID):
                result = server.get_artifact_by_build_id(args[ARGS.BUILD_ID])
            elif args.get(ARGS.ARTIFACT_ID):
                result = server.get_artifact_by_artifact_id(
                    args[ARGS.ARTIFACT_ID])
            else:
                code = 409
        result = [parse_times(x) for x in result]
        app.logger.debug('fetched artifact: %s', result)
        return result, code

    @api.doc(parser=artifact_post_parser,
             responses={404: 'build id not found'})
    def post(self):
        """
        create a new artifact
        """
        result = None
        code = 200
        args = artifact_post_parser.parse_args()
        args[ARGS.MISC] = json.loads(args[ARGS.MISC])
        app.logger.debug(args)
        try:
            with PgServer(ENVIRONMENT_PROPERTIES) as server:
                result = server.append_artifact(**args)
        except IntegrityError as ex:
            app.logger.warn(ex)
            api.abort(404, 'build id not found')
        return result, code


@api.doc(responses={404: 'no data available',
                    200: 'ok'})
@api.route("/artifact/<int:artifact_id>")
class ArtifactRecord(Resource):

    @api.marshal_list_with(artifact, code=200)
    @api.doc(responses={404: 'no data available',
                        200: 'ok'})
    def get(self, **kwargs):
        """
        get artifact based on its id
        """
        id = kwargs['artifact_id']
        app.logger.info("Getting id  %s", id)
        code = 200
        result = []
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.get_artifact_by_artifact_id(id)
        if result == []:
            code = 404
        result = [parse_times(x) for x in result]
        return result, code


@api.route("/artifact/all")
class ArtifactList(Resource):

    @api.marshal_list_with(artifact, code=200)
    def get(self):
        """
        list all artifacts
        """
        result = None
        code = 200
        args = flask.request.values
        app.logger.debug(args)

        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.get_all_artifacts()
        result = [parse_times(x) for x in result]
        return (result, code)

# not yet implemented
# @api.route("/artifact/history")
# class ArtifactHistory(Resource):
#
#     @api.doc(responses={409: 'arguments incorrect'},
#              params={ARGS.ARTIFACT_ID: 'artifact id'})
#     def get(self):
#         """
#         get map of the environments/deploys this artifact-id is in
#         """
#         args = flask.request.values
#         app.logger.debug(args)
#         result = None
#         artifact_id = args.get('artifact-id')
#         # TODO - Implement this.
#         if artifact_id:
#             result = None
#             with PgServer(ENVIRONMENT_PROPERTIES) as server:
#                 (result, code) = (
#                     server.get_artifact_history(artifact_id), 501)
#         else:
#             (result, code) = ("arguments incorrect", 409)
#
#         return result, code


@api.route("/promote")
class Promote(Resource):

    @api.marshal_list_with(promote, code=200)
    @api.doc(parser=promote_get_parser,
             responses={409: 'bad parameter type'},
             params={ARGS.PROMOTE_ID: 'promotion id',
                     ARGS.FILENAME: 'filename',
                     ARGS.ENVIRONMENT: 'environment'})
    def get(self):
        """
        retrieve details of promotion assertion
        """
        args = promote_get_parser.parse_args()
        app.logger.debug(args)
        result = []
        code = 200
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            if args.get(ARGS.THING_TYPE) and args.get(ARGS.THING_NAME):
                result = server.get_promote_by_thing(args[ARGS.THING_TYPE],
                                                     args[ARGS.THING_NAME])
            elif args.get(ARGS.ENVIRONMENT):
                result = server.get_promote_by_environment(
                    args[ARGS.ENVIRONMENT])
            elif args.get(ARGS.PROMOTE_ID):
                result = server.get_promote_by_promote_id(
                    args[ARGS.PROMOTE_ID])
            else:
                code = 409
        result = [parse_times(x) for x in result]
        app.logger.debug(result)
        return result, code

    @api.doc(parser=promote_post_parser,
             responses={404: 'thing id not found'})
    def post(self):
        """
        create a promotion assertion
        """
        args = promote_post_parser.parse_args()
        args[ARGS.MISC] = json.loads(args[ARGS.MISC])
        app.logger.debug(args)
        code = 200
        result = None
        try:
            with PgServer(ENVIRONMENT_PROPERTIES) as server:
                result = server.append_promote(**args)
        except IntegrityError as ex:
            app.logger.warn(ex)
            api.abort(404, 'thing id not found')
        return result, code


@api.doc(responses={404: 'no data available',
                    200: 'ok'})
@api.route("/promote/<int:promote_id>")
class PromoteRecord(Resource):

    @api.marshal_with(promote, code=200)
    def get(self, **kwargs):
        """
        get promote based on its id
        """
        id = kwargs['promote_id']
        app.logger.info("Getting id  %s", id)
        code = 200
        result = 'No data visible'
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.get_promote_by_promote_id(id)
        if result == []:
            code = 404
        result = [parse_times(x) for x in result]
        return result, code


@api.route("/promote/all")
class PromoteList(Resource):

    @api.marshal_list_with(promote, code=200)
    def get(self):
        """
        list all promotion assertions
        """
        args = flask.request.values
        app.logger.debug(args)
        result = None
        code = 200
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.get_all_promotes()
        app.logger.debug(result)
        result = [parse_times(x) for x in result]
        return result, code


# deploy
@api.route("/deploy")
class Deploy(Resource):

    @api.marshal_list_with(deploy, code=200)
    @api.doc(parser=deploy_get_parser,
             responses={409: ''},
             params={ARGS.DEPLOY_ID: 'deploy_id',
                     ARGS.ENVIRONMENT: 'environment',
                     ARGS.THING_NAME: 'thing_name'})
    def get(self):
        """
        retrieve details of deployment assertion
        """
        args = deploy_get_parser.parse_args()
        app.logger.debug(args)
        result = []
        code = 200
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            if args.get(ARGS.DEPLOY_ID):
                result = server.get_deploys_by_deploy_id(args[ARGS.DEPLOY_ID])
            elif args.get(ARGS.ENVIRONMENT):
                result = server.get_deploys_by_environment(
                    args[ARGS.ENVIRONMENT])
            elif args.get(ARGS.VERSION_TYPE) and args.get(ARGS.VERSION):
                result = server.get_deploys_by_version(
                    args[ARGS.VERSION_TYPE],
                    args[ARGS.VERSION]
                )
            elif args.get(ARGS.THING_NAME):
                result = server.get_deploys_by_thing_name(
                    args[ARGS.THING_NAME])
            else:
                code = 409
        result = [parse_times(x) for x in result]
        app.logger.debug(result)
        return result, code

    @api.doc(parser=deploy_post_parser,
             responses={200: 'created deployment'})
    def post(self):
        """
        create deployment assertion
        """
        args = deploy_post_parser.parse_args()
        args[ARGS.MISC] = json.loads(args[ARGS.MISC])

        app.logger.info("POST DEPLOY ARGS %s",  args)
        code = 200
        result = None
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.append_deploy(**args)
            app.logger.debug('successful deploy asserted: %d' % result)
        return result, code


@api.doc(responses={404: 'no data available',
                    200: 'ok'})
@api.route("/deploy/<int:deploy_id>")
class DeployRecord(Resource):

    @api.marshal_list_with(deploy, code=200)
    @api.doc(responses={404: 'no data available',
                        200: 'ok'})
    def get(self, **kwargs):
        """
        get deploy based on its id
        """
        id = kwargs['deploy_id']
        app.logger.info("Getting deploy id  %s", id)
        code = 200
        result = 'No data available'
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.get_deploys_by_deploy_id(id)
            app.logger.debug('got deploy records: %s', result)
        if result == []:
            code = 404
        result = [parse_times(x) for x in result]
        return result, code


@api.route("/deploy/all")
class DeployList(Resource):

    @api.marshal_list_with(deploy, code=200)
    @api.doc(responses={409: 'bad parameter type'})
    def get(self):
        """
        list all deployment assertions
        """
        args = flask.request.values
        app.logger.debug(args)
        result = None
        code = 200
        with PgServer(ENVIRONMENT_PROPERTIES) as server:
            result = server.get_all_deploys()
        result = [parse_times(x) for x in result]
        return result, code


# first-order queries:

# not yet implemented
# @api.route("/environment/current")
# class Environment(Resource):
#
#     @api.doc(responses={409: 'bad parameter type'})
#     def get(self):
#         """
#         list all recent artifact-ids in environment
#         """
#         args = flask.request.values
#         app.logger.debug(args)
#         response = None
#         code = 200
#         environment = args.get('environment')
#         # TODO - Implement this.
#         if environment:
#             with PgServer(ENVIRONMENT_PROPERTIES) as server:
#                 response = server.get_current_environment(environment)
#                 code = 501
#         else:
#             response = "arguments incorrect"
#             code = 409
#
#         return response, code


if __name__ == "__main__":
    # this is only for development.
    # note that production use runs app.web in a twistd server
    app.run(debug=True, host='::', port=5000, threaded=True)
