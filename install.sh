#!/bin/sh
apt-get update

apt-get install --no-install-recommends \
    software-properties-common \
    gpg-agent 

add-apt-repository ppa:deadsnakes/ppa

apt-get install --no-install-recommends \
    build-essential \
    gcc \
    libgmp-dev \
    git \
    python3.9-dev \
    pip

pip install --upgrade pip
pip install pipenv

pipenv install
pipenv run pysmt-install ---msat
