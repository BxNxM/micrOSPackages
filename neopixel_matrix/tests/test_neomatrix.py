"""
LM_neomatrix.py and effects.py unit tests - runs on host CPython without hardware.

Run:
  python3 -m pytest neopixel_matrix/tests/test_neomatrix.py -v
"""

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent.parent / "package"


def _load_effects_module():
    if "neopixel_matrix" not in sys.modules:
        pkg = types.ModuleType("neopixel_matrix")
        pkg.__path__ = [str(PACKAGE_DIR)]
        sys.modules["neopixel_matrix"] = pkg

    spec = importlib.util.spec_from_file_location(
        "neopixel_matrix.effects", str(PACKAGE_DIR / "effects.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["neopixel_matrix.effects"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_file_player_module():
    if "neopixel_matrix" not in sys.modules:
        pkg = types.ModuleType("neopixel_matrix")
        pkg.__path__ = [str(PACKAGE_DIR)]
        sys.modules["neopixel_matrix"] = pkg

    spec = importlib.util.spec_from_file_location(
        "neopixel_matrix.file_player", str(PACKAGE_DIR / "file_player.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["neopixel_matrix.file_player"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_neomatrix_module():
    effects_mod = _load_effects_module()
    file_player_mod = _load_file_player_module()

    machine = types.ModuleType("machine")

    class Pin:
        OUT = 1

        def __init__(self, pin, mode=None):
            self.pin = pin
            self.mode = mode

    machine.Pin = Pin
    sys.modules["machine"] = machine

    neopixel = types.ModuleType("neopixel")

    class NeoPixel:
        def __init__(self, pin, count):
            self.pin = pin
            self.data = [(0, 0, 0)] * count
            self.write_count = 0

        def __setitem__(self, index, value):
            self.data[index] = value

        def __getitem__(self, index):
            return self.data[index]

        def write(self):
            self.write_count += 1

    neopixel.NeoPixel = NeoPixel
    sys.modules["neopixel"] = neopixel

    microIO = types.ModuleType("microIO")
    microIO.bind_pin = lambda name, pin: pin
    sys.modules["microIO"] = microIO

    types_mod = types.ModuleType("Types")
    types_mod.resolve = lambda value, **kwargs: value
    sys.modules["Types"] = types_mod

    common = types.ModuleType("Common")
    common.manage_task = lambda tag, operation: False
    common.web_endpoint = lambda endpoint, path: None
    common.data_dir = lambda f_name=None: f_name if f_name else "."

    class AnimationPlayer:
        def __init__(self, tag=None, **kwargs):
            self._task_tag = "%s.player" % (tag if tag else "animation")
            self.play_calls = []

        def control(self, play_speed_ms=None, bt_draw=None, bt_size=None, loop=None):
            return {"speed_ms": play_speed_ms, "batched": bt_draw, "size": bt_size}

        def play(self, animation=None, speed_ms=None, bt_draw=False, bt_size=None, loop=True):
            self.play_calls.append((animation, speed_ms, bt_draw, bt_size, loop))
            return {"speed_ms": speed_ms, "batched": bt_draw, "size": bt_size, "loop": loop}

        def stop(self):
            return "Stop animation player"

    common.AnimationPlayer = AnimationPlayer
    sys.modules["Common"] = common

    spec = importlib.util.spec_from_file_location(
        "LM_neomatrix_real", str(PACKAGE_DIR / "LM_neomatrix.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._effects_mod = effects_mod
    mod._file_player_mod = file_player_mod
    return mod


effects = _load_effects_module()
file_player = _load_file_player_module()


class TestEffectGenerators(unittest.TestCase):
    def test_generators_use_shared_context_dimensions(self):
        ctx = effects.make_context(5, 3, lambda: (20, 10, 5))

        generators = (
            effects.rainbow_gen(ctx, total_frames=1),
            effects.snake_gen(ctx, length=3),
            effects.spiral_gen(ctx, trail=4, hold=1),
            effects.noise_gen(ctx),
        )

        for gen in generators:
            sample = [next(gen) for _ in range(6)]
            for x, y, color in sample:
                self.assertGreaterEqual(x, 0)
                self.assertLess(x, ctx.width)
                self.assertGreaterEqual(y, 0)
                self.assertLess(y, ctx.height)
                self.assertEqual(len(color), 3)

    def test_context_color_is_dynamic(self):
        color = {"value": (10, 0, 0)}
        ctx = effects.make_context(2, 2, lambda: color["value"])

        gen = effects.snake_gen(ctx, length=1)
        self.assertEqual(next(gen), (0, 0, (10, 0, 0)))

        color["value"] = (0, 20, 0)
        self.assertEqual(next(gen), (0, 0, (0, 0, 0)))
        self.assertEqual(next(gen), (1, 0, (0, 20, 0)))

    def test_snake_clears_tail_after_matrix_end(self):
        ctx = effects.make_context(2, 1, lambda: (9, 6, 3))
        frames = list(effects.snake_gen(ctx, length=1))
        self.assertEqual(frames[-1], (1, 0, (0, 0, 0)))

    def test_legacy_generator_call_shapes_still_work(self):
        rainbow = next(effects.rainbow_gen(3, 2, total_frames=1))
        snake = next(effects.snake_gen(1, lambda: (7, 4, 2)))

        self.assertEqual(rainbow[0:2], (0, 0))
        self.assertEqual(snake, (0, 0, (7, 4, 2)))


class TestFilePlayer(unittest.TestCase):
    def test_file_colormap_gen_streams_json_lines(self):
        tmpdir = tempfile.mkdtemp()
        file_path = os.path.join(tmpdir, "anim.jsonl")
        with open(file_path, "w") as f:
            f.write('[[0, 0, [1, 2, 3]]]\n')
            f.write('{"pixels": [{"x": 1, "y": 0, "color": {"r": 4, "g": 5, "b": 6}}]}\n')

        try:
            self.assertEqual(
                list(file_player.file_colormap_gen(file_path)),
                [(0, 0, (1, 2, 3)), (1, 0, (4, 5, 6))],
            )
        finally:
            os.remove(file_path)
            os.rmdir(tmpdir)

    def test_file_colormap_gen_accepts_coordinate_dict_frame(self):
        self.assertEqual(list(file_player.iter_frame_pixels({"2,1": [7, 8, 9]})), [(2, 1, (7, 8, 9))])

    def test_valid_file_name_requires_extension_and_plain_name(self):
        self.assertTrue(file_player.valid_file_name("anim.jsonl"))
        self.assertFalse(file_player.valid_file_name("anim"))
        self.assertFalse(file_player.valid_file_name("../anim.jsonl"))

    def test_webui_export_json_line_is_file_player_compatible(self):
        exported_line = '[[0,0,[131,17,0]],[1,0,[0,255,0]]]\n'
        tmpdir = tempfile.mkdtemp()
        file_path = os.path.join(tmpdir, "web_export.jsonl")
        with open(file_path, "w") as f:
            f.write(exported_line)

        try:
            self.assertEqual(
                list(file_player.file_colormap_gen(file_path)),
                [(0, 0, (131, 17, 0)), (1, 0, (0, 255, 0))],
            )
        finally:
            os.remove(file_path)
            os.rmdir(tmpdir)

    def test_file_frame_gen_yields_one_frame_per_line(self):
        tmpdir = tempfile.mkdtemp()
        file_path = os.path.join(tmpdir, "frames.jsonl")
        with open(file_path, "w") as f:
            f.write('[[0, 0, [1, 2, 3]]]\n')
            f.write('[[1, 0, [4, 5, 6]]]\n')

        try:
            self.assertEqual(
                list(file_player.file_frame_gen(file_path)),
                [([(0, 0, (1, 2, 3))],), ([(1, 0, (4, 5, 6))],)],
            )
        finally:
            os.remove(file_path)
            os.rmdir(tmpdir)


class TestNeoMatrixModule(unittest.TestCase):
    def setUp(self):
        self.mod = _load_neomatrix_module()
        self.mod.NeoPixelMatrix.INSTANCE = None
        self.mod.NeoPixelMatrix.DEFAULT_COLOR = (100, 23, 0)

    def test_matrix_effect_context_shares_size_and_live_color(self):
        matrix = self.mod.NeoPixelMatrix(width=4, height=2, pin=14)
        ctx = matrix.effect_context()

        self.assertEqual(ctx.width, 4)
        self.assertEqual(ctx.height, 2)
        self.assertEqual(ctx.color(), (100, 23, 0))

        self.mod.NeoPixelMatrix.DEFAULT_COLOR = (1, 2, 3)
        self.assertEqual(ctx.color(), (1, 2, 3))

    def test_animation_wrappers_use_matrix_width_for_batch_size(self):
        matrix = self.mod.NeoPixelMatrix(width=6, height=4, pin=14)
        self.mod.NeoPixelMatrix.INSTANCE = matrix

        result = self.mod.rainbow(speed_ms=12)

        self.assertEqual(result["size"], 6)
        self.assertEqual(result["speed_ms"], 12)
        self.assertTrue(result["batched"])

    def test_animation_wrapper_passes_callable_animation(self):
        matrix = self.mod.NeoPixelMatrix(width=6, height=4, pin=14)
        self.mod.NeoPixelMatrix.INSTANCE = matrix

        self.mod.snake(speed_ms=12, length=2)
        animation = matrix.play_calls[-1][0]

        self.assertTrue(callable(animation))
        x, y, color = next(animation())
        self.assertGreaterEqual(x, 0)
        self.assertLess(x, 6)
        self.assertGreaterEqual(y, 0)
        self.assertLess(y, 4)
        self.assertEqual(len(color), 3)

    def test_noise_wrapper_passes_callable_animation(self):
        matrix = self.mod.NeoPixelMatrix(width=4, height=2, pin=14)
        self.mod.NeoPixelMatrix.INSTANCE = matrix

        self.mod.noise(speed_ms=12)
        animation = matrix.play_calls[-1][0]

        self.assertTrue(callable(animation))
        x, y, color = next(animation())
        self.assertGreaterEqual(x, 0)
        self.assertLess(x, 4)
        self.assertGreaterEqual(y, 0)
        self.assertLess(y, 2)
        self.assertEqual(len(color), 3)

    def test_play_file_resolves_data_dir_and_starts_animation(self):
        tmpdir = tempfile.mkdtemp()
        file_name = "anim.jsonl"
        file_path = os.path.join(tmpdir, file_name)
        with open(file_path, "w") as f:
            f.write('[[0, 0, [1, 2, 3]]]\n')

        try:
            self.mod.data_dir = lambda f_name=None: (
                os.path.join(tmpdir, f_name) if f_name else tmpdir
            )
            matrix = self.mod.NeoPixelMatrix(width=4, height=2, pin=14)
            self.mod.NeoPixelMatrix.INSTANCE = matrix

            result = self.mod.play_file(file_name, speed_ms=25)
            animation = matrix.play_calls[-1][0]

            self.assertEqual(result["speed_ms"], 25)
            self.assertFalse(result["batched"])
            self.assertTrue(callable(animation))
            self.assertEqual(list(animation()), [([(0, 0, (1, 2, 3))],)])
        finally:
            os.remove(file_path)
            os.rmdir(tmpdir)

    def test_matrix_update_draws_file_frames_as_whole_colormaps(self):
        matrix = self.mod.NeoPixelMatrix(width=4, height=2, pin=14)

        matrix.update([(0, 0, (10, 20, 30)), (1, 0, (1, 2, 3))])
        matrix.draw()

        self.assertEqual(matrix.export_colormap()[0], (0, 0, (10, 20, 30)))
        self.assertEqual(matrix.export_colormap()[1], (1, 0, (1, 2, 3)))

    def test_play_file_requires_file_name_with_extension(self):
        result = self.mod.play_file("anim")
        self.assertIn("Invalid file name", result)

    def test_control_reports_speed_ms_key(self):
        matrix = self.mod.NeoPixelMatrix(width=3, height=3, pin=14)
        self.mod.NeoPixelMatrix.INSTANCE = matrix

        result = self.mod.control(speed_ms=77, bt_draw=True)

        self.assertIn("speed: 77ms", result)


if __name__ == "__main__":
    unittest.main()
