import struct, tempfile, unittest, wave
from pathlib import Path

from src import humanize


class HumanizeTests(unittest.TestCase):
    def test_filter_graph_scales_with_strength(self):
        low, high = humanize.filter_graph(0.0), humanize.filter_graph(1.0)
        self.assertIn("anoisesrc", low)
        self.assertNotEqual(low, high)

    def test_humanize_produces_mp3_of_same_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.wav"
            with wave.open(str(src), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(struct.pack("<h", 3000) * 24000)  # 1 s tone-ish
            out = humanize.humanize(src, Path(tmp) / "out.mp3", 0.6)
            self.assertTrue(out.exists() and out.stat().st_size > 1000)
            import subprocess
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip())
            self.assertAlmostEqual(dur, 1.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
