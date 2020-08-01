import numpy as np
from tempfile import NamedTemporaryFile
import imageio
import os
import subprocess
from typing import Union, List, Dict
from distutils.spawn import find_executable
import re
from .util import RoundRobinList
from io import BytesIO

try:
    import av
    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False


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


def _param_to_arg_list(param: Dict[str, str]) -> List[str]:
    result = list()
    for k, v in param.items():
        if v is None:
            continue
        result.append(f"-{k}")
        result.append(v)
    return result


class FFMPEG(Codec):

    def __init__(self, pixel_format: str = 'yuv444p', ffmpeg_path: str = None, backend: str = None, format: str = 'nut',
                 file_extension: str = '.nut', **kwargs):
        super(FFMPEG, self).__init__(**kwargs)
        self.file_extension = file_extension
        self.format = format
        self.pixel_format = pixel_format
        self.codec = ''
        if ffmpeg_path is None or len(ffmpeg_path) == 0:
            self.ffmpeg_path = 'ffmpeg'
        elif os.path.isdir(ffmpeg_path):
            self.ffmpeg_path = os.path.join(ffmpeg_path, 'ffmpeg')
        else:
            self.ffmpeg_path = ffmpeg_path
        self.additional_output_commands = dict()
        self.additional_input_commands = dict()
        assert backend in ('ffmpeg', 'pyav', None)
        if PYAV_AVAILABLE and backend in ('pyav', None):
            self._backend = 'pyav'
        elif self._is_ffmpeg_backend_available() and backend in ('ffmpeg', None):
            self._backend = 'ffmpeg'
        else:
            raise LookupError("Could not find any suitable backend for ffmpeg-based codecs.")

    @property
    def backend(self) -> str:
        return self._backend

    def can_pipe(self) -> bool:
        return True

    def _quality_param(self, quality: int) -> Dict[str, str]:
        raise NotImplementedError()

    def _is_ffmpeg_backend_available(self) -> bool:
        ffmpeg_exec = find_executable(self.ffmpeg_path)
        if ffmpeg_exec is None:
            return False
        return True

    def _available(self, codec_code: str):
        if self.backend == 'pyav':
            return codec_code in av.codec.codecs_available
        elif self.backend == 'ffmpeg':
            if not self._is_ffmpeg_backend_available():
                return False
            output = subprocess.Popen([self.ffmpeg_path, '-hide_banner', '-codecs'], stdout=subprocess.PIPE).communicate()[0]
            output = output.decode().split('\n')
            for line in output:
                if codec_code in line:
                    return True
        return False

    def _encode_pyav(self, source: np.ndarray, quality: int) -> bytes:
        assert type(source) == np.ndarray, f"Source must be numpy.ndarray for PyAV but was {type(source)}"
        options_dict = dict()
        for k, v in self.additional_output_commands.items():
            if v is None:
                continue
            options_dict[k] = v
        for k, v in self._quality_param(quality).items():
            if k in options_dict.keys():
                options_dict[k] = options_dict[k] + ":" + v
            else:
                options_dict[k] = v
        bio = BytesIO()
        container = av.open(bio, mode='w', format=self.format)

        stream = container.add_stream(self.codec, rate=1, framerate=1, options=options_dict)
        stream.width = source.shape[1]
        stream.height = source.shape[0]
        stream.pix_fmt = self.pixel_format
        stream.codec_context.bit_rate = 0  # Needs to be set to 0 for libaom-av1 to work properly
        stream.codec_context.bit_rate_tolerance = 0
        # Mux the packets of the stream into the container
        frame = av.VideoFrame.from_ndarray(source, format='rgb24')
        for packet in stream.encode(frame):
            container.mux(packet)
        # Write any residual information
        for packet in stream.encode():
            container.mux(packet)
        container.close()
        return bio.getvalue()

    def _decode_pyav(self, source: bytes) -> np.ndarray:
        bio = BytesIO(source)
        container = av.open(bio, mode='r', format=self.format)
        for frame in container.decode(video=0):
            return frame.to_ndarray(format='rgb24')

    def _encode_ffmpeg(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) \
            -> Union[None, bytes]:
        input_cmd = list()
        if type(source) == str:
            source_file = source
        else:
            if type(source) != np.ndarray:
                source = np.array(source)
            source_file = "-"
            input_cmd = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{source.shape[1]}x{source.shape[0]}"]
        target_file = target
        if target is None:
            target_file = "-"
        target_pixel_format = []
        if self.pixel_format is not None:
            target_pixel_format = ["-pix_fmt", self.pixel_format]
        # , '-loglevel', 'panic', '-nostats'
        cmd = [self.ffmpeg_path, '-y', '-hide_banner'] + \
            _param_to_arg_list(self.additional_input_commands) + input_cmd + \
              ["-i", source_file, "-c:v", self.codec] + target_pixel_format \
            + _param_to_arg_list(self._quality_param(quality)) \
            + _param_to_arg_list(self.additional_output_commands) +\
              ['-f', self.format, target_file]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if type(source) == np.ndarray:
            stream, message = proc.communicate(input=source.tobytes())  # if target is a file, then stream will be None
        else:
            stream, message = proc.communicate()
        self.system_calls.append((cmd, message.decode()))
        return stream

    def encode(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) \
            -> Union[None, bytes]:
        if quality is None:
            quality = self.default_quality
        if quality not in self.quality_steps():
            raise ValueError("Given quality index is not a valid quality step!")

        if self.backend == 'ffmpeg':
            return self._encode_ffmpeg(source, target, quality)
        elif self.backend == 'pyav':
            if type(source) == str:
                raise ValueError("PyAV backend for now only supports numpy.ndarray")
            return self._encode_pyav(source, quality)

    def _decode_ffmpeg(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        source_file = source
        if type(source) == bytes:
            source_file = "-"
        target_file = target
        output_spec = list()
        if target is None:
            target_file = "-"
            output_spec = ['-pix_fmt', 'rgb24', '-f', 'rawvideo']

        cmd = [self.ffmpeg_path, '-y', '-hide_banner', '-f', self.format, '-i', source_file] + output_spec + [
            target_file]
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
                raise ValueError(f"Could not find image dimensions in FFMPEG info.\n"
                                 f"Last two commands/responses:\n"
                                 f"CMD: {self.system_calls[-1][0]}\n"
                                 f"RSP: {self.system_calls[-1][1]}\n"
                                 f"CMD: {self.system_calls[-2][0]}\n"
                                 f"RSP: {self.system_calls[-2][1]}")
            return np.frombuffer(comm[0], dtype=np.uint8).reshape(h, w, 3)
        else:
            return None

    def decode(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        if self.backend == 'ffmpeg':
            return self._decode_ffmpeg(source, target)
        elif self.backend == 'pyav':
            return self._decode_pyav(source)


class AV1(FFMPEG):

    def __init__(self, **kwargs):
        super(AV1, self).__init__(**kwargs)
        self.codec = "libaom-av1"
        self.additional_output_commands = {"strict": "experimental", "b:v": "0"}

    def available(self) -> bool:
        return super(AV1, self)._available('libaom-av1')

    def _quality_param(self, quality: int) -> Dict[str, str]:
        return {"crf": f"{quality}"}

    def quality_steps(self):
        return [q for q in range(63, 0, -1)]


class X265(FFMPEG):

    def __init__(self, tune: Union[str, None] = 'ssim', preset: str = 'veryslow', format: str = 'hevc', **kwargs):
        super(X265, self).__init__(**kwargs)
        self.format = format
        self.codec = "libx265"
        self.preset = preset
        self.additional_output_commands = {"preset": preset}
        if tune is not None:
            if self.format == 'nut' and self.backend == 'pyav':
                raise ValueError("Error: Using the NUT format with x265 tuning (especially psnr/ssim) is known to"
                                 " yield errors within PyAV, please either deactivate tuning or choose hevc format")
            self.additional_output_commands["tune"] = tune
        if self.backend == 'pyav':
            self.additional_output_commands['x265-params'] = 'log-level=0'

    def available(self) -> bool:
        return super(X265, self)._available(self.codec)

    def _quality_param(self, quality: int) -> Dict[str, str]:
        return {"x265-params": f"qp={quality}"}

    def quality_steps(self):
        return [q for q in range(51, -1, -1)]


class X264(FFMPEG):

    available_presets = ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower',
                         'veryslow', 'placebo')
    available_tunes = ('film', 'animation', 'grain', 'stillimage', 'fastdecode', 'zerolatency', 'psnr', 'ssim', None)

    def __init__(self, tune: Union[str, None] = None, preset: str = 'veryslow', format: str = 'h264', **kwargs):
        super(X264, self).__init__(**kwargs)
        assert preset in self.available_presets, f"Chosen preset '{preset}' is not available."
        assert tune in self.available_tunes, f"Chosen tune '{tune}' is not available."
        self.format = format
        self.codec = "libx264"
        self.preset = preset
        self.additional_output_commands = {"preset": preset}
        if tune is not None:
            self.additional_output_commands["tune"] = tune

    def available(self) -> bool:
        return super(X264, self)._available(self.codec)

    def _quality_param(self, quality: int) -> Dict[str, str]:
        return {"x264-params": f"qp={quality}"}

    def quality_steps(self):
        return [q for q in range(51, -1, -1)]


# ToDo: Properly transmit quality parameter when JPEG is used with PyAV
class MJPEG(FFMPEG):

    def __init__(self, **kwargs):
        super(MJPEG, self).__init__(**kwargs)
        self.format = 'nut'
        self.codec = 'mjpeg'
        self.pixel_format = 'yuvj444p'
        if not self.backend == 'ffmpeg':
            if not super(JPEG, self)._is_ffmpeg_backend_available():
                raise LookupError(f"{self.__class__.__name__} is currently only available with ffmpeg backend, but the"
                                  f"ffmpeg executable could not be found.")
            else:
                self._backend = 'ffmpeg'

    def available(self) -> bool:
        return super(MJPEG, self)._available(self.codec)

    def _quality_param(self, quality: int) -> Dict[str, str]:
        return {"qscale:v": f"{quality}"}

    def quality_steps(self) -> List[int]:
        return [q for q in range(31, 1, -1)]


# ToDo: Properly transmit quality parameter when JPEG2000 is used with PyAV
class JPEG2000(FFMPEG):

    def __init__(self, **kwargs):
        super(JPEG2000, self).__init__(**kwargs)
        self.format = 'nut'
        self.codec = 'jpeg2000'
        self.pixel_format = 'yuv444p'
        if not self.backend == 'ffmpeg':
            if not super(JPEG2000, self)._is_ffmpeg_backend_available():
                raise LookupError(f"{self.__class__.__name__} is currently only available with ffmpeg backend, but the"
                                  f"ffmpeg executable could not be found.")
            else:
                self._backend = 'ffmpeg'

    def available(self) -> bool:
        return super(JPEG2000, self)._available(self.codec)

    def _quality_param(self, quality: int) -> Dict[str, str]:
        return {"qscale:v": f"{quality}"}

    def quality_steps(self) -> List[int]:
        return [q for q in range(31, 1, -1)]


class JPEG(Codec):

    def __init__(self, optimize: bool = True, **kwargs):
        super(JPEG, self).__init__(**kwargs)
        self.optimize = optimize

    def available(self) -> bool:
        return True

    def encode(self, source: Union[str, np.ndarray], target: Union[str, None] = None, quality: int = None) -> Union[None, bytes]:
        if quality is None:
            quality = self.default_quality
        out = BytesIO()
        if self.optimize:
            imageio.imwrite(out, source, format='jpeg', quality=quality, optimize=True)
        else:
            imageio.imwrite(out, source, format='jpeg', quality=quality)
        return out.getvalue()

    def decode(self, source: Union[str, bytes], target: Union[str, None] = None) -> Union[None, np.ndarray]:
        io = BytesIO(initial_bytes=source)
        return np.asarray(imageio.imread(io, format='jpeg', pilmode='RGB'))

    def quality_steps(self) -> List[int]:
        return list(range(1, 101))

    def can_pipe(self) -> bool:
        return True

