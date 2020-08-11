import libvirt
from . import LibvirtHost
from xml.dom import minidom

def get_conn(uri: str, rw: bool = False):
    if rw:
        conn = libvirt.open(uri)
    else:
        conn = libvirt.openReadOnly(uri)
    return conn
def get_capabilities(conn):
    capXML = conn.getCapabilities()
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
        "Threads": total_cpus
    }
    return response, 200
