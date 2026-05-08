from random import randint


class EffectContext:
    """
    Shared effect input for matrix size and dynamic color lookup.
    """
    __slots__ = ("width", "height", "_color_getter")

    def __init__(self, width:int=8, height:int=8, color_getter=None):
        self.width = width
        self.height = height
        self._color_getter = color_getter if color_getter else self._default_color

    def color(self):
        return self._color_getter()

    @staticmethod
    def _default_color():
        return (100, 23, 0)


def make_context(width:int=8, height:int=8, color_getter=None):
    return EffectContext(width, height, color_getter)


def _resolve_context(ctx=None, height:int=None, color_getter=None):
    if isinstance(ctx, EffectContext):
        return ctx
    if isinstance(ctx, int):
        return EffectContext(ctx, height if height is not None else 8, color_getter)
    return EffectContext(color_getter=color_getter)


def rainbow_gen(ctx=None, height:int=None, total_frames=64):
    """
    Rainbow color effect generator for LED matrix
    """
    ctx = _resolve_context(ctx, height)

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
        for y in range(ctx.height):
            for x in range(ctx.width):
                index = y * ctx.width + x
                hue = ((index + frame) % 64) / 64.0
                r, g, b = _hsv_to_rgb(hue, 1.0, 0.7)
                yield x, y, (r, g, b)


def snake_gen(ctx=None, height:int=None, length:int=6, color_getter=None):
    """
    Snake color effect generator for LED matrix
    :param ctx: EffectContext with matrix dimensions and color getter
    :param length: snake length in pixels
    """
    if isinstance(ctx, int) and callable(height) and color_getter is None:
        length = ctx
        color_getter = height
        ctx = None
        height = None
    elif isinstance(ctx, EffectContext) and isinstance(height, int) and length == 6:
        length = height
        height = None
    ctx = _resolve_context(ctx, height, color_getter)
    clear_color = (0, 0, 0)
    total_pixels = ctx.width * ctx.height
    total_steps = total_pixels + length  # run just past the end to clear tail

    for step in range(total_steps):
        # 1) clear the tail pixel once the snake is longer than `length`
        if step >= length:
            tail_idx = step - length
            tx, ty = tail_idx % ctx.width, tail_idx // ctx.width
            yield tx, ty, clear_color

        # 2) draw the snake segments with decreasing brightness
        for i in range(length):
            seg_idx = step - i
            if 0 <= seg_idx < total_pixels:
                x, y = seg_idx % ctx.width, seg_idx // ctx.width
                br = 1.0 - (i / length) ** 0.6
                r, g, b = ctx.color()
                color = (int(r * br), int(g * br), int(b * br))
                yield x, y, color


def spiral_gen(ctx=None, height:int=None, color_getter=None, trail:int=12, hold:int=6):
    """
    Center-out spiral with row-prewarp so the visual is continuous
    even when set_pixel() applies zigzag=True internally.
    """
    ctx = _resolve_context(ctx, height, color_getter)

    # Build center-out spiral path in true matrix coords (x,y).
    # Exact center on odd sizes; upper-left of center 2x2 on even sizes.
    cx = (ctx.width // 2 - 1) if (ctx.width % 2 == 0) else (ctx.width // 2)
    cy = (ctx.height // 2 - 1) if (ctx.height % 2 == 0) else (ctx.height // 2)

    x, y = cx, cy
    path, seen = [], set()

    def _add(ax, ay):
        if 0 <= ax < ctx.width and 0 <= ay < ctx.height and (ax, ay) not in seen:
            seen.add((ax, ay))
            path.append((ax, ay))

    _add(x, y)
    dirs = ((1, 0), (0, 1), (-1, 0), (0, -1))  # R, D, L, U
    step_len, d = 1, 0
    while len(path) < ctx.width * ctx.height:
        for _ in range(2):
            dx, dy = dirs[d & 3]
            for _ in range(step_len):
                x += dx
                y += dy
                _add(x, y)
                if len(path) >= ctx.width * ctx.height:
                    break
            d += 1
            if len(path) >= ctx.width * ctx.height:
                break
        step_len += 1

    def _warp(ax, ay):
        return (ctx.width - 1 - ax, ay) if (ay & 1) else (ax, ay)

    off = (0, 0, 0)

    def _shade(k):
        r0, g0, b0 = ctx.color()
        k = max(0.0, min(1.0, k)) ** 0.9
        return int(r0 * k), int(g0 * k), int(b0 * k)

    # Expand with tail.
    for n in range(len(path)):
        clear_at = n - trail - 1
        if clear_at >= 0:
            cx_, cy_ = _warp(*path[clear_at])
            yield cx_, cy_, off

        start = 0 if n < trail else (n - trail + 1)
        span = max(1, n - start + 1)
        for i in range(start, n + 1):
            k = (i - start + 1) / span
            px, py = _warp(*path[i])
            yield px, py, _shade(k)

    # Brief hold.
    hx, hy = _warp(*path[-1])
    for _ in range(hold):
        yield hx, hy, _shade(1.0)

    # Shrink with fading tail.
    for n in range(len(path) - 1, -1, -1):
        px, py = _warp(*path[n])
        yield px, py, off
        start = max(0, n - trail + 1)
        span = max(1, n - start)
        for i in range(start, n):
            k = (i - start + 1) / span
            qx, qy = _warp(*path[i])
            yield qx, qy, _shade(k)


def noise_gen(ctx=None, height:int=None, color_getter=None):
    """
    Noise color effect generator for LED matrix.
    """
    ctx = _resolve_context(ctx, height, color_getter)

    total_steps = ctx.width * ctx.height
    for step in range(total_steps):
        x, y = step % ctx.width, step // ctx.width
        r, g, b = ctx.color()
        br = float(randint(0, 100) * 0.01)
        color = (int(r * br), int(g * br), int(b * br))
        yield x, y, color
