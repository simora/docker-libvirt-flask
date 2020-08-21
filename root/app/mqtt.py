import yaml, traceback, sys, json, inspect, asyncio
import libvirt

from contextlib import AsyncExitStack, asynccontextmanager
from random import randrange
from asyncio_mqtt import Client, MqttError
from typing import Dict
from xml.dom import minidom

ANNOUNCE_INTERVAL = 300
STATE_PUBLISH_INTERVAL = 60

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
    def from_dict(cls, datadict):
        return cls(datadict.items())

class LibvirtConfig(dict):
    def from_yaml(self, configFile: str):
        with open(configFile) as file:
            self.rawConfig = yaml.load(file, Loader=yaml.FullLoader)
        for key, value in self.rawConfig.items():
            if key.lower() == 'libvirt_hosts' and len(value) > 0:
                for host in value:
                    if 'hosts' not in self.keys():
                        self['hosts'] = []
                    self['hosts'].append(LibvirtHost.from_dict(host))
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
        return f"Failed to connect to host {host['name']}"
    try:
        caps = get_capabilities(conn)
    except libvirt.libvirtError:
        clean_and_return(conn, f"Failed to request capabilities for host {host['name']}")

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
    clean_and_return(conn, response)

def get_domains(host: LibvirtHost):
    try:
        conn = get_conn(host['uri'])
    except:
        return f"Failed to connect to host {host['name']}"

    getDomResult = None
    domains = conn.listAllDomains(0)
    if len(domains) != 0:
        getDomResult = []
        for dom in domains:
            state, reason = dom.state()
            if state == libvirt.VIR_DOMAIN_RUNNING:
                getDomResult.append({'Name': dom.name(), 'UUID': dom.UUIDString(), 'state': 1})
            else:
                getDomResult.append({'Name': dom.name(), 'UUID': dom.UUIDString(), 'state': 0})
    clean_and_return(conn, getDomResult)

def get_domain(host: LibvirtHost, name: str):
    try:
        conn = get_conn(host['uri'])
    except:
        return f"Failed to connect to host {host['name']}"
    getdomResult = None
    dom = conn.lookupByName(name)
    if dom == None:
        clean_and_return(conn, f"Failed to get domain {name}")
    getdomResult['name'] = dom.name()
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        getdomResult['state'] = 1
    else:
        getdomResult['state'] = 0
    clean_and_return(conn, getdomResult)

def set_domain(host: LibvirtHost, name: str, state: int):
    try:
        conn = get_conn(host['uri'], rw = True)
    except:
        return f"Failed to connect to host {host['name']}"
    dom = conn.lookupByName(name)
    retVal = None
    if dom == None:
        clean_and_return(conn, f"Failed to get domain {name}")
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        curState = 1
    else:
        curState = 0
    if state == curState:
        clean_and_return(conn, {'Name': dom.name(), 'UUID': dom.UUIDString(), 'state': curState})
    else:
        if curState == 0 and state == 1:
            if dom.create() < 0:
                clean_and_return(conn, f"Failed to start domain {name}")
        elif curState == 1 and state == 0:
            if dom.destroy() < 0:
                clean_and_return(conn, f"Failed to stop domain {name}")
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        curState = 1
    else:
        curState = 0
    if state == curState:
        clean_and_return(conn, {'Name': dom.name(), 'UUID': dom.UUIDString(), 'state': curState})
    else:
        clean_and_return(conn, f"Failed to set state of domain {name}")

async def main():
    reconnect_interval = 3  # [seconds]
    config = LibvirtConfig().from_yaml("/config/config.yaml")
    while True:
        try:
            await mqtt_client(config)
        except MqttError as error:
            print(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        finally:
            await asyncio.sleep(reconnect_interval)

async def mqtt_client(config: LibvirtConfig):
    async with AsyncExitStack() as stack:
        # Keep track of the asyncio tasks that we create, so that
        # we can cancel them on exit
        tasks = set()
        stack.push_async_callback(cancel_tasks, tasks)

        # Connect to the MQTT broker
        client = Client(config['mqtt_host'])
        await stack.enter_async_context(client)


        """
        # You can create any number of topic filters
        topic_filters = (
            "floors/+/humidity",
            "floors/rooftop/#"
            # 👉 Try to add more filters!
        )
        for topic_filter in topic_filters:
            # Log all messages that matches the filter
            manager = client.filtered_messages(topic_filter)
            messages = await stack.enter_async_context(manager)
            template = f'[topic_filter="{topic_filter}"] {{}}'
            task = asyncio.create_task(log_messages(messages, template))
            tasks.add(task)

        # Messages that doesn't match a filter will get logged here
        messages = await stack.enter_async_context(client.unfiltered_messages())
        task = asyncio.create_task(log_messages(messages, "[unfiltered] {}"))
        tasks.add(task)

        # Subscribe to topic(s)
        # 🤔 Note that we subscribe *after* starting the message
        # loggers. Otherwise, we may miss retained messages.
        await client.subscribe("floors/#")

        # Publish a random value to each of these topics
        topics = (
            "floors/basement/humidity",
            "floors/rooftop/humidity",
            "floors/rooftop/illuminance",
            # 👉 Try to add more topics!
        )
        task = asyncio.create_task(post_to_topics(client, topics))
        tasks.add(task)
        """
        # Wait for everything to complete (or fail due to, e.g., network
        # errors)
        await asyncio.gather(*tasks)

async def announce():
    pass

async def state_publish():
    pass

async def update_listener():
    pass

async def state_listener():
    pass

if __name__ == '__main__':
    asyncio.run(main())
