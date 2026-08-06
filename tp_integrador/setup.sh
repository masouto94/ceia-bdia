#!/bin/bash

docker compose down && sudo rm -rf postgres_data/ pgadmin_data/ && docker compose up -d
