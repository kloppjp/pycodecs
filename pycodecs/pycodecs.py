import numpy as np
from tempfile import NamedTemporaryFile
import imageio
import os
import subprocess
from typing import Union
from distutils.spawn import find_executable


class Codec(object):

    def __init__(self):
        self.file_extension = None

    def encode(self, ifile: str, ofile: str, quality: int):
        raise NotImplementedError()

    def decode(self, ifile: str, ofile: str):
        raise NotImplementedError()

    def quality_steps(self):
        raise NotImplementedError()

    def available(self):
        raise NotImplementedError()

    def apply(self, original: Union[np.ndarray, str], quality: int, encoded: str = None, decoded: str = None) -> \
            (int, np.ndarray):
        if type(original) == np.ndarray:
            original_file = NamedTemporaryFile(suffix=".png")
            imageio.imsave(original_file.name, original)
            original_file_name = original_file.name
        else:
            original_file_name = original

        if encoded is None:
            encoded_file = NamedTemporaryFile(suffix=self.file_extension)
            encoded_file_name = encoded_file.name
        else:
            encoded_file_name = encoded

        if decoded is None:
            decoded_file = NamedTemporaryFile(suffix=".png")
            decoded_file_name = decoded_file.name
        else:
            decoded_file_name = decoded

        self.encode(original_file_name, encoded_file_name, quality)
        self.decode(encoded_file_name, decoded_file_name)

        encoded_size_bytes = os.stat(encoded_file_name).st_size

        restored = None
        if decoded is None:
            restored = imageio.imread(decoded_file_name)
            decoded_file.close()

        if encoded is None:
            encoded_file.close()

        if type(original) == np.ndarray:
            original_file.close()
        return encoded_size_bytes, restored


class BPG(Codec):

    def __init__(self, speed: int = 9, bitdepth: int = 12, colourspace: str = 'ycbcr', format: str = '444',
                 encoder: str = 'jctvc'):
        super(BPG, self).__init__()
        self.speed = speed
        self.bitdepth = bitdepth
        self.colourspace = colourspace
        self.format = format
        self.file_extension = '.bpg'
        self.encoder = encoder

    def available(self):
        return not find_executable("bpgenc") is None and not find_executable("bpgdec") is None

    def encode(self, ifile: str, ofile: str, quality: int):
        subprocess.run(["bpgenc", "-m", str(self.speed), "-b", str(self.bitdepth), "-q", str(quality), "-c",
                        self.colourspace, "-f", self.format, "-e", self.encoder, ifile, "-o", ofile])

    def decode(self, ifile: str, ofile: str):
        subprocess.run(["bpgdec", ifile, "-o", ofile])

    def quality_steps(self):
        return range(51, 0, -1)


class X265(BPG):

    def __init__(self, **kwargs):
        super(X265, self).__init__(encoder='x265', **kwargs)


class H265(BPG):

    def __init__(self, **kwargs):
        super(H265, self).__init__(encoder='jctvc', **kwargs)


class WebP(Codec):

    def __init__(self, speed: int = 6):
        super().__init__()
        self.speed = speed
        self.file_extension = '.webp'

    def available(self):
        return not find_executable('cwebp') is None and not find_executable('dwebp') is None

    def encode(self, ifile: str, ofile: str, quality: int):
        subprocess.run(["cwebp", "-quiet", "-m", str(self.speed), "-q", str(quality), ifile, "-o", ofile])

    def decode(self, ifile: str, ofile: str):
        subprocess.run(["dwebp", "-quiet", ifile, "-o", ofile])

    def quality_steps(self):
        return range(0, 101)


class JPEGFI(Codec):

    def __init__(self):
        super(JPEGFI, self).__init__()
        self.file_extension = '.jif'

    def available(self):
        return True

    def encode(self, ifile: str, ofile: str, quality: int):
        imageio.imwrite(ofile, imageio.imread(ifile), quality=quality, optimize=True, baseline=True)

    def decode(self, ifile: str, ofile: str):
        imageio.imwrite(ofile, imageio.imread(ifile))

    def quality_steps(self):
        return range(1, 101)


class JPEG(Codec):

    def __init__(self):
        super(JPEG, self).__init__()
        self.file_extension = '.jpg'

    def available(self):
        return True

    def encode(self, ifile: str, ofile: str, quality: int):
        imageio.imwrite(ofile, imageio.imread(ifile), quality=quality, optimize=True)

    def decode(self, ifile: str, ofile: str):
        imageio.imwrite(ofile, imageio.imread(ifile))

    def quality_steps(self):
        return range(1, 101)


class AV1(Codec):

    def __init__(self, pixel_format: str = 'yuv444p', ffmpeg_path: str = None):
        super(AV1, self).__init__()
        self.file_extension = '.ivf'
        self.pixel_format = pixel_format
        if ffmpeg_path is None:
            self.ffmpeg_path = 'ffmpeg'
        else:
            self.ffmpeg_path = ffmpeg_path

    def available(self):
        ffmpeg_exec = find_executable(self.ffmpeg_path)
        if ffmpeg_exec is None:
            return False
        output = subprocess.Popen([self.ffmpeg_path, '-hide_banner', '-codecs'], stdout=subprocess.PIPE).communicate()
        for line in output:
            if "libaom-av1" in line.decode():
                return True
        return False

    def encode(self, ifile: str, ofile: str, quality: int):
        subprocess.run([self.ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'panic',
                        "-i", ifile, "-c:v", "libaom-av1", "-pix_fmt", self.pixel_format, "-crf", f"{quality}",
                        "-b:v", "0", "-strict", "experimental", ofile])

    def decode(self, ifile: str, ofile: str):
        subprocess.run([self.ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'panic',
                        '-i', ifile, ofile])

    def quality_steps(self):
        return range(60, 0, -1)


codecs = {'bpg': BPG, 'webp': WebP, 'jpegfi': JPEGFI, 'av1': AV1, 'jpeg': JPEG, 'x265': X265}