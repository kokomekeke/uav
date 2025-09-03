This folder contains scripts for running the components in sgx-pc the cloned repository directly.

These are useful for developement, when the software has to be tested frequently, without building new wheel files. Launching can sometimes be a cumbersome repeated task, that's when these scripts are useful.

You might need to change a line here or there to make it work on your instance, but you get the idea.


## How to use:
- Run these scripts from terminal
- For even easier usage, you can set up a `.desktop` launcher file for these scripts and place them on the desktop or in the start menu (to show in the start menu, save the desktop files to `/home/username/.local/share/applications/`).
- Don't forget to set the working directory to the path of the local repository, and make the `.sh` scripts excecutable using `sudo chmod +x my_script.sh`.
- An example for the `.desktop` file:


```
[Desktop Entry]
Type=Application
Name=SPOTclient

# Exec=zsh -c "./.sh/run_spotclient.sh"
Exec=xfce4-terminal --title="SPOTclient Terminal" -e "./.sh/run_spotclient.sh" # This one sets the title to SPOTclient

Icon=/home/username/Documents/sgx-pc/pysagax/spot.png
Path=/home/username/Documents/sgx-pc
Terminal=true
```