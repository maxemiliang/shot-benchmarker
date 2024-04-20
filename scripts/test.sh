#!/bin/bash
# Environment variables
FILE=requirements.txt

source project_2001223-openrc.sh

cd ..
export INPUT_BENCHMARK_FOLDER=MINLP-convex-small
export INPUT_BENCHMARK_TYPE=nl
export INPUT_SHOT_EXECUTABLE=/home/maxemilian/projects/master-thesis/shot-benchmarker/SHOT
#export INPUT_COMPARISON_SUFFIX=test

# Github specific stuff
export GITHUB_REF_TYPE="branch"
export GITHUB_REF_NAME="feature/ci-cd-improvements"
export GITHUB_RUN_NUMBER="1"

if [ ! -d "venv" ]
then
    python -m venv venv
fi
source venv/bin/activate
if [ -f "$FILE" ]; then
    echo "$FILE exists, checking Python requirements..."
    pip freeze > current_requirements.txt
    DIFF=$(diff current_requirements.txt $FILE)
    if [ "$DIFF" != "" ];
    then
        echo "Python requirements mismatch. Installing necessary packages..."
        pip install -r $FILE
    else
        echo "All Python requirements are satisfied."
    fi
else
    echo "No requirements.txt file found, skipping check."
fi
rm current_requirements.txt
python main.py -r 5 -c -s
