#!/bin/bash

docker build -t telegram .
docker run --name telegrambot telegram
