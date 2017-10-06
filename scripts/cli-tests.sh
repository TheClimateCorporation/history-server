#!/bin/bash -ex

READLINK=${READLINK:-"readlink"}
cd $(dirname $(dirname $(${READLINK} -f $0)))/src

# Astute readers will notice that this draws from the G-Z portion of
# the alphabet. It's fake.
set +x
FAKE_GIT0=$(python -c "import random; import string; print ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(40))")
set -x

# pokes at each option in the cli, attempting to expose the underlying
# branch logic in the backend.
python ./history.py w-changeset $FAKE_GIT0
# do it again
python ./history.py w-changeset $FAKE_GIT0
python ./history.py w-filename `mktemp`
python ./history.py w-servername `mktemp`
set +x

FAKE_GIT=$(python -c "import random; import string; print ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(40))")

FAKE_GIT2=$(python -c "import random; import string; print ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(40))")

# populates the system with a few of these guys
DATA=$(cat /dev/urandom | head -c 30)
RANDOM_SLUG=$(echo ${DATA:21:3} | hexdump -v -e '/1 "%u"')
DURATION_SLUG=$(echo ${DATA:24:1} | hexdump -v -e '/1 "%u"')
MAJOR_SLUG=$(echo ${DATA:26:1} | hexdump -v -e '/1 "%0X"')
MINOR_SLUG=$(echo ${DATA:28:2} | hexdump -v -e '/1 "%0X"')
set -x

build_fk=$(python ./history.py w-build $FAKE_GIT "http://example.com/$RANDOM_SLUG" "Desc at $(date -R)" $DURATION_SLUG true no-op)

python history.py w-artifact $FAKE_GIT "artifact-$MAJOR_SLUG.$MINOR_SLUG" $build_fk no-op
python history.py w-artifact $FAKE_GIT "artifact-dev-$MAJOR_SLUG.$MINOR_SLUG" $build_fk no-op
artifact_fk=$(python history.py w-artifact $FAKE_GIT "artifact-docs-$MAJOR_SLUG.$MINOR_SLUG" $build_fk no-op)

python history.py w-deploy filename "artifact-$MAJOR_SLUG.$MINOR_SLUG"  $FAKE_GIT "qa" no-op --servername "server-null-qa"
python history.py w-deploy filename "artifact-$MAJOR_SLUG.$MINOR_SLUG"  $FAKE_GIT "production" no-op --servername "server-null-prod"

python history.py w-deploy config "config-$RANDOM_SLUG" $FAKE_GIT2 "qa"  no-op

python history.py w-promote "artifact-$MAJOR_SLUG.$MINOR_SLUG" qa no-op
python history.py w-promote "artifact-$MAJOR_SLUG.$MINOR_SLUG" production no-op

# read from all the things

# builds
python ./history.py all-builds
python ./history.py build --job-url "http://example.com/$RANDOM_SLUG"
python ./history.py build --changeset $FAKE_GIT
python ./history.py build --build-id $build_fk

# promotes
python ./history.py all-promotes
python ./history.py promote --filename "artifact-$MAJOR_SLUG.$MINOR_SLUG"
python ./history.py promote --environment "qa"

# artifacts
python ./history.py all-artifacts
python ./history.py artifact --filename "artifact-$MAJOR_SLUG.$MINOR_SLUG"
python ./history.py artifact --changeset $FAKE_GIT
python ./history.py artifact --build-id $build_fk
python ./history.py artifact --artifact-id $artifact_fk

# deploys
python ./history.py all-deploys
python ./history.py deploy --environment "production"
python ./history.py deploy --thing_name "artifact-$MAJOR_SLUG.$MINOR_SLUG"
python ./history.py deploy --deploy_id "$deploy_id"
python ./history.py deploy --changeset $FAKE_GIT0
python ./history.py deploy --changeset $FAKE_GIT
python ./history.py deploy --changeset $FAKE_GIT2
