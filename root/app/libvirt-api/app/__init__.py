from flask import Flask
from .libvirtHelper import *

def create_app():
    Flask.config_class = LibvirtConfig
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_yaml(configFile='/config/config.yaml')
    for i, host in enumerate(app.config['hosts']):
        topology = get_topology(host)
        if isinstance(topology, type(dict)):
            app.config['hosts'][i].update(topology)

    with app.app_context():
        # Include our Routes
        from . import routes

        return app
