"""Synthetic intro tracks for calibrating pipeline/intro_style.py.

    drums(out, sec, bpm)   kick on every beat, accented every 4, hat noise on
                           the off-beats: bright, dense onsets (energetic)
    ballad(out, sec, bpm)  sustained major chords I-IV-V-I, soft attack, one
                           chord a bar: dark, sparse onsets (emotional)

Generated with ffmpeg's aevalsrc, so they are reproducible and royalty-free.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

def drums(out, sec=40, bpm=140):
    beat = 60.0 / bpm
    # kick on every beat (decaying 60Hz burst), hat noise on off-beats, accent every 4
    expr = (f"(0.9*sin(2*PI*60*mod(t,{beat}))*exp(-30*mod(t,{beat}))"
            f"*(1+0.6*eq(mod(floor(t/{beat}),4),0)))"
            f"+0.25*(random(0)-0.5)*exp(-60*mod(t+{beat/2},{beat}))")
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"aevalsrc='{expr}':s=44100:d={sec}", "-ac", "2",
                    "-b:a", "192k", str(out)], check=True)
def ballad(out, sec=40, bpm=66):
    beat = 60.0 / bpm
    bar = 4 * beat
    # C major / F major / G major / C major, soft attack, one chord a bar
    roots = [261.63, 174.61, 196.0, 261.63]
    chord = "+".join(
        f"if(eq(mod(floor(t/{bar}),4),{k}),"
        f"0.12*sin(2*PI*{r}*t)+0.08*sin(2*PI*{r*1.25992}*t)+0.08*sin(2*PI*{r*1.4983}*t),0)"
        for k, r in enumerate(roots))
    env = f"(1-exp(-3*mod(t,{bar})))"
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"aevalsrc='({chord})*{env}':s=44100:d={sec}", "-ac", "2",
                    "-b:a", "192k", str(out)], check=True)
