#!/bin/bash -ex
function finish {
    docker-compose kill
}
trap finish EXIT

echo -n "continuous-integration-build-" > git_hash
git rev-parse HEAD >> git_hash
date > build_date
docker-compose build
docker-compose up -d web

N=25
echo "Waiting $N seconds for Postgres to finish booting..."
sleep $N

docker-compose run tests

# ensure that we do not exit with a passing code unless all docker
# compose containers exited cleanly
# http://stackoverflow.com/questions/29568352/using-docker-compose-with-ci-how-to-deal-with-exit-codes-and-daemonized-linked
docker-compose ps
exit $(docker-compose ps -q | xargs docker inspect -f '{{ .State.ExitCode }}' | grep -v 0 | wc -l | tr -d ' ')
