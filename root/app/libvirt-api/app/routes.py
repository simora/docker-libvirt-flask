import yaml, traceback, sys, json, inspect
from .helper import *
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
    response = []
    for host in app.config['hosts']:
        retVal, code = get_topology(host)
        response.append({"Return": retVal, "Code": code})
    return jsonify(response), 200

@app.route("/list")
def list():
    response = []
    for host in app.config['hosts']:
        retVal, code = get_domains(host)
        response.append({"Host": host['name'], "Domains": retVal})
    return jsonify(response), 200

@app.route('/host/<int:id>')
def domain(id: int):
    response = []
    host = app.config['hosts'][id] if id < len(app.config['hosts']) else None
    if host != None:
        response, code = get_domains(host)
        return jsonify(response), code
    return 500

@app.route('/host/<int:id>/domain/<string:uuid>')
def domain(id: int, uuid: str):
    response = []
    host = app.config['hosts'][id] if id < len(app.config['hosts']) else None
    if host != None:
        response, code = get_domain(host, uuid)
        return jsonify(response), code
    return 500
