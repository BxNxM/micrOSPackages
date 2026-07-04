"""Small, dependency-free QR Code generator for CPython and MicroPython.

The encoder supports byte mode, error-correction level L, and versions 1-10.
Typical use:

    import qr_code
    qr_code.print_qr("https://micros.example")
"""

_DATA_CODEWORDS = (19, 34, 55, 80, 108, 136, 156, 194, 232, 274)
_ECC_PER_BLOCK = (7, 10, 15, 20, 26, 18, 20, 24, 30, 18)
_BLOCKS = (1, 1, 1, 1, 1, 2, 2, 2, 2, 4)


def _append_bits(out, value, length):
    for i in range(length - 1, -1, -1):
        out.append((value >> i) & 1)


def _gf_mul(x, y):
    result = 0
    while y:
        if y & 1:
            result ^= x
        y >>= 1
        x = (x << 1) ^ (0x11D if x & 0x80 else 0)
    return result


def _rs_divisor(degree):
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 2)
    return result


def _rs_remainder(data, divisor):
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i in range(len(result)):
            result[i] ^= _gf_mul(divisor[i], factor)
    return result


def _raw_modules(version):
    result = (16 * version + 128) * version + 64
    if version >= 2:
        align = version // 7 + 2
        result -= (25 * align - 10) * align - 55
        if version >= 7:
            result -= 36
    return result


