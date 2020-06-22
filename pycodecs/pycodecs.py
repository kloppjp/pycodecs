import numpy as np
from tempfile import NamedTemporaryFile
import imageio
import os
import subprocess
from typing import Union, List
from distutils.spawn import find_executable
import re
from .util import RoundRobinList


class Codec(object):

    def __init__(self, quality: int = None, call_log_len: int = 10):
        self.file_extension = None
        if quality is None:
            self.default_quality = self.quality_steps()[len(self.quality_steps()) // 2]
        else:
            self.default_quality = quality
        self.system_calls = RoundRobinList(max_size=call_log_len)

    def encode(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) \
            -> Union[None, bytes]:
        raise NotImplementedError()

    def decode(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        raise NotImplementedError()

    def can_pipe(self) -> bool:
        raise NotImplementedError()

    def quality_steps(self) -> List[int]:
        raise NotImplementedError()

    def available(self) -> bool:
        raise NotImplementedError()

    def apply(self, original: Union[np.ndarray, str], quality: int = None, encoded: str = None, decoded: str = None) -> \
            (int, np.ndarray):
        channels_first = False
        original_ndim = original.ndim
        encode_to_file = encoded is not None
        decode_to_file = decoded is not None
        original_file = None
        if type(original) == np.ndarray:
            if original.ndim == 4:
                if original.shape[0] != 1:
                    raise ValueError("If a 4D ndarray is supplied, it can only have a single entry in the first "
                                     "dimension")
                original = original[0]
            if original.ndim == 3:  # Check which is the channel dimension
                if original.shape[0] == 3 and not original.shape[2] == 3:
                    original = np.transpose(original, (1, 2, 0))
                    channels_first = True
            if not self.can_pipe():
                original_file = NamedTemporaryFile(suffix=".png")
                imageio.imwrite(original_file.name, original)
                original = original_file.name

        encoded_file = None
        if encoded is None and not self.can_pipe():
            encoded_file = NamedTemporaryFile(suffix=self.file_extension)
            encoded = encoded_file.name

        decoded_file = None
        if decoded is None and not self.can_pipe():
            decoded_file = NamedTemporaryFile(suffix=".png")
            decoded = decoded_file.name

        if quality is None:
            quality = self.default_quality

        encoder_output = self.encode(original, encoded, quality)
        if not encode_to_file and self.can_pipe():
            encoded = encoder_output
            encoded_size_bytes = len(encoded)
        else:
            encoded_size_bytes = os.stat(encoded).st_size

        decoder_output = self.decode(encoded, decoded)

        if not decode_to_file:
            if self.can_pipe():
                restored = decoder_output
            else:
                restored = imageio.imread(decoded)
        else:  # We don't restore if file is given (you can read it yourself)
            restored = None

        if restored is not None:
            if channels_first:
                restored = np.transpose(restored, (2, 0, 1))
            while restored.ndim < original_ndim:
                restored = restored[None]

        if decoded_file is not None:
            decoded_file.close()

        if encoded_file is not None:
            encoded_file.close()

        if original_file is not None:
            original_file.close()
        return encoded_size_bytes, restored


class BPG(Codec):

    def __init__(self, speed: int = 9, bitdepth: int = 12, colourspace: str = 'ycbcr', format: str = '444',
                 encoder: str = 'jctvc', **kwargs):
        super(BPG, self).__init__(**kwargs)
        self.speed = speed
        self.bitdepth = bitdepth
        self.colourspace = colourspace
        self.format = format
        self.file_extension = '.bpg'
        self.encoder = encoder

    def available(self):
        return not find_executable("bpgenc") is None and not find_executable("bpgdec") is None

    def encode(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) \
            -> Union[None, bytes]:
        if quality is None:
            quality = self.default_quality
        cmd = ["bpgenc", "-m", str(self.speed), "-b", str(self.bitdepth), "-q", str(quality), "-c",
                        self.colourspace, "-f", self.format, "-e", self.encoder, source, "-o", target]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        result = proc.communicate()
        self.system_calls.append((cmd, result[0].decode()))
        return None

    def decode(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        cmd = ["bpgdec", source, "-o", target]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        result = proc.communicate()
        self.system_calls.append((cmd, result[0].decode()))
        return None

    def quality_steps(self):
        return [q for q in range(51, 0, -1)]

    def can_pipe(self):
        return False


class H265(BPG):

    def __init__(self, **kwargs):
        super(H265, self).__init__(encoder='jctvc', **kwargs)


class WebP(Codec):

    def __init__(self, speed: int = 6, **kwargs):
        super(WebP, self).__init__(**kwargs)
        self.speed = speed
        self.file_extension = '.webp'

    def available(self):
        return not find_executable('cwebp') is None and not find_executable('dwebp') is None

    def encode(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) \
            -> Union[None, bytes]:
        if quality is None:
            quality = self.default_quality
        cmd = ["cwebp", "-quiet", "-m", str(self.speed), "-q", str(quality), source, "-o", target]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        result = proc.communicate()
        self.system_calls.append((cmd, result[0].decode()))
        return None

    def decode(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        cmd = ["dwebp", "-quiet", source, "-o", target]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        result = proc.communicate()
        self.system_calls.append((cmd, result[0].decode()))
        return None

    def quality_steps(self):
        return [q for q in range(0, 101)]

    def can_pipe(self):
        return False


class JPEGFI(Codec):

    def __init__(self, **kwargs):
        super(JPEGFI, self).__init__(**kwargs)
        self.file_extension = '.jif'

    def available(self):
        return True

    def encode(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) \
            -> Union[None, bytes]:
        if quality is None:
            quality = self.default_quality
        imageio.imwrite(target, imageio.imread(source), quality=quality, optimize=True, baseline=True)
        return None

    def decode(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        imageio.imwrite(target, imageio.imread(source))
        return None

    def quality_steps(self):
        return [q for q in range(1, 101)]

    def can_pipe(self) -> bool:
        return False


class JPEG(Codec):

    def __init__(self, **kwargs):
        super(JPEG, self).__init__(**kwargs)
        self.file_extension = '.jpg'

    def available(self):
        return True

    def encode(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) \
            -> Union[None, bytes]:
        if quality is None:
            quality = self.default_quality
        imageio.imwrite(target, imageio.imread(source), quality=quality, optimize=True)
        return None

    def decode(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        imageio.imwrite(target, imageio.imread(source))
        return None

    def quality_steps(self):
        return [q for q in range(1, 101)]

    def can_pipe(self) -> bool:
        return False


class FFMPEG(Codec):

    def __init__(self, pixel_format: str = 'yuv444p', ffmpeg_path: str = None, **kwargs):
        super(FFMPEG, self).__init__(**kwargs)
        self.file_extension = '.nut'
        self.format = 'nut'
        self.pixel_format = pixel_format
        self.codec = ''
        if ffmpeg_path is None or len(ffmpeg_path) == 0:
            self.ffmpeg_path = 'ffmpeg'
        elif os.path.isdir(ffmpeg_path):
            self.ffmpeg_path = os.path.join(ffmpeg_path, 'ffmpeg')
        else:
            self.ffmpeg_path = ffmpeg_path
        self.additional_output_commands = list()
        self.additional_input_commands = list()

    def can_pipe(self) -> bool:
        return True

    def _quality_param(self, quality: int) -> List[str]:
        raise NotImplementedError()

    def _available(self, codec_code: str):
        ffmpeg_exec = find_executable(self.ffmpeg_path)
        if ffmpeg_exec is None:
            return False
        output = subprocess.Popen([self.ffmpeg_path, '-hide_banner', '-codecs'], stdout=subprocess.PIPE).communicate()[0]
        output = output.decode().split('\n')
        for line in output:
            if codec_code in line:
                return True
        return False

    def encode(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) \
            -> Union[None, bytes]:
        if quality is None:
            quality = self.default_quality
        if quality not in self.quality_steps():
            raise ValueError("Given quality index is not a valid quality step!")

        input_cmd = list()
        if type(source) == str:
            source_file = source
        else:
            if type(source) != np.ndarray:
                source = np.ndarray(source)
            source_file = "-"
            input_cmd = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{source.shape[1]}x{source.shape[0]}"]
        target_file = target
        if target is None:
            target_file = "-"
        # , '-loglevel', 'panic', '-nostats'
        cmd = [self.ffmpeg_path, '-y', '-hide_banner'] + \
              self.additional_input_commands + input_cmd +\
              ["-i", source_file, "-c:v", self.codec, "-pix_fmt", self.pixel_format] \
              + self._quality_param(quality) + self.additional_output_commands + ['-f', self.format, target_file]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if type(source) == np.ndarray:
            stream, message = proc.communicate(input=source.tobytes()) # if target is a file, then stream will be None
        else:
            stream, message = proc.communicate()
        self.system_calls.append((cmd, message.decode()))
        return stream

    def decode(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        source_file = source
        if type(source) == bytes:
            source_file = "-"
        target_file = target
        output_spec = list()
        if target is None:
            target_file = "-"
            output_spec = ['-pix_fmt', 'rgb24', '-f', 'rawvideo']

        cmd = [self.ffmpeg_path, '-y', '-hide_banner', '-f', self.format, '-i', source_file] + output_spec + [target_file]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if type(source) == bytes:
            comm = proc.communicate(input=source)
        else:
            comm = proc.communicate()

        self.system_calls.append((cmd, comm[1].decode()))

        if target is None:
            h = w = 0
            for line in comm[1].decode().split('\n'):
                if line.strip().startswith("Stream"):
                    for d in line.strip().split(','):
                        match = re.search("^([0-9]{1,4})x([0-9]{1,4})$", d.strip())
                        if match is not None:
                            w = int(match.groups()[0])
                            h = int(match.groups()[1])
            if h == 0 or w == 0:
                raise ValueError(f"Could not find image dimensions in FFMPEG info: {comm[1].decode()}")
            return np.frombuffer(comm[0], dtype=np.uint8).reshape(h, w, 3)
        else:
            return None


class AV1(FFMPEG):

    def __init__(self, **kwargs):
        super(AV1, self).__init__(**kwargs)
        self.codec = "libaom-av1"
        self.additional_output_commands = ["-b:v", "0", "-strict", "experimental"]

    def available(self) -> bool:
        return super(AV1, self)._available('libaom-av1')

    def _quality_param(self, quality: int) -> List[str]:
        return ["-crf", f"{quality}"]

    def quality_steps(self):
        return [q for q in range(63, 0, -1)]


class X265(FFMPEG):

    def __init__(self, format: str = 'hevc', tune: str = 'ssim', **kwargs):
        super(X265, self).__init__(**kwargs)
        self.format = format
        self.codec = "libx265"
        self.additional_output_commands = ["-preset", "placebo", "-tune", tune]

    def available(self) -> bool:
        return super(X265, self)._available(self.codec)

    def _quality_param(self, quality: int) -> List[str]:
        return ["-x265-params", f"qp={quality}"]

    def quality_steps(self):
        return [q for q in range(51, 0, -1)]


codecs = {'bpg': BPG, 'webp': WebP, 'jpegfi': JPEGFI, 'av1': AV1, 'jpeg': JPEG, 'x265': X265}
