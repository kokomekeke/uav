#!/bin/zsh

# change the terminal window title
echo -ne "\033]0;ZMQtestclient\007"

trap 'echo \\n\\nZMQtestclient terminated!' INT
source .venv/bin/activate
python pysagax/zmqtestclient.py
vared -p 'Press enter to exit' -c tmp