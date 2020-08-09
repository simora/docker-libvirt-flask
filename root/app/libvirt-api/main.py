import yaml, traceback, sys, json, inspect

from typing import Dict
from flask import Flask, jsonify
app = Flask(__name__)

class LibvirtHost(json.JSONEncoder):
    def __init__(self, config: Dict[str, str]):
        if 'type' in config.keys() and 'type' == 'qemu+ssh':
            self.name = config['name']
            self.type = config['type']
            self.username = config['username']
            self.address = config['address']
            self.uri = f'{self.type}://{self.username}@{self.address}/system?keyfile=/config/key/id_rsa.pub'
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return self.default(obj.to_json())
        elif not isinstance(obj, dict):
            d = dict(
                (key, value)
                for key, value in inspect.getmembers(obj)
                if not key.startswith("__")
                and not inspect.isabstract(value)
                and not inspect.isbuiltin(value)
                and not inspect.isfunction(value)
                and not inspect.isgenerator(value)
                and not inspect.isgeneratorfunction(value)
                and not inspect.ismethod(value)
                and not inspect.ismethoddescriptor(value)
                and not inspect.isroutine(value)
            )
            return self.default(d)
        return obj

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
