from imageio import imread
from pycodecs import X265, AV1, BPG, Codec
import numpy as np
from time import time
import sys

TEST_IMAGE = "examples/PM5544_with_non-PAL_signals.png"


def rgb2ycbcr(rgb_image: np.ndarray) -> np.ndarray:
    assert rgb_image.shape[-1] == 3, "RGB image does not have three channels in the last dimension"
    assert rgb_image.dtype == np.uint8, "RGB image doesn't have the correct data type"
    weights = np.zeros(shape=(3, 3), dtype=np.float32)
    weights[0] = (65.481 / 255.0, 128.553 / 255.0, 24.944 / 255.0)
    weights[1] = (-37.797 / 255.0, -74.203 / 255.0, 112.0 / 255.0)
    weights[2] = (112.0 / 255.0, -93.786 / 255.0, -18.214 / 255.0)
    bias = np.array((16.0, 128.0, 128.0), dtype=np.float32)
    return (np.matmul(rgb_image.astype(np.float32), weights) + bias).astype(np.uint8)


def encode(codec: Codec):

    if not codec.available():
        print(f"{codec.__class__.__name__} is not available on your computer, please use scripts in ./util/ to install.")
        return

    source = np.array(imread(TEST_IMAGE))
    t0 = time()
    encoded_len, restored = codec.apply(original=source)
    dT = time() - t0
    se = np.square(rgb2ycbcr(restored).astype(np.float32) - rgb2ycbcr(source).astype(np.float32))
    mse = np.sum(np.mean(se, axis=(0, 1)) * np.array([6.0, 1.0, 1.0]) / 8.0)
    psnr = 10.0 * np.log10(255.0 * 255.0 / mse)
    print(
        f"{codec.__class__.__name__}: Encoded image has YCbCr444 PSNR={psnr:0.4f}dB at "
        f"{encoded_len * 8 / source.size * 3:0.4f}bpp. "
        f"Took {dT:0.4f}s")


if __name__ == "__main__":
    ffmpeg_path = None
    if len(sys.argv) > 1:
        ffmpeg_path = sys.argv[1]
    encode(codec=BPG(format='444', quality=22))
    encode(codec=X265(ffmpeg_path=ffmpeg_path, pixel_format='yuv444p', quality=33))
    encode(codec=AV1(ffmpeg_path=ffmpeg_path, pixel_format='yuv444p', quality=63))
