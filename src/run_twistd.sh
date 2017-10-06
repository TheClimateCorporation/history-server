#!/bin/bash

function cleanup {
    sudo rm -f twistd.pid
}
trap cleanup EXIT
sudo rm -f twistd.pid
twistd -n -l - web --wsgi web.app --port 5000