def _make_codewords(data, version):
    capacity = _DATA_CODEWORDS[version - 1]
    bits = []
    _append_bits(bits, 4, 4)  # Byte mode
    _append_bits(bits, len(data), 8 if version < 10 else 16)
    for byte in data:
        _append_bits(bits, byte, 8)
    _append_bits(bits, 0, min(4, capacity * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    out = []
    for i in range(0, len(bits), 8):
        value = 0
        for bit in bits[i:i + 8]:
            value = (value << 1) | bit
        out.append(value)
    pad = 0xEC
    while len(out) < capacity:
        out.append(pad)
        pad ^= 0xFD  # Alternates EC, 11
    return out


def _add_ecc(data, version):
    blocks = _BLOCKS[version - 1]
    ecc_len = _ECC_PER_BLOCK[version - 1]
    raw = _raw_modules(version) // 8
    short_len = raw // blocks
    short_blocks = blocks - raw % blocks
    divisor = _rs_divisor(ecc_len)
    data_blocks = []
    ecc_blocks = []
    offset = 0
    for i in range(blocks):
        length = short_len - ecc_len + (0 if i < short_blocks else 1)
        block = data[offset:offset + length]
        offset += length
        data_blocks.append(block)
        ecc_blocks.append(_rs_remainder(block, divisor))
    result = []
    for i in range(max(len(block) for block in data_blocks)):
        for block in data_blocks:
            if i < len(block):
                result.append(block[i])
    for i in range(ecc_len):
        for block in ecc_blocks:
            result.append(block[i])
    return result


def _alignment_positions(version):
    if version == 1:
        return ()
    count = version // 7 + 2
    step = 26 if version == 32 else ((version * 4 + count * 2 + 1) //
                                     (count * 2 - 2) * 2)
    result = [6]
    pos = version * 4 + 10
    for _ in range(count - 1):
        result.insert(1, pos)
        pos -= step
    return result


def _set_function(matrix, functions, x, y, dark):
    if 0 <= y < len(matrix) and 0 <= x < len(matrix):
        matrix[y][x] = bool(dark)
        functions[y][x] = True


def _finder(matrix, functions, x, y):
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            distance = max(abs(dx), abs(dy))
            _set_function(matrix, functions, x + dx, y + dy,
                          distance != 2 and distance != 4)


def _alignment(matrix, functions, x, y):
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            _set_function(matrix, functions, x + dx, y + dy,
                          max(abs(dx), abs(dy)) != 1)


def _version_bits(matrix, functions, version):
    if version < 7:
        return
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    bits = (version << 12) | rem
    size = len(matrix)
    for i in range(18):
        bit = (bits >> i) & 1
        a, b = size - 11 + i % 3, i // 3
        _set_function(matrix, functions, a, b, bit)
        _set_function(matrix, functions, b, a, bit)


def _format_bits(matrix, functions, mask):
    # Error correction L has format selector 01.
    data = (1 << 3) | mask
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    bits = ((data << 10) | rem) ^ 0x5412
    size = len(matrix)
    for i in range(0, 6):
        _set_function(matrix, functions, 8, i, (bits >> i) & 1)
    _set_function(matrix, functions, 8, 7, (bits >> 6) & 1)
    _set_function(matrix, functions, 8, 8, (bits >> 7) & 1)
    _set_function(matrix, functions, 7, 8, (bits >> 8) & 1)
    for i in range(9, 15):
        _set_function(matrix, functions, 14 - i, 8, (bits >> i) & 1)
    for i in range(0, 8):
        _set_function(matrix, functions, size - 1 - i, 8, (bits >> i) & 1)
    for i in range(8, 15):
        _set_function(matrix, functions, 8, size - 15 + i,
                      (bits >> i) & 1)
    _set_function(matrix, functions, 8, size - 8, True)


def _base_matrix(version):
    size = version * 4 + 17
    matrix = [[False] * size for _ in range(size)]
    functions = [[False] * size for _ in range(size)]
    for i in range(size):
        _set_function(matrix, functions, 6, i, i % 2 == 0)
        _set_function(matrix, functions, i, 6, i % 2 == 0)
    _finder(matrix, functions, 3, 3)
    _finder(matrix, functions, size - 4, 3)
    _finder(matrix, functions, 3, size - 4)
    positions = _alignment_positions(version)
    for y in positions:
        for x in positions:
            if not functions[y][x]:
                _alignment(matrix, functions, x, y)
    _version_bits(matrix, functions, version)
    _format_bits(matrix, functions, 0)  # Reserves format modules.
    return matrix, functions


def _mask_bit(mask, x, y):
    if mask == 0:
        return (x + y) % 2 == 0
    if mask == 1:
        return y % 2 == 0
    if mask == 2:
        return x % 3 == 0
    if mask == 3:
        return (x + y) % 3 == 0
    if mask == 4:
        return (x // 3 + y // 2) % 2 == 0
    if mask == 5:
        return x * y % 2 + x * y % 3 == 0
    if mask == 6:
        return (x * y % 2 + x * y % 3) % 2 == 0
    return ((x + y) % 2 + x * y % 3) % 2 == 0


def _draw_data(base, functions, codewords, mask):
    matrix = [row[:] for row in base]
    bits = []
    for value in codewords:
        _append_bits(bits, value, 8)
    index = 0
    size = len(matrix)
    right = size - 1
    upward = True
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            y = size - 1 - vert if upward else vert
            for x in (right, right - 1):
                if not functions[y][x]:
                    bit = bits[index] if index < len(bits) else 0
                    index += 1
                    matrix[y][x] = bool(bit) ^ _mask_bit(mask, x, y)
        upward = not upward
        right -= 2
    _format_bits(matrix, [[False] * size for _ in range(size)], mask)
    return matrix


def _penalty(matrix):
    size = len(matrix)
    score = 0
    for rows in (matrix, zip(*matrix)):
        for row in rows:
            row = list(row)
            run_color = row[0]
            run = 1
            for value in row[1:]:
                if value == run_color:
                    run += 1
                else:
                    if run >= 5:
                        score += run - 2
                    run_color, run = value, 1
            if run >= 5:
                score += run - 2
            pattern = "1011101"
            text = "".join("1" if value else "0" for value in row)
            for i in range(size - 10):
                part = text[i:i + 11]
                if part == pattern + "0000" or part == "0000" + pattern:
                    score += 40
    for y in range(size - 1):
        for x in range(size - 1):
            total = (matrix[y][x] + matrix[y][x + 1] +
                     matrix[y + 1][x] + matrix[y + 1][x + 1])
            if total == 0 or total == 4:
                score += 3
    dark = sum(sum(row) for row in matrix)
    score += abs(dark * 20 - size * size * 10) // (size * size) * 10
    return score


def make(url):
    """Return a QR matrix (a list of boolean rows) for *url*."""
    if not isinstance(url, str):
        raise TypeError("url must be a string")
    data = url.encode("utf-8")
    version = 0
    for candidate in range(1, 11):
        count_bits = 8 if candidate < 10 else 16
        if 4 + count_bits + len(data) * 8 <= _DATA_CODEWORDS[candidate - 1] * 8:
            version = candidate
            break
    if not version:
        raise ValueError("URL is too long (maximum is 271 UTF-8 bytes)")
    words = _add_ecc(_make_codewords(data, version), version)
    base, functions = _base_matrix(version)
    best = None
    best_score = None
    for mask in range(8):
        candidate = _draw_data(base, functions, words, mask)
        score = _penalty(candidate)
        if best_score is None or score < best_score:
            best, best_score = candidate, score
    return best


def render(url, dark="██", light="  ", border=2):
    """Return a terminal-friendly string containing the QR Code."""
    matrix = make(url)
    width = len(matrix) + border * 2
    rows = [light * width] * border
    for row in matrix:
        rows.append(light * border + "".join(dark if cell else light
                                              for cell in row) +
                    light * border)
    rows.extend([light * width] * border)
    return "\n".join(rows)


def print_qr(url, dark="██", light="  ", border=2):
    """Print a URL as a QR Code and return its matrix."""
    matrix = make(url)
    width = len(matrix) + border * 2
    blank = light * width
    for _ in range(border):
        print(blank)
    for row in matrix:
        print(light * border + "".join(dark if cell else light
                                        for cell in row) + light * border)
    for _ in range(border):
        print(blank)
    return matrix


if __name__ == "__main__":
    print_qr("https://github.com/BxNxM/micrOS")
