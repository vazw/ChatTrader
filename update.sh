#!/bin/bash

docker cp ./* telegrambot:/
docker restart telegrambot
