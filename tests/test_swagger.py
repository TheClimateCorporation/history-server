#!/usr/bin/env python

import os

from swagger_tester import swagger_test

WEB_SERVER_HOST = os.getenv('WEB_SERVER_HOST', 'localhost')
WEB_SERVER_PORT = os.getenv('WEB_SERVER_PORT', '5000')
URL = 'http://{0}:{1}/api/v1'.format(WEB_SERVER_HOST, WEB_SERVER_PORT)

authorize_error = {
    'get': {
        '/api/v1/artifact/{artifact_id}': [404, 200],
        '/api/v1/promote/{promote_id}': [404, 200],
        '/api/v1/build/{build_id}': [404, 200],
        '/api/v1/deploy/{deploy_id}': [404, 200],
    },
    'post': {
        '/api/v1/artifact': [404, 200],
        '/api/v1/promote': [404, 200],
        '/api/v1/environment/current': [409, 200],
        },
    }


swagger_test(app_url=URL, authorize_error=authorize_error)
