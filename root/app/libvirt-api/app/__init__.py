import yaml, traceback, sys, json, inspect

from typing import Dict
from flask import Flask, jsonify, g

class LibvirtHost(dict):
    def __init__(self, *args, **kwargs):
        if 'config' in kwargs.keys():
            config = kwargs.pop('config')
            self.update(config)
        self.update(*args, **kwargs)
        if 'type' in self.keys() and self['type'] == 'qemu+ssh':
            self['uri'] = f"{self['type']}://{self['username']}@{self['address']}/system?keyfile=/config/key/id_rsa.pub"

class Config(object):
    hosts = []

    def __init__(self, configFile: str):
        with open(configFile) as file:
            self.rawConfig = yaml.load(file, Loader=yaml.FullLoader)
        if 'hosts' in self.rawConfig.keys():
            for host in self.rawConfig['hosts']:
                self.hosts.append(LibvirtHost(config=host))

    def to_dict(self):
        retVal = {}
        retVal['hosts'] = self.hosts
        return retVal

def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.update(dict(
        HOST='localhost',
        PORT='80',
        DICT={'host':'localhost','port':'80'}
    ))

    with app.app_context():
        # Include our Routes
        from . import routes

        g.config = 'test'

        return app
