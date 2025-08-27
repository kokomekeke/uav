#!/bin/zsh

# prevent keyboard interrupt from closing the terminal
trap 'echo \\n\\nSPOTclient terminated!' INT

# setup
source .venv/bin/activate

# run
python pysagax/spotclient.py spotclient.toml

# wait for user to manually close the terminal
vared -p 'Press enter to exit' -c tmp