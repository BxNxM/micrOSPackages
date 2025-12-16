
def rainbow_gen(width=8, height=8, total_frames=64):
    """
    Rainbow color effect generator for LED matrix
    """

    def _hsv_to_rgb(h, s, v):
        max_color = 150   #255
        h = float(h)
        s = float(s)
        v = float(v)
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6
        _r, _g, _b = 0, 0, 0
        if i == 0:
            _r, _g, _b = v, t, p
        elif i == 1:
            _r, _g, _b = q, v, p
        elif i == 2:
            _r, _g, _b = p, v, t
        elif i == 3:
            _r, _g, _b = p, q, v
        elif i == 4:
            _r, _g, _b = t, p, v
        elif i == 5:
            _r, _g, _b = v, p, q
        return int(_r * max_color), int(_g * max_color), int(_b * max_color)

    # Generator
    for frame in range(total_frames):
        for y in range(height):
            for x in range(width):
                index = y * width + x
                hue = ((index + frame) % 64) / 64.0
                r, g, b = _hsv_to_rgb(hue, 1.0, 0.7)
                yield x, y, (r, g, b)


def snake_gen(length:int, color_getter):
    """
    Snake color effect generator for LED matrix
    :param length: snake length in pixels
    :param color_getter: callable that returns (r:int, g:int, b:int) tuple
    """
    clear_color = (0, 0, 0)
    total_pixels = 8 * 8
    total_steps = total_pixels + length  # run just past the end to clear tail

    for step in range(total_steps):
        # 1) clear the tail pixel once the snake is longer than `length`
        if step >= length:
            tail_idx = step - length
            tx, ty = tail_idx % 8, tail_idx // 8
            yield tx, ty, clear_color

        # 2) draw the snake segments with decreasing brightness
        for i in range(length):
            seg_idx = step - i
            if 0 <= seg_idx < total_pixels:
                x, y = seg_idx % 8, seg_idx // 8
                br = 1.0 - (i / length) ** 0.6
                r, g, b = color_getter()
                color = (int(r * br), int(g * br), int(b * br))
                yield x, y, color
