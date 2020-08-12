import yaml, traceback, sys, json, inspect

from typing import Dict
from flask import Flask, Config, jsonify
from .libvirtHelper import *

def create_app():
    Flask.config_class = LibvirtConfig
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_yaml(configFile='/config/config.yaml')
    for i, host in enumerate(app.config['hosts']):
        topology, code = get_topology(host)
        if code == 200:
            app.config['hosts'][i].update(topology)

    with app.app_context():
        # Include our Routes
        from . import routes

        return app
