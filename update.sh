#!/bin/bash

git fetch --all && git reset --hard origin/main && git pull origin main
git submodule update