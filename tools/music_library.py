# -*- coding: utf-8 -*-
"""music_library.py - command line for the channel's cue library.
The logic lives in pipeline/music_library.py (the render uses it too).

    python tools/music_library.py fetch
    python tools/music_library.py pick --project <name>
    python tools/music_library.py credits --project <name>
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline.music_library import *  # noqa: E402,F401,F403
from pipeline.music_library import (main, load, fetch, pick, choose,  # noqa
                                    credits_text, url_of, film_text,
                                    ensure_cues, MOODS, LIB, CATALOGUE,
                                    _used)

if __name__ == "__main__":
    sys.exit(main())
