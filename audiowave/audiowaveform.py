import enum, math, typing
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import QWidget, QFrame
from audiowave import *


class AudioWaveFormGravity(enum.Enum):
    Average = enum.auto()
    Min_Max = enum.auto()
    Max_Min = Min_Max
    Min = enum.auto()
    Max = enum.auto()


COLORS = typing.Union[Qt.GlobalColor, QColor]


class AudioWaveFormOptions:
    def __init__(
        self,
        visible: bool = True,
        background: COLORS = Qt.white,
        pixelSpacing: int = 1,
        pixelWidth: int = 2,
        zoom: float = 1,
        scale: int = 0,
        avgColor: COLORS = Qt.blue,
        minColor: COLORS = Qt.blue,
        maxColor: COLORS = Qt.blue,
        radius: int = 0,
        grid: int = 0,
        emptyPixelHeight: int = 2,
        showHLine: bool = False,
        gridColor: COLORS = Qt.white,
        seekColor: COLORS = None,
        seekerColor: COLORS = Qt.transparent,
        seekerRadius: int = 5,
        gravity: AudioWaveFormGravity = AudioWaveFormGravity.Min_Max,
    ):
        self.visible = visible
        self.background = background
        self.pixelSpacing = pixelSpacing
        self.pixelWidth = pixelWidth
        self.avgColor = avgColor
        self.showHLine = showHLine
        self.minColor = minColor
        self.zoom = zoom
        self.scale = scale
        self.maxColor = maxColor
        self.gravity = gravity
        self.radius = radius
        self.emptyPixelHeight = emptyPixelHeight
        self.grid = grid
        self.gridColor = gridColor
        self.seekColor = seekColor
        self.seekerColor = seekerColor
        self.seekerRadius = seekerRadius

        self.channel: AudioWaveFormChannel = None

    def offset(self):
        return self.pixelWidth + self.pixelSpacing

    def pixelsPerWidth(self, width: int):
        return width // self.offset()

    def updateChannel(self):
        if self.channel:
            self.channel.updateWaveForm()

    def setVisible(self, visible: bool) -> None:
        if visible != self.visible:
            self.visible = visible
            self.updateChannel()

    def setBackground(self, background: COLORS) -> None:
        if background != self.background:
            self.background = background
            self.updateChannel()

    def setEmptyPixelHeight(self, emptyPixelHeight: int) -> None:
        if emptyPixelHeight != self.emptyPixelHeight:
            self.emptyPixelHeight = emptyPixelHeight
            self.updateChannel()

    def setPixelSpacing(self, pixelSpacing: int) -> None:
        if pixelSpacing != self.pixelSpacing:
            self.pixelSpacing = pixelSpacing
            self.updateChannel()

    def setPixelWidth(self, pixelWidth: int) -> None:
        if pixelWidth != self.pixelWidth:
            self.pixelWidth = pixelWidth
            self.updateChannel()

    def setScale(self, scale: int):
        if scale != self.scale:
            self.scale = scale
            self.updateChannel()

    def setZoom(self, zoom: int):
        if zoom != self.zoom:
            self.zoom = zoom
            self.updateChannel()

    def setAvgColor(self, avgColor: COLORS) -> None:
        if avgColor != self.avgColor:
            self.avgColor = avgColor
            self.updateChannel()

    def setShowHLine(self, showHLine: bool) -> None:
        if showHLine != self.showHLine:
            self.showHLine = showHLine
            self.updateChannel()

    def setMinColor(self, minColor: COLORS) -> None:
        if minColor != self.minColor:
            self.minColor = minColor
            self.updateChannel()

    def setMaxColor(self, maxColor: COLORS) -> None:
        if maxColor != self.maxColor:
            self.maxColor = maxColor
            self.updateChannel()

    def setGravity(self, gravity: int) -> None:
        if gravity != self.gravity:
            self.gravity = gravity
            self.updateChannel()

    def setRadius(self, radius: int) -> None:
        if radius != self.radius:
            self.radius = radius
            self.updateChannel()

    def setGrid(self, grid: int) -> None:
        if grid != self.grid:
            self.grid = grid
            self.updateChannel()

    def setGridColor(self, gridColor: COLORS) -> None:
        if gridColor != self.gridColor:
            self.gridColor = gridColor
            self.updateChannel()

    def setSeekColor(self, seekColor: COLORS) -> None:
        if seekColor != self.seekColor:
            self.seekColor = seekColor
            self.updateChannel()

    def setSeekerColor(self, seekerColor: COLORS) -> None:
        if seekerColor != self.seekerColor:
            self.seekerColor = seekerColor
            self.updateChannel()

    def setSeekerRadius(self, seekerRadius: int) -> None:
        if seekerRadius != self.seekerRadius:
            self.seekerRadius = seekerRadius
            self.updateChannel()


