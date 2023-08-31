#!/usr/bin/env bash

docker cp ./ telegrambot:/
docker restart telegrambot
