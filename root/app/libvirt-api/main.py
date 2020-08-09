import yaml, traceback, sys, json, inspect

from typing import Dict
from flask import Flask, jsonify
app = Flask(__name__)

class LibvirtHost(dict):
    def __init__(self, *args, **kwargs):
        if 'type' in kwargs.keys() and kwargs['type'] == 'qemu+ssh':
            kwargs['uri'] = f"{kwargs['type']}://{kwargs['username']}@{kwargs['address']}/system?keyfile=/config/key/id_rsa.pub"
            self.update(*args, **kwds)

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
    resp = Config(configFile='/config/config.yaml').to_dict()
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
