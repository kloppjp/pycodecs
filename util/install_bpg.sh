#!/usr/bin/env bash

if [ -z "$1" ]
then
  BPG="$HOME/bpg"
  echo "No path for BPG supplied. Using ${BPG}."
else
  BPG=$1
  echo "BPG will be build in ${BPG}"
fi

sudo apt update
sudo apt install -y libpng-dev libjpeg-dev cmake yasm

mkdir -p $BPG && \
  git clone https://github.com/kloppjp/libbpg.git ${BPG} && \
  cd ${BPG} && \
  make && \
  sudo make install