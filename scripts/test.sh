#!/bin/bash
cd ..
export INPUT_BENCHMARK_FOLDER=MINLP-convex-small
export INPUT_BENCHMARK_TYPE=nl
export INPUT_SHOT_EXECUTABLE=/home/maxemilian/projects/master-thesis/shot-benchmarker/SHOT
source venv/bin/activate
python main.py