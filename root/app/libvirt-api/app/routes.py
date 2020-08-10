import yaml, traceback, sys, json, inspect

from flask import Flask, jsonify, g
from flask import current_app as app

@app.errorhandler(Exception)
def handle_exception(e):
    etype, value, tb = sys.exc_info()
    print(traceback.print_exception(etype, value, tb))
    resp = {}
    with app.app_context():
        resp['config'] = g.config.to_dict()
    resp['error'] = str(traceback.format_exc())
    return jsonify(resp), 500

@app.route("/")
def hello():
    return "<h1 style='color:blue'>Welcome to the Libvirt Flask API</h1>"

@app.route("/info")
def info():
    with app.app_context():
        if len(g.config.hosts) > 0:
            return f"<h1 style='color:blue'>Name: {g.config.hosts[0]['name']}</h1>"
