import yaml, traceback, sys, json, inspect
from .libvirtHelper import *
from flask import Flask, jsonify, g, request
from flask import current_app as app

DOMAIN_KEYS_PUT = ['name', 'state', 'host']
DOMAIN_KEYS_GET = ['name', 'host']

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
        response.append(host)
    return jsonify(response), 200

@app.route("/list")
def list_get():
    response = []
    for host in app.config['hosts']:
        retVal = get_domains(host)
        if isinstance(retVal, type([])):
            response.append({"Host": host['name'], "Domains": retVal})
        else:
            return jsonify(retVal), 500
    return jsonify(response), 200

@app.route('/dom/', methods = ['GET'])
def dom_get():
    reponse = None
    if all(arg in request.args for arg in DOMAIN_KEYS_GET):
        host = next((i for i in app.config['hosts'] if 'name' in i.keys() and i['name'] == request.args.get('host')), None)
        if host != None:
            response = get_domain(host, request.args.get('name'))
        else:
            response = f"No host {request.args.get('host')}"
    else:
        response = 'JSON is invalid or missing keys'
    if isinstance(response, type(dict)):
        return jsonify(response), 200
    else:
        return jsonify(response), 500

@app.route('/dom/', methods = ['PUT', 'POST', 'PATCH'])
def dom_put():
    content = request.json
    response = None
    if content != None:
        if all(key in content.keys() for key in DOMAIN_KEYS_PUT):
            host = next((i for i in app.config['hosts'] if 'name' in i.keys() and i['name'] == content['host']), None)
            retVal = set_domain(host, content['name'], content['state'])
            if retVal:
                return jsonify(f"Successfully set state of domain '{content['name']}' on host '{content['host']}' to state {content['state']}"), 200
            else:
                return jsonify(f"Failed to set state of domain '{content['name']}' on host '{content['host']}' to state {content['state']}"), 500
        else:
            response = 'JSON is invalid or missing keys'
    else:
        response = 'JSON not supplied or invalid'
    return jsonify(response), 500
