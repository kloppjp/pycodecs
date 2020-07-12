from imageio import imread
from pycodecs import X265, AV1, BPG, Codec, X264, JPEG, JPEG2000
import numpy as np
from time import time
import argparse


def rgb2ycbcr(rgb_image: np.ndarray) -> np.ndarray:
    assert rgb_image.shape[-1] == 3, "RGB image does not have three channels in the last dimension"
    assert rgb_image.dtype == np.uint8, "RGB image doesn't have the correct data type"
    weights = np.zeros(shape=(3, 3), dtype=np.float32)
    weights[0] = (65.481 / 255.0, 128.553 / 255.0, 24.944 / 255.0)
    weights[1] = (-37.797 / 255.0, -74.203 / 255.0, 112.0 / 255.0)
    weights[2] = (112.0 / 255.0, -93.786 / 255.0, -18.214 / 255.0)
    bias = np.array((16.0, 128.0, 128.0), dtype=np.float32)
    return (np.matmul(rgb_image.astype(np.float32), weights.T) + bias).astype(np.uint8)


def encode(codec: Codec, image: str, show_syscalls: bool = False):

    if not codec.available():
        print(f"{codec.__class__.__name__} is not available on your computer, please use scripts in ./util/ to install.")
        return

    source = np.array(imread(image))
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
    if show_syscalls and len(codec.system_calls) >= 2:
        print(f"CMD: {codec.system_calls[-1][0]}\n"
              f"RSP: {codec.system_calls[-1][1]}\n"
              f"CMD: {codec.system_calls[-2][0]}\n"
              f"RSP: {codec.system_calls[-2][1]}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg_backend", type=str, choices=['ffmpeg', 'pyav'], default='ffmpeg')
    parser.add_argument("--ffmpeg_path", type=str, default=None)
    parser.add_argument("--image", type=str, default="examples/Kinkaku-ji.png")
    args = parser.parse_args()
    encode(codec=JPEG(quality=14, backend=args.ffmpeg_backend), image=args.image)
    encode(codec=JPEG2000(quality=19, backend=args.ffmpeg_backend), image=args.image)
    encode(codec=X264(ffmpeg_path=args.ffmpeg_path, backend=args.ffmpeg_backend, pixel_format='yuv444p', quality=37),
           image=args.image)
    encode(codec=BPG(format='444', quality=36), image=args.image)
    encode(codec=X265(ffmpeg_path=args.ffmpeg_path, backend=args.ffmpeg_backend, pixel_format='yuv444p', quality=37),
           image=args.image)
    encode(codec=AV1(ffmpeg_path=args.ffmpeg_path, backend=args.ffmpeg_backend, pixel_format='yuv444p', quality=42),
           image=args.image)

