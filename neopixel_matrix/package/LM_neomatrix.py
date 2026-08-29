from neopixel import NeoPixel
from machine import Pin

from microIO import bind_pin, pinmap_search
from Types import resolve
from Common import manage_task, AnimationPlayer, data_dir, web_endpoint

from neopixel_matrix.effects import make_context, noise_gen, rainbow_gen, snake_gen, spiral_gen
from neopixel_matrix.file_player import file_frame_gen, valid_file_name


class NeoPixelMatrix(AnimationPlayer):
    INSTANCE = None
    DEFAULT_COLOR = (100, 23, 0)  # Default color for the matrix
    DEFAULT_BRIGHTNESS = 20

    def __init__(self, width: int = 8, height: int = 8, pin: int = 0):
        super().__init__(tag="neomatrix")
        self.width = width
        self.height = height
        self.num_pixels = width * height
        self.pixels = NeoPixel(Pin(pin, Pin.OUT), self.num_pixels)
        self._color_buffer = [(0, 0, 0)] * self.num_pixels      # Store original RGB values
        self._brightness = NeoPixelMatrix.DEFAULT_BRIGHTNESS / 100.0
        NeoPixelMatrix.INSTANCE = self

    def update(self, *data):
        # Animation player will call this method to update pixels.
        if len(data) == 1:
            self._set_colormap(data[0])
            return
        x, y, color = data
        self.set_pixel(x, y, color)

    def draw(self):
        # Animation player will call this method to update the display.
        self.pixels.write()

    def clear(self):
        # Animation player will call this method to clear the display.
        for i in range(self.num_pixels):
            # Write pixel buffer before write to ws2812
            self.pixels[i] = (0, 0, 0)
            self._color_buffer[i] = (0, 0, 0)
        # Send buffer to device
        self.draw()

    def _coord_to_index(self, x: int, y: int, zigzag:bool=True):
        """
        Zigzag layout: even rows left-to-right, odd rows right-to-left
        """
        if zigzag is None or zigzag:
            if y % 2 == 0:
                return y * self.width + x
            return y * self.width + (self.width - 1 - x)
        return y * self.width + x

    def _index_to_coord(self, index: int, zigzag:bool=True) -> tuple[int, int]:
        """
        Converts a linear index to (x, y) coordinates.
        Zigzag layout: even rows left-to-right, odd rows right-to-left.
        """
        y = index // self.width
        x = index % self.width
        if (zigzag is None or zigzag) and y % 2 == 1:
            x = self.width - 1 - x
        return x, y

    def _rgb_to_grb_with_br(self, color: tuple[int, int, int]):
        """
        Converts RGB to GRB with brightness adjustment.
        """
        def _scale(val):
            return max(0, min(255, int(val * self._brightness)))

        return _scale(color[1]), _scale(color[0]), _scale(color[2])

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int], zigzag:bool=True):
        """
        Set pixel at (x, y) with RGB
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            index = self._coord_to_index(x, y, zigzag=zigzag)
            self._color_buffer[index] = color  # store original RGB for brightness control
            self.pixels[index] = self._rgb_to_grb_with_br(color)

    def color(self, color: tuple[int, int, int]):
        """
        Fill color OR Animation color change.
        :param color: tuple[int, int, int] range: 0-255
        :return: str
        """
        r, g, b = max(0, min(color[0], 255)), max(0, min(color[1], 255)), max(0, min(color[2], 255))
        color = (r, g, b)
        NeoPixelMatrix.DEFAULT_COLOR = color
        if manage_task(self._task_tag, "isbusy"):
            return f"Set animation color to {color}"
        for i in range(self.num_pixels):
            self._color_buffer[i] = color
            # Write pixel buffer before write to ws2812
            self.pixels[i] = self._rgb_to_grb_with_br(color)
        # Send buffer to device
        self.draw()
        return f"Set all pixels to {color}"

    def brightness(self, br: int):
        """
        Change the brightness of all pixels.
        """
        br = max(0, min(br, 100))  # clamp brightness to 0–100%
        self._brightness = br / 100.0
        # Set color matrix brightness
        for i, color in enumerate(self._color_buffer):
            # Write pixel buffer before write to ws2812
            self.pixels[i] = self._rgb_to_grb_with_br(color)
        self.draw()
        return f"Set brightness to {br}%"

    def draw_colormap(self, bitmap:list):
        """
        Draw a bitmap on the Neopixel
        bitmap: [(x, y, (r, g, b)),
                 (x, y, (r, g, b)), ...]
        """
        if len(bitmap) == 0:
            self.clear()
            return
        self._set_colormap(bitmap)
        self.draw()

    def _set_colormap(self, bitmap:list):
        """
        Set colors as a color map without drawing.
        """
        for bm in bitmap:
            x, y, color = bm
            self.set_pixel(x, y, color, zigzag=False)

    def export_colormap(self):
        """
        Export the current screen as bitmap
        """
        colormap = []
        for i, color in enumerate(self._color_buffer):
            x, y = self._index_to_coord(i, zigzag=False)
            colormap.append((x, y, color))
        return colormap

    def effect_context(self):
        """
        Share matrix dimensions and dynamic color with effect generators.
        """
        return make_context(self.width, self.height, lambda: NeoPixelMatrix.DEFAULT_COLOR)

##########################################################################################################
##########################################################################################################
# --- Example usage with micrOS framework ---

def load(width=8, height=8, neop=14, i2c_sda=11, i2c_scl=12, builtin=1):
    """
    Load NeoPixelMatrix instance.
    :param width: neopixel matrix width (default: 8)
    :param height: neopixel matrix height (default: 8)
    :param neop: neopixel GPIO number (default: 14)
    :param i2c_sda: I2C data GPIO number for QMI8658C GYRO (default: 11)
    :param i2c_scl: I2C clock GPIO number for QMI8658C GYRO (default: 12)
    :param builtin: built-in/progress LED GPIO number (default: 1)

    ESP32-S3 Matrix 8x8 RGB-LED WiFi Bluetooth With QST Attitude Gyro Sensor QMI8658C
      https://spotpear.com/shop/ESP32-S3FH4R2-Matrix-8x8-RGB-LED-WiFi-Bluetooth-QST-Attitude-Gyro-Sensor-QMI8658C-Arduino-Python-ESP-IDF.html
    """
    if NeoPixelMatrix.INSTANCE is None:
        NeoPixelMatrix(width=width, height=height, pin=bind_pin('neop', neop))
        web_endpoint('matrixDraw', 'matrix_draw.html')
        # Overwrite i2c bus pins for neomatrix board for QMI8658C
        bind_pin('i2c_sda', i2c_sda)
        bind_pin('i2c_scl', i2c_scl)
        # Set default builtin led (no built-in led on hw, external available...)
        bind_pin('builtin', builtin)
    return NeoPixelMatrix.INSTANCE


def pixel(x, y, color=None, show=True):
    """
    Set pixel at (x,y) to RGB color.
    """
    color = NeoPixelMatrix.DEFAULT_COLOR if color is None else color
    matrix = load()
    matrix.set_pixel(x, y, color)
    if show:
        matrix.draw()
        return "Set and draw color"
    return "Set color"


def draw():
    """
    Draw the current frame manually on the screen.
    """
    load().draw()
    return "Draw screen"


def clear():
    """
    Clear the screen.
    """
    load().clear()
    return "Clear screen"


def color_fill(r: int, g: int, b: int):
    """
    Fill the screen with a solid color.
    OR
    Change animation color (when possible)
    """
    return load().color((r, g, b))


def brightness(br: int):
    """
    Change the brightness of the display. (0-100)
    """
    return load().brightness(br)


def control(speed_ms=None, bt_draw:bool=None):
    """
    Change the speed of frame generation for animations.
    """
    data = load().control(play_speed_ms=speed_ms, bt_draw=bt_draw)
    _speed_ms = data.get("speed_ms", None)
    return f"Control state: {data} (speed: {_speed_ms}ms)"


def stop():
    """
    Stop the current animation
    """
    return load().stop()


def draw_colormap(bitmap):
    """
    Draw colors as a color map
    [(x, y, (r, g,b)), ...]
    """
    try:
        load().draw_colormap(bitmap)
    except Exception as e:
        return str(e)
    return "Done."


def play_file(file, speed_ms:int=85):
    """
    Play colormap animation from a JSON-lines file under /data.
    """
    if not valid_file_name(file):
        return "Invalid file name: use a file name with extension"
    path = data_dir(file)
    try:
        f = open(path, "r")
        f.close()
    except Exception as e:
        return str(e)
    matrix = load()
    return matrix.play(lambda: file_frame_gen(path), speed_ms=speed_ms, bt_draw=False)


def get_colormap():
    return load().export_colormap()


def status():
    """
    Get the current status of the matrix
    """
    matrix = NeoPixelMatrix.INSTANCE
    r, g, b = NeoPixelMatrix.DEFAULT_COLOR
    br = NeoPixelMatrix.DEFAULT_BRIGHTNESS if matrix is None else int(matrix._brightness * 100 + 0.5)
    state = 1 if br > 0 and (r > 0 or g > 0 or b > 0) else 0
    return {'R': r, 'G': g, 'B': b, 'S': state, 'BR': br}


def pinmap():
    """
    Shows logical pins used by this Load Module.
    """
    return pinmap_search(['neop', 'i2c_sda', 'i2c_scl', 'builtin'])


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

def rainbow(speed_ms=0):
    """
    Play rainbow effect
    """
    matrix = load()
    ctx = matrix.effect_context()
    return matrix.play(lambda: rainbow_gen(ctx), speed_ms=speed_ms, bt_draw=True, bt_size=matrix.width)


def snake(speed_ms:int=30, length:int=6):
    matrix = load()
    ctx = matrix.effect_context()
    return matrix.play(lambda: snake_gen(ctx, length=length), speed_ms=speed_ms, bt_draw=False)


def spiral(speed_ms=40):
    matrix = load()
    ctx = matrix.effect_context()
    return matrix.play(lambda: matrix.clear() or spiral_gen(ctx), speed_ms=speed_ms, bt_draw=True, bt_size=matrix.width)


def noise(speed_ms:int=85):
    matrix = load()
    ctx = matrix.effect_context()
    return matrix.play(lambda: noise_gen(ctx), speed_ms=speed_ms, bt_draw=True, bt_size=max(1, matrix.width // 2))


def help(widgets=False):
    return resolve(('load width=8 height=8 neop=14 i2c_sda=11 i2c_scl=12 builtin=1',
                     'pixel x y color=(10, 3, 0) show=True',
                     'BUTTON clear',
                     'COLOR color_fill r=<0-255-5> g=<0-255-5> b=<0-255-5>',
                     'SLIDER brightness br=<0-60-2>',
                     'BUTTON stop',
                     'BUTTON snake speed_ms=50 length=5',
                     'BUTTON rainbow',
                     'BUTTON spiral speed_ms=40',
                     'BUTTON noise speed_ms=85',
                     'play_file file="animation.json" speed_ms=85',
                     'SLIDER control speed_ms=<1-200> bt_draw=None',
                     'draw_colormap bitmap=[(0,0,(10,2,0)),(x,y,color),...]',
                     'get_colormap',
                     'pinmap',
                     'STATUS status'), widgets=widgets)
