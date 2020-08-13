import yaml, traceback, sys, json, inspect
from .libvirtHelper import *
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
        if 'UUID' not in host.keys():
            retVal, code = get_topology(host)
            response.append({"Return": retVal, "Code": code})
        else:
            response.append({"Cached": host})
    return jsonify(response), 200

@app.route("/list")
def list():
    response = []
    for host in app.config['hosts']:
        retVal, code = get_domains(host)
        response.append({"Host": host['name'], "Domains": retVal})
    return jsonify(response), 200

@app.route('/host/<string:hostUUID>')
def host_get(hostUUID: str):
    response = []
    host = next((i for i in app.config['hosts'] if 'UUID' in i.keys() and i['UUID'] == hostUUID), None)
    if host != None:
        response, code = get_domains(host)
        return jsonify(response), code
    return 500

@app.route('/host/<string:hostUUID>/domain/<string:domUUID>')
def domain_get(hostUUID: str, domUUID: str):
    host = next((i for i in app.config['hosts'] if 'UUID' in i.keys() and i['UUID'] == hostUUID), None)
    if host != None:
        response, code = get_domain(host, domUUID)
        return jsonify(response), code
    return 500
