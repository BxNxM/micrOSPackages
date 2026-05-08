from json import loads


def valid_file_name(file):
    return isinstance(file, str) and "/" not in file and "\\" not in file and "." in file and not file.endswith(".")


def parse_color(color):
    if isinstance(color, dict):
        return (int(color.get("r", 0)), int(color.get("g", 0)), int(color.get("b", 0)))
    return (int(color[0]), int(color[1]), int(color[2]))


def parse_pixel(pixel):
    if isinstance(pixel, dict):
        color = pixel.get("color", pixel)
        return int(pixel["x"]), int(pixel["y"]), parse_color(color)
    return int(pixel[0]), int(pixel[1]), parse_color(pixel[2])


def iter_frame_pixels(frame):
    if isinstance(frame, dict):
        for key in ("bitmap", "colormap", "pixels", "frame"):
            if key in frame:
                frame = frame[key]
                break
        else:
            if "x" in frame and "y" in frame:
                yield parse_pixel(frame)
                return
            for coord, color in frame.items():
                if isinstance(color, dict) and "x" in color and "y" in color:
                    yield parse_pixel(color)
                    continue
                x, y = coord.split(",", 1)
                yield int(x), int(y), parse_color(color)
            return
    for pixel in frame:
        yield parse_pixel(pixel)


def file_colormap_gen(path):
    """
    Generate colormap pixels from a JSON-lines animation file.
    Each non-empty line is one frame.
    """
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line == "":
                continue
            frame = loads(line)
            for pixel in iter_frame_pixels(frame):
                yield pixel


def file_frame_gen(path):
    """
    Generate one colormap frame per JSON line.
    """
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line == "":
                continue
            yield (list(iter_frame_pixels(loads(line))),)
