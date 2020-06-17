# PyCodecs
PyCodecs: A simple (image) codec interface. In early alpha stage.

## Capabilities

The (for now) supported codecs are listed below. 
Only image coding is supported.
Some codecs can be supplied with data via IPC (pipe), so you can encode and decode directly from and to memory,
i.e. a `numpy.ndarray` doesn't have to be saved to disk first.

Codec | Pipe | Info
----- | ---- | ----
WebP | No | https://developers.google.com/speed/webp
BPG/H265 | No |  https://bellard.org/bpg/
X265 | Yes | http://x265.org/
AV1 | Yes | https://aomedia.org/av1-features/get-started/

### Caveats

While there are certainly some bugs hidden and the API design isn't final, the size 
estimates for the AV1 code are too high, because the bitstream is wrapped in FFMPEG's _NUT_ format.
This is to be fixed soon. X265 writes raw _hevc_ format on the contrary (you can enforce _NUT_ for comparison, though).

## Install
To install, first clone `git clone https://github.com/kloppjp/pycodecs.git`

Install requirements with `pip install -r requirements.txt`

Or, if you use conda: `conda install --file requirements.txt`

Install PyCodecs for use: `pip install .`

Or for development (your changes are applied locally directly): `pip install -e .`

If you want to use AV1, you can get a current ffmpeg build with AV1 and x265 by running (you will be prompted for root): 
```shell script
bash util/install_ffmpeg_av1_x265.sh
```

Same goes for BPG (providing x265 and h265/JCTVC image coding):
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
python examples/example.py PATH_TO_FFMPEG_WITH_X265_AV1
```

Alternatively, as simple as this:
```python
import pycodecs
x265 = pycodecs.X265(colourspace='ycbcr')
if x265.available():
    x265.apply(original="example.png", quality=37, encoded=f"example_37.{x265.file_extension}",
    decoded="example_decoded_37.png")
```
