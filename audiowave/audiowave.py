import enum
import io, wave, typing

__author__ = "PRMPSmart @prmpsmart"

FLOATS = list[float]
INTS_FLOATS = list[typing.Union[float, int]]
LIST_INTS_FLOATS = list[INTS_FLOATS]

INTS = list[int]
LIST_INTS = list[INTS]
TUPLED_INTS = tuple[int]
TUPLED_INTS_FLOATS = tuple[typing.Union[float, int]]
LIST_TUPLED_INTS = list[TUPLED_INTS]
LIST_TUPLED_INTS_FLOATS = list[TUPLED_INTS_FLOATS]

MAX_CHANNELS = 2
BUFFER_SIZE = 1024

MIN_SLICE = slice(0, None, 2)
MAX_SLICE = slice(1, None, 2)


class AudioWave:
    def __init__(
        self, byte_converter: typing.Callable[[bytes], int] = None, *args, **kwargs
    ):

        self.byte_converter = byte_converter
        self.__bytes = b""
        self.__sample_width = 0
        self.__channels = 0
        self.__total_frames = 0
        self.__compression_name = ""
        self.__compression_type = ""
        self.__frame_rate = 0

        self.__array: INTS = []
        self.__channels_array: LIST_INTS = []
        self.__channels_min_max_array: list[LIST_INTS] = []
        self.__channels_min_max_tupled_array: list[LIST_TUPLED_INTS] = []

        self.__real_array: INTS = []
        self.__channels_real_array: LIST_INTS = []
        self.__channels_min_max_real_array: list[LIST_INTS] = []
        self.__channels_min_max_tupled_real_array: list[LIST_TUPLED_INTS] = []

        if args or kwargs:
            self.open(*args, **kwargs)

    # scaling

    def scale(self, array: INTS, scale: int) -> INTS_FLOATS:
        self.check_array(array)

        min_ = min(array)
        max_ = max(array)

        scaled_array: INTS_FLOATS = []

        for point in array:
            reference_point = min_ if point < 0 else max_
            scale_factor = scale / reference_point
            scaled_point = point * scale_factor
            scaled_array.append(scaled_point)

        return scaled_array

    # sampling

    def sample(self, array: INTS_FLOATS, samples: int):
        self.check_array(array)
        slicer = len(array) // samples
        return array[::slicer]

    def save(self, name: str):
        if self.bytes:
            wave_write = wave.Wave_write(name)
            wave_write.setnchannels(self.channels)
            wave_write.setsampwidth(self.sample_width)
            wave_write.setframerate(self.frame_rate)
            wave_write.writeframes(self.bytes)
            wave_write.close()

    def open(
        self,
        file: typing.Union[io.TextIOWrapper, str] = "",
        bytes: bytes = b"",
        array: INTS = [],
        channels: int = 1,
        with_header: bool = True,
    ):
        self.clear()
        self.__channels = channels

        if bytes and with_header:
            file = io.BytesIO(bytes)

        if file:
            _wave = wave.Wave_read(file)
            bytes = _wave._data_chunk.read()
            self.__sample_width = _wave.getsampwidth()
            self.__channels = _wave.getnchannels()
            self.__total_frames = _wave.getnframes()
            self.__compression_name = _wave.getcompname()
            self.__compression_type = _wave.getcomptype()
            self.__frame_rate = _wave.getframerate()

        elif array:
            self.__array = array

        self.__bytes = bytes
        self.check_channel(self.channels)

    def clear(self):
        self.__bytes = b""
        self.__array.clear()
        self.__channels_array.clear()
        self.__channels_min_max_array.clear()
        self.__channels_min_max_tupled_array.clear()

        self.__real_array.clear()
        self.__channels_real_array.clear()
        self.__channels_min_max_real_array.clear()
        self.__channels_min_max_tupled_real_array.clear()

    def check_channel(self, channel):
        assert channel in [1, 2], "channel 1 or 2 supported"

    def check_array(self, array):
        assert isinstance(array, list), f"array must be {INTS}"

    @property
    def bits(self):
        return self.sample_width * 8

    @property
    def sample_width(self):
        return self.__sample_width

    @property
    def channels(self):
        return self.__channels

    @property
    def total_frames(self):
        if self.__total_frames:
            return self.__total_frames
        return len(self.channels_min_max_array[0][0])
        return len(self.channels_array[0])

    @property
    def total_samples(self):
        return self.total_frames

    @property
    def duration(self):
        return self.total_frames / self.frame_rate

    @property
    def compression_name(self):
        return self.__compression_name

    @property
    def compression_type(self):
        return self.__compression_type

    @property
    def frame_rate(self):
        return self.__frame_rate

    @frame_rate.setter
    def frame_rate(self, frame_rate: int):
        self.__frame_rate = frame_rate

    @property
    def bytes(self):
        return self.__bytes

    # dynamic getters

    # absolute values

    @property
    def array(self) -> INTS:
        if not self.__array:
            byte_converter = None
            if self.byte_converter:
                try:
                    self.byte_converter(self.bytes[0])
                    byte_converter = self.byte_converter
                except:
                    ...

            self.__array = [
                byte_converter(i) if byte_converter else i for i in self.__bytes
            ]
        return self.__array

    @property
    def channels_array(self) -> LIST_INTS:
        if not self.__channels_array:
            if self.channels == 1:
                self.__channels_array = [self.array]

            elif self.channels == 2:
                channel_1: INTS = []
                channel_2: INTS = []

                count, length = 0, len(self.array)
                while count < length:
                    channel_1.extend(self.array[count : count + 2])
                    count += 2
                    channel_2.extend(self.array[count : count + 2])
                    count += 2

                self.__channels_array = [channel_1, channel_2]

        return self.__channels_array

    @property
    def channels_peaks(self) -> INTS:
        return [max(channel) for channel in self.channels_array]

    @property
    def channels_min_max_array(self) -> list[LIST_INTS]:
        if not self.__channels_min_max_array:

            if self.channels == 1:
                self.__channels_min_max_array = [
                    [self.array[MIN_SLICE], self.array[MAX_SLICE]]
                ]

            elif self.channels == 2:
                channel_1: LIST_INTS = [
                    self.channels_array[0][MIN_SLICE],
                    self.channels_array[0][MAX_SLICE],
                ]
                channel_2: LIST_INTS = [
                    self.channels_array[1][MIN_SLICE],
                    self.channels_array[1][MAX_SLICE],
                ]

                self.__channels_min_max_array = [channel_1, channel_2]

        return self.__channels_min_max_array

    @property
    def channels_min_max_tupled_array(self) -> list[TUPLED_INTS]:
        if not self.__channels_min_max_tupled_array:

            if self.channels == 1:
                self.__channels_min_max_tupled_array = [
                    list(
                        zip(
                            self.array[MIN_SLICE],
                            self.array[MAX_SLICE],
                        ),
                    )
                ]

            elif self.channels == 2:
                channel_1: LIST_TUPLED_INTS = list(
                    zip(
                        self.__channels_array[0][MIN_SLICE],
                        self.__channels_array[0][MAX_SLICE],
                    )
                )

                channel_2: LIST_TUPLED_INTS = list(
                    zip(
                        self.__channels_array[1][MIN_SLICE],
                        self.__channels_array[1][MAX_SLICE],
                    )
                )

                self.__channels_min_max_tupled_array = [channel_1, channel_2]

        return self.__channels_min_max_tupled_array

    def channel_array(self, channel: int) -> INTS:
        self.check_channel(channel)
        return self.channels_array[channel - 1]

    def channel_min_max_array(self, channel: int) -> LIST_INTS:
        self.check_channel(channel)
        return self.channels_min_max_array[channel - 1]

    def channel_min_max_tupled_array(self, channel: int) -> LIST_TUPLED_INTS:
        self.check_channel(channel)
        return self.channels_min_max_tupled_array[channel - 1]

    def channel_min_array(self, channel: int) -> INTS:
        self.check_channel(channel)
        return self.channel_min_max_array(channel)[0]

    def channel_max_array(self, channel: int) -> INTS:
        self.check_channel(channel)
        return self.channel_min_max_array(channel)[1]

    def channel_min_tupled_array(self, channel: int) -> TUPLED_INTS:
        self.check_channel(channel)
        return self.channel_min_max_tupled_array(channel)[0]

    def channel_max_tupled_array(self, channel: int) -> TUPLED_INTS:
        self.check_channel(channel)
        return self.channel_min_max_tupled_array(channel)[1]

    # real array ranging from -128 to 127

    @property
    def real_array(self) -> INTS:
        if not self.__real_array:
            self.__real_array = [i - 128 for i in self.array]
        return self.__real_array

    @property
    def channels_real_array(self) -> LIST_INTS:
        if not self.__channels_real_array:

            if self.channels == 1:
                self.__channels_real_array = [self.real_array]

            elif self.channels == 2:
                channel_1: INTS = []
                channel_2: INTS = []

                count, length = 0, len(self.real_array)
                while count < length:
                    channel_1.extend(self.real_array[count : count + 2])
                    count += 2
                    channel_2.extend(self.real_array[count : count + 2])
                    count += 2

                self.__channels_real_array = [channel_1, channel_2]

        return self.__channels_real_array

    @property
    def channels_real_peaks(self) -> INTS:
        return [max(channel) for channel in self.channels_real_array]

    @property
    def channels_min_max_real_array(self) -> list[LIST_INTS]:
        if not self.__channels_min_max_real_array:

            if self.channels == 1:
                self.__channels_min_max_real_array = [
                    [self.real_array[MIN_SLICE], self.real_array[MAX_SLICE]]
                ]

            elif self.channels == 2:
                channel_1: LIST_INTS = [
                    self.channels_real_array[0][MIN_SLICE],
                    self.channels_real_array[0][MAX_SLICE],
                ]
                channel_2: LIST_INTS = [
                    self.channels_real_array[1][MIN_SLICE],
                    self.channels_real_array[1][MAX_SLICE],
                ]

                self.__channels_min_max_real_array = [channel_1, channel_2]

        return self.__channels_min_max_real_array

    @property
    def channels_min_max_tupled_real_array(self) -> list[TUPLED_INTS]:
        if not self.__channels_min_max_tupled_real_array:

            if self.channels == 1:
                self.__channels_min_max_tupled_real_array = [
                    list(
                        zip(
                            self.real_array[MIN_SLICE],
                            self.real_array[MAX_SLICE],
                        ),
                    )
                ]

            elif self.channels == 2:
                channel_1: LIST_TUPLED_INTS = list(
                    zip(
                        self.channels_real_array[0][MIN_SLICE],
                        self.channels_real_array[0][MAX_SLICE],
                    )
                )

                channel_2: LIST_TUPLED_INTS = list(
                    zip(
                        self.channels_real_array[1][MIN_SLICE],
                        self.channels_real_array[1][MAX_SLICE],
                    )
                )

                self.__channels_min_max_tupled_real_array = [channel_1, channel_2]

        return self.__channels_min_max_tupled_real_array

    def channel_real_array(self, channel: int) -> INTS:
        self.check_channel(channel)
        return self.channels_real_array[channel - 1]

    def channel_min_max_real_array(self, channel: int) -> LIST_INTS:
        self.check_channel(channel)
        return self.channels_min_max_real_array[channel - 1]

    def channel_min_max_tupled_real_array(self, channel: int) -> LIST_TUPLED_INTS:
        self.check_channel(channel)
        return self.channels_min_max_tupled_real_array[channel - 1]

    def channel_min_real_array(self, channel: int) -> INTS:
        self.check_channel(channel)
        return self.channel_min_max_real_array(channel)[0]

    def channel_max_real_array(self, channel: int) -> INTS:
        self.check_channel(channel)
        return self.channel_min_max_real_array(channel)[1]

    def channel_min_tupled_real_array(self, channel: int) -> TUPLED_INTS:
        self.check_channel(channel)
        return self.channel_min_max_tupled_real_array(channel)[0]

    def channel_max_tupled_real_array(self, channel: int) -> TUPLED_INTS:
        self.check_channel(channel)
        return self.channel_min_max_tupled_real_array(channel)[1]


