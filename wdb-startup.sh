#!/bin/bash

sleep 30 
pushd /home/pi/Desktop/warzone-discord-bot
tmux kill-session -t wdb

git pull

tmux new -d -s wdb "/home/pi/.pyenv/versions/wdb/bin/python3 main.py"
popd
