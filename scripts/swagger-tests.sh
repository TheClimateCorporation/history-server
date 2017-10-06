#!/bin/bash -ex

tmpdir=$(mktemp -d)
venv=${tmpdir}/venv
virtualenv ${venv}
${venv}/bin/pip install -U pip
${venv}/bin/pip install -r ../tests/requirements.txt
${venv}/bin/python ../tests/test_swagger.py
