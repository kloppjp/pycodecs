# PyCodecs
PyCodecs: A simple (image) codec interface. In early alpha stage.

_New in version 0.2.3: PyAV can be used as backend to reduce latency when making calls to ffmpeg_

## Capabilities

The (for now) supported codecs are listed below. 
Only image coding is supported.
Some codecs can be supplied with data via IPC (pipe) or direct call (via PyAV), so you can encode and decode directly from and to memory,
i.e. a `numpy.ndarray` doesn't have to be saved to disk first.

Codec | Backend | Info
----- | ---- | ----
WebP | syscall | https://developers.google.com/speed/webp
BPG/H265 | syscall |  https://bellard.org/bpg/
X265 | ffmpeg (pipe) / pyav (direct) | http://x265.org/
X264 | ffmpeg (pipe) / pyav (direct) | http://x264.org/
AV1 | ffmpeg (pipe) / pyav (direct) | https://aomedia.org/av1-features/get-started/
JPEG | ffmpeg (pipe) |
JPEG2000 | ffmpeg (pipe)

### Caveats

While there are certainly some bugs hidden and the API design isn't final, the size 
estimates for the AV1 code are too high, because the bitstream is wrapped in FFMPEG's _NUT_ format.
This is to be fixed soon. X265 writes raw _hevc_ format on the contrary (you can enforce _NUT_ for comparison, though).

## Install

1. Requirements
    1. pip:  `pip install -r requirements.txt`
    2. If you use Conda: `conda install --file requirements.txt`
2. If you'd like to use the PyAV backend
    1. FFMPEG (if not installed): `bash util/install_ffmpeg_av1_x265.sh $HOME/ffmpeg`
    2. Add paths to libraries to your environment (so that PyAV can find them)
        1. `export LD_LIBRARY_PATH="$HOME/ffmpeg/build/lib:$LD_LIBRARY_PATH"`
    3. Install PyAV: `pip install av --no-binary av --install-option="--ffmpeg-dir=$HOME/ffmpeg/build/"`
3. Install PyCodecs
    1. Clone: `git clone https://github.com/kloppjp/pycodecs.git`
    2. Setup: `cd pycodecs; pip install .` (use `-e` to install in developer mode)

Note that you can also use PyAV build with FFMPEG by installing `pip install av`, but I noticed
that the `crf` rate control didn't work for AV1, so I use my own ffmpeg build. 

If you want to use BPG, you need to install it:
```shell script
bash util/install_bpg.sh
```

## Use

Basic usage is simple, if you want to apply a codec, use the `n_bytes, restored = codec.apply(original, encoded, decodec, quality)` method.

- `original` path to image file or `numpy.ndarray` of dimension `HxWxC` or `CxHxW` typed `numpy.uint8` in RGB24 format
- (optional) `encoded` path where the encoded file should be stored. If not provided, a temporary file is used.
- (optional) `decoded` path where the decoded file should be stored. If not provided, a temporary file is used.
- (optional) `quality` quality index (`int`) to use. Otherwise the codec's setting is used.
- `n_bytes` size of the encoded bit stream in bytes
- `restored` restored image (RGB24 `numpy.ndarray` in same dimensionality as `original`), only if `decoded` is not supplied. If not provided, a temporary file is used.

### Examples
Take a look at examples/example.py or just run it with
```shell script
python examples/example.py
```
Optionally, you can specify the ffmpeg path via `--ffmpeg_path`, the backend with `--ffmpeg_backend` 
(either `ffmpeg` or `pyav`) and the image path with the `--image` option.

Alternatively, as simple as this:
```python
import pycodecs
x265 = pycodecs.X265(backend='pyav')
if x265.available():
    x265.apply(original="example.png", quality=37, encoded=f"example_37.{x265.file_extension}",
    decoded="example_decoded_37.png")
```
