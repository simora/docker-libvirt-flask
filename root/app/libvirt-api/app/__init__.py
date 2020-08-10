import yaml, traceback, sys, json, inspect

from typing import Dict
from flask import Flask, Config, jsonify

class LibvirtHost(dict):
    def __init__(self, *args, **kwargs):
        if 'config' in kwargs.keys():
            config = kwargs.pop('config')
            self.update(config)
        self.update(*args, **kwargs)
        if 'type' in self.keys() and self['type'] == 'qemu+ssh':
            self['uri'] = f"{self['type']}://{self['username']}@{self['address']}/system?keyfile=/config/key/id_rsa.pub"

class LibvirtConfig(Config):
    hosts = []

    def from_yaml(self, configFile: str):
        with open(configFile) as file:
            self.rawConfig = yaml.load(file, Loader=yaml.FullLoader)
        for key, value in self.rawConfig.items():
            self[key] = value

def create_app():
    Flask.config_class = LibvirtConfig
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_yaml(configFile='/config/config.yaml')

    with app.app_context():
        # Include our Routes
        from . import routes

        return app