DEFAULT_WAVEFORM_OPTIONS = AudioWaveFormOptions()


class AudioWaveFormChannel(AudioWaveChannel):
    def __init__(self, *args, options: AudioWaveFormOptions = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.options: AudioWaveFormOptions = None
        self.waveForm: AudioWaveForm = None
        self.setOptions(options)

    def setWaveForm(self, waveForm: "AudioWaveForm"):
        self.waveForm = waveForm

    def setOptions(self, options: AudioWaveFormOptions):
        self.options = options or DEFAULT_WAVEFORM_OPTIONS
        self.options.channel = self
        self.updateWaveForm()

    def setMinimums(self, minimums: INTS, up=True):
        if super().setMinimums(minimums) and up:
            self.updateWaveForm()

    def setMaximums(self, maximums: INTS, up=True):
        if super().setMaximums(maximums) and up:
            self.updateWaveForm()

    def setAverages(self, averages: INTS, up=True):
        if super().setAverages(averages) and up:
            self.updateWaveForm()

    def setMinMax(self, minimums: INTS, maximums: INTS, up=True):
        if super().setMinMax(minimums, maximums) and up:
            self.updateWaveForm()

    @classmethod
    def from_bytes(cls, bytes: bytes, options: AudioWaveFormOptions):
        return super().from_bytes(bytes, options=options)

    def updateWaveForm(self):
        if self.waveForm:
            self.waveForm.update()

    def setBytes(self, bytes: bytes):
        super().setBytes(bytes)
        self.updateWaveForm()


class RoundedPolygon(QPolygon):
    def __init__(self, radius: int):
        super().__init__()

        self.radius = radius

    def distance(self, p1: QPoint, p2: QPoint):
        d = (p1.x() - p2.x()) ** 2 + (p1.y() - p2.y()) ** 2
        return math.sqrt(d)

    def line(self, i: int):
        pt = QPointF()
        pt1 = self.at(i)
        pt2 = self.at((i + 1) % self.count())
        d = self.distance(pt1, pt2)
        if not d:
            d = 1
        rat = self.radius / d
        if rat > 0.5:
            rat = 0.5
        return pt, pt1, pt2, rat

    def line_start(self, i: int) -> QPointF:
        pt, pt1, pt2, rat = self.line(i)
        pt.setX((1.0 - rat) * pt1.x() + rat * pt2.x())
        pt.setY((1.0 - rat) * pt1.y() + rat * pt2.y())
        return pt

    def line_end(self, i: int) -> QPointF:
        pt, pt1, pt2, rat = self.line(i)
        pt.setX(rat * pt1.x() + (1.0 - rat) * pt2.x())
        pt.setY(rat * pt1.y() + (1.0 - rat) * pt2.y())
        return pt

    def path(self):
        path = QPainterPath()
        pt1 = QPointF()
        pt2 = QPointF()
        for i in range(self.count()):
            pt1 = self.line_start(i)
            if i == 0:
                path.moveTo(pt1)
            else:
                path.quadTo(self.at(i), pt1)
            pt2 = self.line_end(i)
            path.lineTo(pt2)
        pt1 = self.line_start(0)
        path.quadTo(self.at(0), pt1)
        return path

    @classmethod
    def get_path(cls, radius: int, rect: typing.Union[QRect, QRectF]):
        point = lambda p: p.toPoint() if isinstance(p, QPointF) else p

        poly = cls(radius)
        (
            poly
            << point(rect.topLeft())
            << point(rect.topRight())
            << point(rect.bottomRight())
            << point(rect.bottomLeft())
        )
        return poly.path()


DEFAULT_MARGINS = QMargins(0, 0, 0, 0)


class AudioWaveForm(QFrame):
    seeked = Signal(float)

    def __init__(
        self,
        waveFormChannel1: AudioWaveFormChannel = None,
        waveFormChannel2: AudioWaveFormChannel = None,
        margins: QMargins = None,
        backgroundColor: COLORS = Qt.white,
        backgroundRadius: int = 5,
        channelsPixelSpacing: int = 5,
        showHLine: bool = False,
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self.margins = margins or DEFAULT_MARGINS
        self.backgroundColor = backgroundColor
        self.backgroundRadius = backgroundRadius
        self.channelsPixelSpacing = channelsPixelSpacing
        self.showHLine = showHLine
        self.waveFormChannel1: AudioWaveFormChannel = None
        self.waveFormChannel2: AudioWaveFormChannel = None

        self.setChannel1(waveFormChannel1)
        self.setChannel2(waveFormChannel2)

        self.seekRatio: float = 0

        self.setAttribute(Qt.WA_Hover, True)

    def event(self, event: QEvent) -> bool:
        if isinstance(event, QHoverEvent):
            if self.waveFormChannel1:
                rect = self.seekerRect(
                    self.waveFormMidline.y1(),
                    self.waveFormChannel1.options.seekerRadius,
                )
                if rect.contains(event.pos()):
                    cursor = Qt.PointingHandCursor
                else:
                    cursor = Qt.ArrowCursor

                self.setCursor(cursor)

        return super().event(event)

    @property
    def seekX(self):
        return self.seekRatio * self.waveFormRect().width()

    def setChannel1(self, waveFormChannel1: AudioWaveFormChannel):
        if waveFormChannel1:
            self.waveFormChannel1 = waveFormChannel1
            self.waveFormChannel1.setWaveForm(self)

        if self.isVisible():
            self.update()

    def setChannel2(self, waveFormChannel2: AudioWaveFormChannel):
        if waveFormChannel2:
            self.waveFormChannel2 = waveFormChannel2
            self.waveFormChannel2.setWaveForm(self)

        if self.isVisible():
            self.update()

    def isChannel1(self):
        res = False
        if self.waveFormChannel1 and self.waveFormChannel1.hasData():
            if self.waveFormChannel1.options.visible:
                res = True
        return res

    def isChannel2(self):
        res = False
        if self.waveFormChannel2 and self.waveFormChannel2.hasData():
            if self.waveFormChannel2.options.visible:
                res = True
        return res

    def isBothChannels(self):
        return self.isChannel1() and self.isChannel2()

    def roundRectPath(self, rect: QRectF, radius: int) -> QPainterPath:
        return RoundedPolygon.get_path(radius, rect)

    def waveFormRect(self):
        return self.rect().marginsRemoved(self.margins)

    def waveFormChannel1Rect(self):
        channel_rect = QRect(self.waveFormRect())
        channel_rect.setHeight(channel_rect.height() // 2)

        return channel_rect.marginsRemoved(QMargins(0, 0, 0, self.channelsPixelSpacing))

    def waveFormChannel2Rect(self):

        waveFormChannel2_rect = QRect(self.waveFormChannel1Rect())
        waveFormChannel2_rect.moveTop(
            self.waveFormMidline.y1() + self.channelsPixelSpacing
        )
        return waveFormChannel2_rect

    @property
    def waveFormMidlineY(self):
        return self.margins.top() + (self.waveFormRect().height() // 2)

    @property
    def waveFormMidline(self) -> QLine:
        waveFormRect = self.waveFormRect()
        waveFormMidlineY = self.waveFormMidlineY
        waveFormMidlineP1 = QPoint(waveFormRect.left(), waveFormMidlineY)
        waveFormMidlineP2 = QPoint(waveFormRect.right(), waveFormMidlineY)
        waveFormMidline = QLine(waveFormMidlineP1, waveFormMidlineP2)
        return waveFormMidline

    def xRatio(self, x: int):
        ratio = x / self.waveFormRect().width()
        return ratio

    def setSeekRatio(self, seekRatio: float):
        if seekRatio != self.seekRatio:
            self.seekRatio = seekRatio
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setSeekRatio(self.xRatio(event.x()))
        self.seeked.emit(self.seekRatio)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.mousePressEvent(event)

    def get_seekColor(self, x: int, color: COLORS, seekColor: COLORS) -> COLORS:
        if self.seekRatio > self.xRatio(x):
            return seekColor or color
        return color

    def paintGrid(
        self,
        painter: QPainter,
        midline: int,
        top: int,
        bottom: int,
        grid: int,
        gridColor: COLORS,
    ):
        pen = painter.pen()
        painter.setPen(gridColor)
        rect = self.rect()
        left, right = rect.left(), rect.right()

        draw = lambda y: painter.drawLine(left, y, right, y)

        y1 = y2 = midline
        while y1 > top or y2 < bottom:
            y1 -= grid
            y2 += grid
            draw(y1)
            draw(y2)

        painter.setPen(pen)

    def seekerRect(self, midline: int, seekerRadius: int) -> QRectF:
        rect = QRectF()
        if seekerRadius:
            seekX = self.seekX
            waveFormRect = self.waveFormRect()

            if seekX < waveFormRect.left():
                seekX = waveFormRect.left()
            elif seekX > waveFormRect.right():
                seekX = waveFormRect.right()

            half_seekerRadius = seekerRadius / 2
            y = midline - half_seekerRadius

            rect = QRectF(
                seekX - half_seekerRadius,
                y,
                seekerRadius,
                seekerRadius,
            )
        return rect

    def paintSeekBar(
        self,
        painter: QPainter,
        channel: AudioWaveFormChannel,
        midline: int,
        scale: int,
    ):
        if (seekerRadius := channel.options.seekerRadius) and (
            seekerColor := channel.options.seekerColor
        ):
            half_scale = scale / 2
            if seekerRadius > half_scale:
                seekerRadius = half_scale

            rect = self.seekerRect(midline, seekerRadius)
            path = self.roundRectPath(rect, rect.width() / 2)
            painter.fillPath(path, QColor(seekerColor))

    def paintWaveFormSample(
        self,
        painter: QPainter,
        channel: AudioWaveFormChannel,
        rect: typing.Union[QRect, QRectF],
        color: COLORS,
        y: int = 0,
        half_y: int = 0,
    ):
        seekColor = channel.options.seekColor
        color = self.get_seekColor(rect.x(), color, seekColor)
        path = self.roundRectPath(rect, channel.options.radius)
        painter.fillPath(path, QColor(color))

        if y and half_y:
            painter.fillRect(rect.x(), y, rect.width(), half_y, color)

    def paintAverage(
        self,
        painter: QPainter,
        channel: AudioWaveFormChannel,
        scale: int,
        top: int,
        pixels: int,
    ):
        averages = channel.sampleAverages(pixels, scale)
        avgColor = channel.options.avgColor
        x = self.waveFormRect().left()
        offset = channel.options.offset()
        pixelWidth = channel.options.pixelWidth
        emptyPixelHeight = channel.options.emptyPixelHeight
        zoom = channel.options.zoom

        for avg in averages:
            avg = avg or emptyPixelHeight
            avg *= zoom
            avg_rect = QRectF(x, top + (scale - avg) // 2, pixelWidth, avg)
            self.paintWaveFormSample(
                painter=painter, channel=channel, rect=avg_rect, color=avgColor
            )
            x += offset

    def paintMin_Max(
        self,
        painter: QPainter,
        channel: AudioWaveFormChannel,
        scale: int,
        top: int,
        pixels: int,
        midline: int,
    ):
        scale //= 2
        maximums = channel.sampleMaximums(pixels, scale)
        waveFormRect = self.waveFormRect()
        left = waveFormRect.left()

        x = left
        offset = channel.options.offset()
        pixelWidth = channel.options.pixelWidth
        emptyPixelHeight = channel.options.emptyPixelHeight
        maxColor = channel.options.maxColor
        zoom = channel.options.zoom

        for max in maximums:
            max = max or emptyPixelHeight
            max *= zoom
            y = top + scale - max
            half_max = max // 2
            max_rect = QRectF(x, y, pixelWidth, max)
            self.paintWaveFormSample(
                painter=painter,
                channel=channel,
                rect=max_rect,
                color=maxColor,
                y=max_rect.bottom() - half_max,
                half_y=half_max,
            )
            x += offset

        minimums = channel.sampleMinimums(pixels, scale)
        minColor = channel.options.minColor

        x = left
        for min in minimums:
            min = min or emptyPixelHeight
            min *= zoom
            y = midline
            min_rect = QRectF(x, y, pixelWidth, min)
            self.paintWaveFormSample(
                painter=painter,
                channel=channel,
                rect=min_rect,
                color=minColor,
                y=y,
                half_y=min // 2,
            )
            x += offset

    def paintMinMax(
        self,
        painter: QPainter,
        channel: AudioWaveFormChannel,
        scale: int,
        top: int,
        pixels: int,
    ):
        isMax = channel.options.gravity == AudioWaveFormGravity.Max
        if isMax:
            points = channel.sampleMaximums(pixels, scale)
            pointColor = channel.options.maxColor
        else:
            points = channel.sampleMinimums(pixels, scale)
            pointColor = channel.options.minColor
        x = self.waveFormRect().left()

        offset = channel.options.offset()
        pixelWidth = channel.options.pixelWidth
        emptyPixelHeight = channel.options.emptyPixelHeight
        zoom = channel.options.zoom

        for point in points:
            point = point or emptyPixelHeight
            point *= zoom
            y = top
            half_point = point // 2
            if isMax:
                y += scale - point
            point_rect = QRectF(x, y, pixelWidth, point)

            if isMax:
                y = point_rect.bottom() - half_point

            self.paintWaveFormSample(
                painter=painter,
                channel=channel,
                rect=point_rect,
                color=pointColor,
                y=y,
                half_y=half_point,
            )

            x += offset

    def paintChannel(
        self,
        painter: QPainter,
        channel: AudioWaveFormChannel,
        top: int,
        bottom: int,
        scale: int,
        midline: int,
    ):
        if not channel.hasData():
            return

        waveFormRect = self.waveFormRect()
        sampled_waveForm_width = waveFormRect.width() - 1
        pixels = channel.options.pixelsPerWidth(sampled_waveForm_width)

        if channel.options.showHLine:
            painter.drawLine(waveFormRect.x(), midline, waveFormRect.width(), midline)

        if channel.options.gravity == AudioWaveFormGravity.Average:
            self.paintAverage(
                painter=painter, channel=channel, scale=scale, top=top, pixels=pixels
            )

        elif channel.options.gravity == AudioWaveFormGravity.Min_Max:
            self.paintMin_Max(
                painter=painter,
                channel=channel,
                scale=scale,
                top=top,
                pixels=pixels,
                midline=midline,
            )

        elif channel.options.gravity in [
            AudioWaveFormGravity.Max,
            AudioWaveFormGravity.Min,
        ]:
            self.paintMinMax(
                painter=painter, channel=channel, scale=scale, top=top, pixels=pixels
            )

        if grid := channel.options.grid:

            self.paintGrid(
                painter=painter,
                midline=self.waveFormMidlineY,
                top=top,
                bottom=bottom,
                grid=grid,
                gridColor=channel.options.gridColor,
            )

        self.paintSeekBar(
            painter=painter, channel=channel, midline=midline, scale=scale
        )

    def paintEvent(self, _: QPaintEvent) -> None:
        painter = QPainter(self)

        rect = self.rect()
        # waveForm rectangle
        waveFormRect = self.waveFormRect()
        point_path = self.roundRectPath(waveFormRect, self.backgroundRadius)
        painter.fillPath(point_path, QColor(self.backgroundColor))

        # waveForm mid line
        waveFormMidline = self.waveFormMidline
        waveFormMidlineY = waveFormMidline.y1()

        # painter.drawRect(waveFormRect)
        # painter.drawLine(waveFormMidline)
        try:
            if self.isBothChannels():

                waveFormChannel1_rect = self.waveFormChannel1Rect()
                waveFormChannel2_rect = self.waveFormChannel2Rect()

                for channel_rect, channel in zip(
                    [waveFormChannel1_rect, waveFormChannel2_rect],
                    [self.waveFormChannel1, self.waveFormChannel2],
                ):
                    painter.fillRect(channel_rect, channel.options.background)

                    self.paintChannel(
                        painter=painter,
                        channel=channel,
                        scale=channel_rect.height(),
                        top=channel_rect.top(),
                        bottom=channel_rect.bottom(),
                        midline=channel_rect.center().y(),
                    )

            elif self.isChannel1() or self.isChannel2():
                top = waveFormRect.top()
                bottom = waveFormRect.bottom()
                scale = waveFormRect.height()
                channel = (
                    self.waveFormChannel1
                    if self.isChannel1()
                    else self.waveFormChannel2
                )
                self.paintChannel(
                    painter=painter,
                    channel=channel,
                    scale=scale,
                    top=top,
                    bottom=bottom,
                    midline=waveFormMidlineY,
                )
        except Exception as e:
            print(e)

        finally:
            painter.end()


# ----------------------LIVE--------------------------------------


class LiveAudioWaveFormChannel(AudioWaveChannel, QObject):

    currentPixelChanged = Signal(int)
    startedSignal = Signal()
    stoppedSignal = Signal()

    def __init__(
        self,
        samplesPerPixel: int = 1000,
        preOffset: bool = True,
        interval: int = 100,
        pauseOnEnd: bool = True,
        **kwargs,
    ):
        AudioWaveChannel.__init__(self, **kwargs)
        QObject.__init__(self)

        self.waveform_minimums: INTS = []
        self.waveform_maximums: INTS = []

        self.preOffset: bool = preOffset
        self.pauseOnEnd: bool = pauseOnEnd
        self.interval: int = 0
        self.samplesPerPixel: int = 0
        self.visiblePixels: int = 0
        self.waveFormChannel: AudioWaveFormChannel = None

        self.currentPixel = 0

        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.updateCurrentPixel)

        self.syncedIntervalAndSamplesPerPixelWithDuration = False

        self.setInterval(interval)
        self.setSamplesPerPixel(samplesPerPixel)

    def setInterval(self, interval: int):
        interval = int(interval)
        if interval and interval != self.interval:
            self.interval = interval
            self.updateTimer.setInterval(self.interval)

    def setSamplesPerPixel(self, samplesPerPixel: int):
        samplesPerPixel = int(samplesPerPixel)
        if samplesPerPixel and samplesPerPixel != self.samplesPerPixel:
            self.samplesPerPixel = samplesPerPixel
            self.processWaveForm()

    def setWaveFormChannel(self, waveFormChannel: AudioWaveFormChannel):
        self.waveFormChannel = waveFormChannel

    def setVisiblePixels(self, width: int):
        if self.waveFormChannel:
            self.visiblePixels = self.waveFormChannel.options.pixelsPerWidth(width)

    def processWaveForm(self):
        if not (self.minimums and self.maximums and self.waveFormChannel):
            return

        self.waveform_minimums = self.sampleMinimums(
            self.samplesPerPixel, method=SamplingMethod.Cluster
        )
        self.waveform_maximums = self.sampleMaximums(
            self.samplesPerPixel, method=SamplingMethod.Cluster
        )

        self.waveFormChannel.min = min(self.waveform_minimums)
        self.waveFormChannel.max = min(self.waveform_maximums)

    def patchPixels(self, pixels: INTS, before: bool = 1):
        remaining = self.visiblePixels - len(pixels)
        empty = None
        empty = 0

        if remaining > 0:
            for _ in range(remaining):
                if not before:
                    pixels.append(empty)
                else:
                    pixels.insert(0, empty)

    def stop(self):
        self.updateTimer.stop()
        self.stoppedSignal.emit()

    def reset(self):
        self.currentPixel = 0

    def getPixels(self, array: INTS) -> INTS:
        totalArray = len(array)

        if self.preOffset:
            pixels = array[: self.currentPixel]
            before = 1
            if self.currentPixel > totalArray:
                before = 0
                if not self.pauseOnEnd:
                    pixels += [0 for _ in range(self.currentPixel - totalArray)]

            if len(pixels) > self.visiblePixels:
                pixels = pixels[-self.visiblePixels :]
                before = 0

        else:
            pixels = array[self.currentPixel :]
            before = 0

        # print(len(pixels), end=', ')
        self.patchPixels(pixels, before)
        # print(len(pixels))
        return pixels

    def updateCurrentPixel(self):
        if not (self.waveform_minimums and self.waveform_maximums):
            self.processWaveForm()

        min_pixels = self.getPixels(self.waveform_minimums)
        max_pixels = self.getPixels(self.waveform_maximums)

        if self.waveFormChannel:
            self.waveFormChannel.setMinMax(min_pixels, max_pixels)

        self.currentPixelChanged.emit(self.currentPixel)
        self.currentPixel += 1

        if self.pauseOnEnd and self.currentPixel > len(self.waveform_maximums):
            self.stop()

    def start(self):
        if self.waveFormChannel:
            self.updateTimer.start()
            self.startedSignal.emit()

    def syncIntervalAndSamplesPerPixelWithDuration(self, duration: int):
        if self.syncedIntervalAndSamplesPerPixelWithDuration:
            return
        assert len(self.minimums) == len(self.maximums)
        self.syncedIntervalAndSamplesPerPixelWithDuration = True

        totalSamples = len(self.minimums)
        samplesPerPixel = self.samplesPerPixel
        samplesPerPixel = (self.interval * totalSamples) / (duration * 1000)
        self.setSamplesPerPixel(samplesPerPixel)

        updateInterval = samplesPerPixel * duration * 1000 / totalSamples
        self.setInterval(updateInterval - 14)

        updateInterval = self.interval
        print(f"{totalSamples=}, {duration=}, {samplesPerPixel=}, {updateInterval=}")


class LiveAudioWaveForm(AudioWaveForm):
    def __init__(
        self,
        liveWaveFormChannel1: AudioWaveChannel = None,
        liveWaveFormChannel2: AudioWaveChannel = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self.liveWaveFormChannel1: LiveAudioWaveFormChannel = None
        self.liveWaveFormChannel2: LiveAudioWaveFormChannel = None

        self.setLiveChannel1(liveWaveFormChannel1)
        self.setLiveChannel2(liveWaveFormChannel2)

    def setLiveChannel1(self, liveWaveFormChannel1: LiveAudioWaveFormChannel):
        if liveWaveFormChannel1:
            self.liveWaveFormChannel1 = liveWaveFormChannel1
            self.liveWaveFormChannel1.setWaveFormChannel(self.waveFormChannel1)

        if self.isVisible():
            self.update()

    def setLiveChannel2(self, liveWaveFormChannel2: LiveAudioWaveFormChannel):
        if liveWaveFormChannel2:
            self.liveWaveFormChannel2 = liveWaveFormChannel2
            self.liveWaveFormChannel2.setWaveFormChannel(self.waveFormChannel2)

        if self.isVisible():
            self.update()

    def setVisiblePixels(self):
        width = (
            self.waveFormRect().width()
            if not self.isBothChannels()
            else self.waveFormChannel1Rect().width()
        )
        if self.liveWaveFormChannel1:
            self.liveWaveFormChannel1.setVisiblePixels(width)
        if self.liveWaveFormChannel2:
            self.liveWaveFormChannel2.setVisiblePixels(width)

    def startWaveForm(self):
        self.setVisiblePixels()
        w = self.width()
        self.setMinimumWidth(w)
        self.setMaximumWidth(w)

        if self.liveWaveFormChannel1:
            self.liveWaveFormChannel1.start()
        if self.liveWaveFormChannel2:
            self.liveWaveFormChannel2.start()

    def resetWaveForm(self):
        if self.liveWaveFormChannel1:
            self.liveWaveFormChannel1.reset()
        if self.liveWaveFormChannel2:
            self.liveWaveFormChannel2.reset()

    def stopWaveForm(self):
        if self.liveWaveFormChannel1:
            self.liveWaveFormChannel1.stop()
        if self.liveWaveFormChannel2:
            self.liveWaveFormChannel2.stop()


class FixedLiveAudioWaveForm(AudioWaveForm):
    def __init__(self, seconds: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.seconds: float = 0
        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.updateSeekRatio)

        self.interval: float = 0
        self.current: int = 0
        self.total: int = 0

        self.setSeconds(seconds)

    def setSeconds(self, seconds: int):
        if seconds != self.seconds:
            self.seconds = seconds
            seconds *= 1000

            channel = self.waveFormChannel1
            waveFormRect = self.waveFormRect()
            pixels = channel.options.pixelsPerWidth(waveFormRect.width() - 1)

            self.total = pixels
            self.interval = seconds / pixels

            self.updateTimer.setInterval(self.interval - 13)

    def updateSeekRatio(self):
        if self.current > self.total:
            self.stopWaveForm()
            return

        self.setSeekRatio(self.current / self.total)
        self.current += 1

    def startWaveForm(self):
        self.updateTimer.start()

    def resetWaveForm(self):
        self.current = 0

    def stopWaveForm(self):
        self.updateTimer.stop()
