#!/usr/bin/env python3
import json
from pathlib import Path
from render_site import render
ROOT=Path(__file__).resolve().parents[1]
with open(ROOT/"data/resilience-index.json") as f: render(json.load(f))
