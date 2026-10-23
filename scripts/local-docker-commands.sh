#!/usr/bin/env bash
# Manual docker workflow from the original practical (reference only - run line by line).
docker build -t course:local ./course
docker build -t registration:local ./registration
docker network create network-1
docker run -d --name course --network network-1 -p 5001:5001 course:local
docker run -d --name registration --network network-1 \
  -e COURSE_SERVICE_URL=http://course:5001 -p 5000:5000 registration:local

BASE_URL=http://localhost:5000 ./scripts/smoke-test.sh

docker rm -f registration course
docker network rm network-1

# Or with compose:
docker compose up --build -d
