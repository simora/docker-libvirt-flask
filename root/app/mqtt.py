import yaml, traceback, sys, json, inspect, asyncio, os, logging
import libvirt

from contextlib import AsyncExitStack, asynccontextmanager
from asyncio_mqtt import Client, MqttError
from typing import Dict
from slugify import slugify

MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_PORT = os.getenv('MQTT_PORT') if os.getenv('MQTT_PORT') is not None else 1883
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_TLS_CONTEXT = os.getenv('MQTT_TLS_CONTEXT')
MQTT_PROTOCOL = os.getenv('MQTT_PROTOCOL')
MQTT_CLIENT_ID = os.getenv('MQTT_CLIENT_ID')
DEBUG = True if os.getenv('DEBUG') is not None else False
ANNOUNCE_INTERVAL = 300
STATE_PUBLISH_INTERVAL = 10


logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.WARNING,
    format='%(levelname)7s: %(message)s',
    stream=sys.stdout,
)
LOG = logging.getLogger('')

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
    @classmethod
    def from_yaml(cls, configFile: str):
        datadict = {}
        with open(configFile) as file:
            rawConfig = yaml.load(file, Loader=yaml.FullLoader)
        for key, value in rawConfig.items():
            if key.lower() == 'hosts' and len(value) > 0:
                for host in value:
                    if 'hosts' not in datadict.keys():
                        datadict['hosts'] = []
                    datadict['hosts'].append(LibvirtHost.from_dict(host))
            else:
                datadict[key] = value
        return cls(datadict.items())

def get_conn(uri: str, rw: bool = False):
    if rw:
        conn = libvirt.open(uri)
    else:
        conn = libvirt.openReadOnly(uri)
    return conn

def get_domains(conn):
    getDomResult = []
    domains = conn.listAllDomains(0)
    if len(domains) == 0:
        return None
    for dom in domains:
        state, reason = dom.state()
        if state == libvirt.VIR_DOMAIN_RUNNING:
            getDomResult.append({'Name': dom.name(), 'UUID': dom.UUIDString(), 'state': 1})
        else:
            getDomResult.append({'Name': dom.name(), 'UUID': dom.UUIDString(), 'state': 0})
    return getDomResult

def get_domain(conn, name: str):
    getdomResult = {}
    dom = conn.lookupByName(name)
    if dom == None:
        return None
    getdomResult['name'] = dom.name()
    domState, reason = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        getdomResult['state'] = 1
    else:
        getdomResult['state'] = 0
    return getdomResult

def destroy_domain(conn, name: str):
    dom = conn.lookupByName(name)
    if dom == None:
        return False
    domState = dom.state()
    if domState not in [libvirt.VIR_DOMAIN_SHUTOFF, libvirt.VIR_DOMAIN_SHUTDOWN, libvirt.VIR_DOMAIN_NOSTATE]:
        if dom.destroy() < 0:
            return False
    return True

def shutdown_domain(conn, name: str):
    dom = conn.lookupByName(name)
    if dom == None:
        return False
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        if dom.shutdown() < 0:
            return False
    elif domState not in [libvirt.VIR_DOMAIN_SHUTOFF, libvirt.VIR_DOMAIN_SHUTDOWN, libvirt.VIR_DOMAIN_NOSTATE]:
        if dom.destroy() < 0:
            return False
    return True

def start_domain(conn, name: str):
    dom = conn.lookupByName(name)
    if dom == None:
        return None
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_PAUSED:
        if dom.resume() < 0:
            return False
    elif domState != libvirt.VIR_DOMAIN_RUNNING:
        if dom.create() < 0:
            return False
    return True

