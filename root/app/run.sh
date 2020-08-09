#!/bin/bash

export FLASK_APP="hello.py"

cd /app

flask run --host=0.0.0.0
