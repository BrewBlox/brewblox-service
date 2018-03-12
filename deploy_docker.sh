#! /bin/bash
set -e

BASE=brewblox/brewblox-service
PREFIX=$1
LATEST=latest
echo "prefixing docker image with $PREFIX"

# Login and build
docker login -u="$DOCKER_USER" --password-stdin <<< "$DOCKER_PASSWORD"
docker build -t $BASE docker/

# Always push latest image
docker tag $BASE $BASE:$PREFIX$LATEST
docker push $BASE:$PREFIX$LATEST

# If we're in a Travis build: push a specific image
if [ "$CI" == "true" ]; then
    docker tag $BASE $BASE:$PREFIX$TRAVIS_BRANCH
    docker push $BASE:$PREFIX$TRAVIS_BRANCH
fi
