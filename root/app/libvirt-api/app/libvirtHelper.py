import yaml, traceback, sys, json, inspect
import libvirt

from typing import Dict
from xml.dom import minidom
from flask import Config

class LibvirtHost(dict):
    def __init__(self, *args, **kwargs):
        if 'config' in kwargs.keys():
            config = kwargs.pop('config')
            self.update(config)
        self.update(*args, **kwargs)
        if 'type' in self.keys():
            if self['type'] == 'qemu+ssh':
                self['uri'] = f"{self['type']}://{self['username']}@{self['address']}/system?keyfile=/config/key/id_rsa"
            elif self['type'] == 'socket':
                self['uri'] = None
    @classmethod
    def fromdict(cls, datadict):
        return cls(datadict.items())

class LibvirtConfig(Config):
    def from_yaml(self, configFile: str):
        with open(configFile) as file:
            self.rawConfig = yaml.load(file, Loader=yaml.FullLoader)
        for key, value in self.rawConfig.items():
            if key.lower() == 'hosts' and len(value) > 0:
                for host in value:
                    if 'hosts' not in self.keys():
                        self['hosts'] = []
                    self['hosts'].append(LibvirtHost.fromdict(host))
            else:
                self[key] = value

def get_conn(uri: str, rw: bool = False):
    if rw:
        conn = libvirt.open(uri)
    else:
        conn = libvirt.openReadOnly(uri)
    return conn
def get_capabilities(conn):
    capsXML = conn.getCapabilities()
    return minidom.parseString(capsXML)

def get_topology(host: LibvirtHost):
    try:
        conn = get_conn(host['uri'])
    except:
        return f"Failed to connect to host {host['name']}", 500
    try:
        caps = get_capabilities(conn)
    except libvirt.libvirtError:
        return f"Failed to request capabilities for host {host['name']}", 500

    host = caps.getElementsByTagName('host')[0]
    cells = host.getElementsByTagName('cells')[0]
    uuid = host.getElementsByTagName('uuid')[0].firstChild.nodeValue
    total_cpus = cells.getElementsByTagName('cpu').length

    socketIds = []
    siblingsIds = []

    socketIds = [
        proc.getAttribute('socket_id')
        for proc in cells.getElementsByTagName('cpu')
        if proc.getAttribute('socket_id') not in socketIds
    ]

    siblingsIds = [
        proc.getAttribute('siblings')
        for proc in cells.getElementsByTagName('cpu')
        if proc.getAttribute('siblings') not in siblingsIds
    ]
    response = {
        "NUMA nodes": cells.getAttribute('num'),
        "Sockets": len(set(socketIds)),
        "Cores": len(set(siblingsIds)),
        "Threads": total_cpus,
        "UUID" : uuid
    }
    return response, 200

def get_domains(host: LibvirtHost):
    try:
        conn = get_conn(host['uri'])
    except:
        return f"Failed to connect to host {host['name']}", 500

    getdomResult = {
        'running': [],
        'not running': []
    }
    domains = conn.listAllDomains(0)
    if len(domains) != 0:
        for dom in domains:
            state, reason = dom.state()
            if state == libvirt.VIR_DOMAIN_RUNNING:
                getdomResult['running'].append({'Name': dom.name(), 'UUID': dom.UUIDString()})
            else:
                getdomResult['not running'].append({'Name': dom.name(), 'UUID': dom.UUIDString()})
    return getdomResult, 200

def get_domain(host: LibvirtHost, uuid: str):
    try:
        conn = get_conn(host['uri'])
    except:
        return f"Failed to connect to host {host['name']}", 500
    getdomResult = {}
    dom = conn.lookupByUUID(uuid)
    if dom == None:
        return f"Failed to get domain {uuid}", 500
    getdomResult['name'] = dom.name()
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        getdomResult['state'] = 'running'
    else:
        getdomResult['state'] = 'not_running'
    return getdomResult, 200
