import yaml, traceback, sys

from typing import Dict
from flask import Flask, jsonify
app = Flask(__name__)

class LibvirtHost:
    def __init__(self, config: Dict[str, str]):
        try:
            if 'type' in config.keys() and 'type' == 'qemu+ssh':
                self.name = config['name']
                self.type = config['type']
                self.username = config['username']
                self.address = config['address']
                self.uri = f'{self.type}://{self.username}@{self.address}/system?keyfile=/config/key/id_rsa.pub'
        except Exception as e:
            return e
        return self

class Config(object):
    hosts = []
    def __init__(self, configFile: str):
        with open(configFile) as file:
            self.rawConfig = yaml.load(file, Loader=yaml.FullLoader)
        if 'hosts' in self.rawConfig.keys():
            for host in self.rawConfig['hosts']:
                self.hosts.append(LibvirtHost(config=host))
        return self
    def to_dict(self):
        retVal = {}
        retVal['hosts'] = self.hosts
        return retVal


@app.errorhandler(Exception)
def handle_exception(e):
    etype, value, tb = sys.exc_info()
    print(traceback.print_exception(etype, value, tb))
    return jsonify(error=str(traceback.format_exc())), 500

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
