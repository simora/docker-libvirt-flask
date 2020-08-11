import yaml, traceback, sys, json, inspect

from typing import Dict
from flask import Flask, Config, jsonify

class LibvirtHost(dict):
    def __init__(self, *args, **kwargs):
        if 'config' in kwargs.keys():
            config = kwargs.pop('config')
            self.update(config)
        self.update(*args, **kwargs)
        if 'type' in self.keys():
            if self['type'] == 'qemu+ssh':
                self['uri'] = f"{self['type']}://{self['username']}@{self['address']}/system?keyfile=/config/key/id_rsa.pub"
            elif: self['type'] == 'socket':
                self['uri'] = None
    @classmethod
    def fromdict(cls, datadict):
        return cls(datadict.items())

class LibvirtConfig(Config):
    def from_yaml(self, configFile: str):
        with open(configFile) as file:
            self.rawConfig = yaml.load(file, Loader=yaml.FullLoader)
        for key, value in self.rawConfig.items():
            if key.lower() == 'hosts' and len(value) > 0:
                for host in value:
                    if 'hosts' not in self.keys():
                        self['hosts'] = []
                    self['hosts'].append(LibvirtHost.fromdict(host))
            else:
                self[key] = value

def create_app():
    Flask.config_class = LibvirtConfig
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_yaml(configFile='/config/config.yaml')

    with app.app_context():
        # Include our Routes
        from . import routes

        return app
