# PyCodecs
PyCodecs simple (image) codec interface.

## Install
To install, first clone 
```shell script
git clone https://github.com/kloppjp/pycodecs.git
```
Install requirements:
```shell script
pip install -r requirements.txt
```
Or if you use conda:
```shell script
conda install --file requirements.txt
```
Install PyCodecs for use:
```shell script
pip install .
```
Install PyCodecs for development:
```shell script
pip install -e .
```

If you want to use AV1, you can get a current ffmpeg build with AV1 and x265 by running. 
Note that you will be prompted for root access.
```shell script
bash util/install_ffmpeg_av1_x265.sh
```

## Use

```python
import pycodecs
x265 = pycodecs.X265(colourspace='ycbcr')
if x265.available():
    x265.apply(original="example.png", quality=37, encoded=f"example_37.{x265.file_extension}",
    decoded="example_decoded_37.png")
```