class SamplingMethod(enum.Enum):
    Systematic = enum.auto()
    Cluster = enum.auto()


class AudioWaveChannel:
    def __init__(
        self,
        minimums: INTS = None,
        maximums: INTS = None,
        averages: INTS = None,
        averageDivisor: int = 1,
    ):
        self.minimums = minimums or []
        self.maximums = maximums or []
        self._averages = averages or []
        self.min: int = 0
        self.max: int = 0
        assert averageDivisor, "averageDivisor is a non-zero integer"
        self.averageDivisor = averageDivisor

    @property
    def averages(self):
        if (self.minimums or self.maximums) and not self._averages:
            for min, max in zip(self.minimums, self.maximums):
                # print(min, max)
                avg = abs(min) + abs(max)
                self._averages.append(avg / self.averageDivisor)

        return self._averages

    def setMinimums(self, minimums: INTS) -> bool:
        if minimums != self.minimums:
            self._averages.clear()
            self.minimums = minimums
            return True

    def setMaximums(self, maximums: INTS) -> bool:
        if maximums != self.maximums:
            self._averages.clear()
            self.maximums = maximums
            return True

    def setAverages(self, averages: INTS) -> bool:
        if averages != self.averages:
            self._averages.clear()
            self._averages = averages
            return True

    def setMinMax(self, minimums: INTS, maximums: INTS) -> bool:
        min = self.setMinimums(minimums)
        max = self.setMaximums(maximums)
        return min or max

    def hasData(self) -> bool:
        return bool(self.minimums) or bool(self.maximums) or bool(self.averages)

    def systematicSample(self, array: INTS, width: int) -> INTS:
        slicer = len(array) // width
        return array[::slicer]

    def clusterSample(self, array: INTS, width: int) -> INTS:
        lastSamples = 0
        nextSamples = width
        samples = []

        while True:
            cluster = array[lastSamples:nextSamples]

            lastSamples += width
            nextSamples += width

            if cluster:
                pixel = sum(cluster) // width
                samples.append(pixel)

            else:
                break

        return samples

    def sample(
        self,
        array: INTS,
        width: int,
        method: SamplingMethod = SamplingMethod.Systematic,
    ):
        if method == SamplingMethod.Systematic:
            return self.systematicSample(array, width)
        else:
            return self.clusterSample(array, width)

    def averageSample(self, array: INTS, width: int):
        slicer = len(array) // width
        return array[::slicer]

    def scale(self, array: INTS, height: int):
        min_ = self.min or min(array)
        max_ = self.max or max(array)
        scaledArray: INTS_FLOATS = []
        for point in array:
            referencePoint = min_ if point < 0 else max_
            scale_factor = height / referencePoint
            scaled_point = point * scale_factor
            scaledArray.append(scaled_point)
        return scaledArray

    def sampleMinimums(
        self,
        samples: int,
        scale: int = 0,
        method: SamplingMethod = SamplingMethod.Systematic,
    ):
        samples = self.sample(self.minimums, samples, method=method)
        if scale:
            samples = self.scale(samples, scale)
        return samples

    def sampleMaximums(
        self,
        samples: int,
        scale: int = 0,
        method: SamplingMethod = SamplingMethod.Systematic,
    ):
        samples = self.sample(self.maximums, samples, method=method)
        if scale:
            samples = self.scale(samples, scale)
        return samples

    def sampleAverages(
        self,
        samples: int,
        scale: int = 0,
        method: SamplingMethod = SamplingMethod.Systematic,
    ):
        samples = self.sample(self.averages, samples, method=method)
        if scale:
            samples = self.scale(samples, scale)
        return samples

    def setBytes(self, bytes: bytes):
        array = [i for i in bytes]
        self.minimums = array[MIN_SLICE]
        self.maximums = array[MAX_SLICE]

    @classmethod
    def from_bytes(cls, bytes: bytes, *args, **kwargs):
        array = [i for i in bytes]
        return cls(array[MIN_SLICE], array[MAX_SLICE], *args, **kwargs)


if __name__ == "__main__":

    wavs = "test.wav", "test_mono.wav", "test_stereo.wav"

    aw = AudioWave(f"assets/{wavs[1]}")
    # print(aw.channels)
    # print(aw.array[:20])
    # print(aw.bits)
    # print(aw.channels_real_array[0][:10])
    # print(aw.scaled(aw.channels_array[0][:10], 80))

    print(len(aw.channel_array(1)))

    # print(aw.channels_min_max_array[0][0][:10], aw.channels_min_max_array[0][1][:10])
    # print(
    #     aw.channels_min_max_tupled_array[0][:10],
    # )

    # print()
    # # print(min(aw.array))

    # aw = AudioWave(f"../assets/{wavs[2]}")
    # print(aw.channels)
    # print(aw.array[:40])
    # print(aw.channels_array[0][:10], aw.channels_array[1][:10])
    # print(aw.channels_min_max_array[0][0][:10], aw.channels_min_max_array[0][1][:10])
    # print(aw.channels_min_max_array[1][0][:10], aw.channels_min_max_array[1][1][:10])

    # print()
    # print(min(aw.array))
