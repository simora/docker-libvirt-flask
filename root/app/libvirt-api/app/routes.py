import yaml, traceback, sys, json, inspect
import .helper
from flask import Flask, jsonify, g
from flask import current_app as app

@app.errorhandler(Exception)
def handle_exception(e):
    etype, value, tb = sys.exc_info()
    print(traceback.print_exception(etype, value, tb))
    resp = {}
    resp['error'] = str(traceback.format_exc())
    return jsonify(resp), 500

@app.route("/")
def hello():
    return "<h1 style='color:blue'>Welcome to the Libvirt Flask API</h1>"

@app.route("/info")
def info():
    for host in app.config['hosts']:
        response, code = get_topology(host)
        if code == 200:
            return jsonify(response), code
