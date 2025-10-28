#!/bin/zsh

# change the terminal window title


DISABLE_AUTO_TITLE="true"
echo -ne "\033]0;SPOTclient\007"

echo -en "\e]0;stringa\a" #-- Set icon name and window title to string
echo -en "\e]1;stringb\a" #-- Set icon name to string
echo -en "\e]2;stringc\a" #-- Set window title to string

printf "\033];%s\07\n" "SPOT 2"

sleep 2
# prevent keyboard interrupt from closing the terminal
trap 'echo \\n\\nSPOT 2 terminated!' INT
sleep 2
# setup
cd client
/home/rp/.nvm/versions/node/v22.16.0/bin/npm install
sleep 2
# run
/home/rp/.nvm/versions/node/v22.16.0/bin/npm run dev
sleep 2
# wait for user to manually close the terminal
vared -p 'Press enter to exit' -c tmp