async def main():
    reconnect_interval = 3  # [seconds]
    config = LibvirtConfig.from_yaml("/config/config.yaml")
    while True:
        try:
            await mqtt_client(config)
        except MqttError as error:
            LOG.info(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        finally:
            await asyncio.sleep(reconnect_interval)

async def mqtt_client(config: LibvirtConfig):
    async with AsyncExitStack() as stack:
        LOG.info('Config below:')
        LOG.info(json.dumps(config, indent=2))
        # Keep track of the asyncio tasks that we create, so that
        # we can cancel them on exit
        tasks = set()
        stack.push_async_callback(cancel_tasks, tasks)

        # Connect to the MQTT broker
        client = Client(
            hostname = MQTT_HOST,
            port = MQTT_PORT,
            username = MQTT_USERNAME,
            password = MQTT_PASSWORD,
            tls_context = MQTT_TLS_CONTEXT,
            protocol = MQTT_PROTOCOL,
            client_id = MQTT_CLIENT_ID
        )
        await stack.enter_async_context(client)

        connections = []

        for host in config['hosts']:
            conn = get_conn(host['uri'], rw = True)
            if conn is None:
                continue
            domains = get_domains(conn)
            if domains is None:
                continue
            connections.append(conn)
            topic_list = []
            for dom in domains:
                topic_announce = f"homeassistant/switch/{slugify(host['name'])}/{slugify(dom['Name'])}/config"
                topic_state = f"homeassistant/switch/{slugify(host['name'])}/{slugify(dom['Name'])}/state"
                topic_command = f"homeassistant/switch/{slugify(host['name'])}/{slugify(dom['Name'])}/set"
                topic_list.append((topic_announce, 0))
                topic_list.append((topic_state, 0))
                topic_list.append((topic_command, 0))

                # update_listener
                topic_filters = (
                    topic_state
                )
                manager = client.filtered_messages(topic_filters)
                messages = await stack.enter_async_context(manager)
                task = asyncio.create_task(update_listener(client, conn, dom, messages))
                tasks.add(task)
                await client.subscribe(topic_state)

                # announce
                task = asyncio.create_task(announce(client, dom, topic_announce, topic_state, topic_command))
                tasks.add(task)

                # state_publish
                task = asyncio.create_task(state_publish(client, conn, dom, topic_state))
                tasks.add(task)

                # state_listener
                topic_filters = (
                    topic_command
                )
                manager = client.filtered_messages(topic_filters)
                messages = await stack.enter_async_context(manager)
                task = asyncio.create_task(state_listener(client, conn, dom, messages, topic_state))
                tasks.add(task)

        await client.subscribe(topic_list)
        await asyncio.gather(*tasks)

async def announce(client, dom, topic_announce, topic_state, topic_command):
    while True:
        message = {
            "name": dom['Name'],
            "command_topic": topic_command,
            "state_topic": topic_state,
            "unique_id": slugify(dom['Name']),
            "optimistic": True
        }
        await client.publish(topic_announce, json.dumps(message), qos=1)
        await asyncio.sleep(ANNOUNCE_INTERVAL)

async def state_publish(client, conn, dom, topic_state):
    while True:
        domain = get_domain(conn, dom['Name'])
        if domain is None:
            raise Exception("Domain not found")
        message = 'ON' if domain['state'] == 1 else 'OFF'
        LOG.info(f"Publishing state of {dom['Name']} as {message}")
        await client.publish(topic_state, message, qos=1)
        await asyncio.sleep(STATE_PUBLISH_INTERVAL)

async def update_listener(client, conn, dom, messages):
    async for message in messages:
        LOG.info(f"Message for {dom['Name']} received on topic_state: {message.payload.decode()}")

async def state_listener(client, conn, dom, messages, topic_state):
    async for message in messages:
        domain = get_domain(conn, dom['Name'])
        if message.payload.decode() == "OFF" and domain['state'] == 1:
            LOG.info(f"Shutting down domain {dom['Name']}")
            shutdown_domain(conn, dom['Name'])
        elif message.payload.decode() == "ON" and domain['state'] == 0:
            LOG.info(f"Creating domain {dom['Name']}")
            start_domain(conn, dom['Name'])
        elif message.payload.decode() == "DIE":
            LOG.info(f"Destroying domain {dom['Name']}")
            destroy_domain(conn, dom['Name'])
        await asyncio.sleep(2)
        domain = get_domain(conn, dom['Name'])
        message = 'ON' if domain['state'] == 1 else 'OFF'
        LOG.info(f"Publishing state of {dom['Name']} as {message}")
        await client.publish(topic_state, message, qos=1)


async def cancel_tasks(tasks):
    for task in tasks:
        if task.done():
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

if __name__ == '__main__':
    asyncio.run(main())
