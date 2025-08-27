#!/bin/zsh

# setup
sudo systemctl stop postgresql
sudo systemctl restart docker
sudo docker-compose up -d
source .venv/bin/activate

# prevent keyboard interrupt from closing the terminal
trap 'echo \\n##########################\\n# pysagaxGND terminated! \#\\n##########################\\n\\n' INT

# run gnd
python pysagax/pysagax_gnd.py -c pysagaxgnd.toml --db-url 'postgresql+psycopg2://pysagax_gnd:S3cret@localhost/comint' --level TRACE

# teardown
sudo docker-compose stop

# wait for user to manually close the terminal
echo '\nFinished\n'
vared -p 'Press enter to exit' -c tmp

