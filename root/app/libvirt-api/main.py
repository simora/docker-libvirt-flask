import yaml, traceback, sys, json, inspect

from typing import Dict
from flask import Flask, jsonify
app = Flask(__name__)

class LibvirtHost(dict):
    def __init__(self, *args, **kwargs):
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


@app.errorhandler(Exception)
def handle_exception(e):
    etype, value, tb = sys.exc_info()
    print(traceback.print_exception(etype, value, tb))
    resp = {}
    resp['config'] = Config(configFile='/config/config.yaml').to_dict()
    resp['error'] = str(traceback.format_exc())
    return jsonify(resp), 500

@app.route("/")
def hello():
    return "<h1 style='color:blue'>Welcome to the Libvirt Flask API</h1>"

@app.route("/info")
def info():
    if len(app.config['hosts']) > 0:
        return f"<h1 style='color:blue'>Name: {app.config['hosts'][0].name}</h1>"

if __name__ == "__main__":
    app.config.update(Config(configFile='/config/config.yaml').to_dict())
    app.run(host='0.0.0.0')
