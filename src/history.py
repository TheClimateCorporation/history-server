#!/usr/bin/python
import argparse
import logging
import sys
from pprint import pprint
from backend import PgServer, ThingType
logging.basicConfig(format='%(asctime)-15s %(levelname)s: %(message)s')
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

def arg_handler():
    parser = argparse.ArgumentParser(description="command line interface to the history server")
    # parser.add_argument('--dry-run', '-n', action='store_true', help="Dry_run")
    subparsers = parser.add_subparsers(help='sub-command help',
                                       title='queries',
                                       dest='command')

    temp_parser = subparsers.add_parser('w-changeset')
    temp_parser.add_argument('value',nargs='+')

    temp_parser = subparsers.add_parser('w-filename')
    temp_parser.add_argument('value',nargs='+')

    temp_parser = subparsers.add_parser('w-servername')
    temp_parser.add_argument('value',)

    temp_parser = subparsers.add_parser('w-build')
    temp_parser.add_argument('changeset')
    temp_parser.add_argument('job_url')
    temp_parser.add_argument('job_description')
    temp_parser.add_argument('duration')
    temp_parser.add_argument('result')
    temp_parser.add_argument('misc')

    temp_parser = subparsers.add_parser('w-promote')
    temp_parser.add_argument('filename')
    temp_parser.add_argument('environment')
    temp_parser.add_argument('misc')

    temp_parser = subparsers.add_parser('promote')
    temp_parser.add_argument("--filename")
    temp_parser.add_argument("--environment")

    temp_parser = subparsers.add_parser('w-deploy')
    temp_parser.add_argument('thingtype')
    temp_parser.add_argument('thingname')
    temp_parser.add_argument('changeset')
    temp_parser.add_argument('environment')
    temp_parser.add_argument('misc')
    temp_parser.add_argument('--servername')

    temp_parser = subparsers.add_parser('deploy')
    temp_parser.add_argument('--environment')
    temp_parser.add_argument('--deploy_id')
    temp_parser.add_argument('--thing_name')
    temp_parser.add_argument('--changeset')

    temp_parser = subparsers.add_parser('w-artifact')
    temp_parser.add_argument('changeset')
    temp_parser.add_argument('filename')
    temp_parser.add_argument('build_id')
    temp_parser.add_argument('misc')

    temp_parser = subparsers.add_parser('artifact')
    temp_parser.add_argument('--filename')
    temp_parser.add_argument('--changeset')
    temp_parser.add_argument('--build-id')
    temp_parser.add_argument('--artifact-id')

    temp_parser = subparsers.add_parser('build')
    temp_parser.add_argument('--job-url')
    temp_parser.add_argument('--changeset')
    temp_parser.add_argument('--build-id')

    temp_parser = subparsers.add_parser('all-builds')
    temp_parser = subparsers.add_parser('all-artifacts')
    temp_parser = subparsers.add_parser('all-deploys')
    temp_parser = subparsers.add_parser('all-promotes')

    return parser.parse_args()

def main(args):
    args = arg_handler()
    command_string = args.command
    with PgServer() as server:
        if command_string == 'w-changeset':
            for v in args.value:
                server.ensure_version('changeset', v)

        elif command_string == 'w-filename':
            for v in args.value:
                server.append_thing(ThingType.FILENAME,
                                    v)

        elif command_string == 'w-servername':
            server.ensure_servername(
                args.value)

        elif command_string == 'w-build':
            print server.append_build(
                'changeset',
                args.changeset,
                args.job_url,
                args.job_description,
                args.duration,
                args.result,
                {} )
        elif command_string == 'build':
            if args.job_url:
                pprint(server.get_build_by_url(args.job_url))
            elif args.build_id:
                pprint(server.get_build_by_build_id(args.build_id))
            elif args.changeset:
                pprint(server.get_build_by_version('changeset', args.changeset))
            else:
                print "Must specify one of three options - execute --help"

        elif command_string == "all-builds":
            pprint(server.get_all_builds())

        elif command_string == 'w-artifact':
            print server.append_artifact(
                'changeset',
                args.changeset,
                args.filename,
                args.build_id,
                {})

        elif command_string == 'artifact':
            if args.filename:
                pprint(server.get_artifact_by_filename(args.filename))
            elif args.changeset:
                pprint(server.get_artifact_by_version('changeset', args.changeset))
            elif args.build_id:
                pprint(server.get_artifact_by_build_id(args.build_id))
            elif args.artifact_id:
                pprint(server.get_artifact_by_artifact_id(args.artifact_id))
            else:
                print "Must specify one of three options... see --help"

        elif command_string == "all-artifacts":
            pprint(server.get_all_artifacts())

        elif command_string == "all-deploys":
            pprint(server.get_all_deploys())

        elif command_string == "all-promotes":
            pprint(server.get_all_promotes())

        elif command_string == 'w-deploy':
            pprint(server.append_deploy(
                args.thingtype,
                args.thingname,
                'changeset',
                args.changeset,
                args.environment,
                args.servername,
                {}))
        elif command_string == "deploy":

            if args.environment:
                pprint(server.get_deploys_by_environment(args.environment))
            elif args.deploy_id:
                pprint(server.get_deploys_by_deploy_id(args.deploy_id))
            elif args.thing_name:
                pprint(server.get_deploys_by_thing_name(args.thing_name))
            elif args.changeset:
                pprint(server.get_deploys_by_version('changeset', args.changeset))
            else:
                print "must specify a correct option...  see --help"

        elif command_string == 'w-promote':
            pprint(server.append_promote(
                ThingType.FILENAME,
                args.filename,
                args.environment,
                {}))

        elif command_string == 'promote':
            if args.filename:
                pprint(server.get_promote_by_thing(ThingType.FILENAME,
                                                   args.filename))
            elif args.environment:
                pprint(server.get_promote_by_environment(args.environment))
            else:
                print "Need an option, specify --help"

        else:
            assert False, "unable to parse"
    return 0

if __name__ == "__main__":
    # assumes True / False
    main(sys.argv[1:])
    exit(0)
