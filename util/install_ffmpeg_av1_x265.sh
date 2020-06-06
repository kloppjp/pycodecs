#!/usr/bin/env bash

if [ -z "$1" ]
then
  FFMPEG="$HOME/ffmpeg_aom"
  echo "No path for FFMPEG supplied. Using $FFMPEG. Binaries will be in $FFMPEG/bin"
else
  FFMPEG=$1
  echo "FFMPEG with AOM AV1 will be installed in $FFMPEG/bin"
fi

FFMPEG_SRC=$FFMPEG/src
FFMPEG_BIN=$FFMPEG/bin
FFMPEG_BLD=$FFMPEG/build

mkdir -p $FFMPEG_SRC $FFMPEG_BIN $FFMPEG_BLD

sudo apt update

sudo apt -y install \
  autoconf \
  automake \
  build-essential \
  cmake \
  git \
  libass-dev \
  libfreetype6-dev \
  libsdl2-dev \
  libtheora-dev \
  libtool \
  libva-dev \
  libvdpau-dev \
  libvorbis-dev \
  libxcb1-dev \
  libxcb-shm0-dev \
  libxcb-xfixes0-dev \
  mercurial \
  pkg-config \
  texinfo \
  wget \
  zlib1g-dev \
  yasm \
  libvpx-dev \
  libopus-dev \
  libx264-dev \
  libmp3lame-dev \
  libfdk-aac-dev

# Install libaom from source.
mkdir -p $FFMPEG_SRC/libaom && \
  cd $FFMPEG_SRC/libaom && \
  git clone https://aomedia.googlesource.com/aom && \
  cmake ./aom && \
  make && \
  sudo make install

# Install libx265 from source.
cd $FFMPEG_SRC && \
  hg clone https://bitbucket.org/multicoreware/x265 && \
  cd x265/build/linux && \
  cmake -G "Unix Makefiles" -DCMAKE_INSTALL_PREFIX="$FFMPEG_BLD" -DENABLE_SHARED:bool=off ../../source && \
  make && \
  make install

cd $FFMPEG_SRC && \
  wget -O ffmpeg-snapshot.tar.bz2 https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 && \
  tar xjvf ffmpeg-snapshot.tar.bz2 && \
  cd ffmpeg && \
  PKG_CONFIG_PATH="$FFMPEG_BLD/lib/pkgconfig" ./configure \
    --prefix="$FFMPEG_BLD" \
    --pkg-config-flags="--static" \
    --extra-cflags="-I$FFMPEG_BLD/include" \
    --extra-ldflags="-L$FFMPEG_BLD/lib" \
    --extra-libs="-lpthread -lm" \
    --bindir="$FFMPEG_BIN" \
    --enable-gpl \
    --enable-libass \
    --enable-libfdk-aac \
    --enable-libmp3lame \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libtheora \
    --enable-libfreetype \
    --enable-libvorbis \
    --enable-libopus \
    --enable-libvpx \
    --enable-libaom \
    --enable-nonfree && \
  make && \
  make install && \
  hash -r

