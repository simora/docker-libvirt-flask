import yaml

from typing import Dict
from flask import Flask
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

@app.route("/")
def hello():
    return "<h1 style='color:blue'>Welcome to the Libvirt Flask API</h1>"

@app.route("/info")
def info():
    hosts = []
    if 'hosts' in config.keys():
        for host in config['hosts']:
            hosts.append(LibvirtHost(config=host))
    if hosts.length() > 0:
        return f"<h1 style='color:blue'>Name: {hosts[0].name}</h1>"
    return "No can"

if __name__ == "__main__":
    config = {}
    with open(r'/config/config.yaml') as file:
        # The FullLoader parameter handles the conversion from YAML
        # scalar values to Python the dictionary format
        config = yaml.load(file, Loader=yaml.FullLoader)

    app.run(host='0.0.0.0')
