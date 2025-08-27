#!/bin/zsh

trap 'echo \\n\\nZMQtestclient terminated!' INT
source .venv/bin/activate
python pysagax/zmqtestclient.py
vared -p 'Press enter to exit' -c tmp