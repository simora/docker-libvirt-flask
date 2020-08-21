import yaml, traceback, sys, json, inspect, asyncio, os
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
            if key.lower() == 'hosts' and len(value) > 0:
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

def get_domains(conn):
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
    return getDomResult

def get_domain(conn, name: str):
    getdomResult = None
    dom = conn.lookupByName(name)
    if dom == None:
        return None
    getdomResult['name'] = dom.name()
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        getdomResult['state'] = 1
    else:
        getdomResult['state'] = 0
    return getdomResult

def set_domain(conn, name: str, state: int):
    dom = conn.lookupByName(name)
    if dom == None:
        return None
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        curState = 1
    else:
        curState = 0
    if state == curState:
        return {'Name': dom.name(), 'UUID': dom.UUIDString(), 'state': curState}
    else:
        if curState == 0 and state == 1:
            if dom.create() < 0:
                return None
        elif curState == 1 and state == 0:
            if dom.destroy() < 0:
                return None
    domState = dom.state()
    if domState == libvirt.VIR_DOMAIN_RUNNING:
        curState = 1
    else:
        curState = 0
    return {'Name': dom.name(), 'UUID': dom.UUIDString(), 'state': curState}

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
            if domains is not None:
                continue
            connections.append(conn)
            for dom in domains:
                topic_announce = f"homeassistant/switch/{slugify(host['name'])}/{slugify(dom['Name'])}/config"
                topic_state = f"homeassistant/switch/{slugify(host['name'])}/{slugify(dom['Name'])}/state"
                topic_command = f"homeassistant/switch/{slugify(host['name'])}/{slugify(dom['Name'])}/set"

                # update_listener
                topic_filters = (
                    topic_state
                )
                manager = client.filtered_messages(topic_filter)
                messages = await stack.enter_async_context(manager)
                task = asyncio.create_task(update_listener(client, conn, dom, messages))
                tasks.add(task)
                await client.subscribe(topic_state)

                # announce
                task = asyncio.create_task(announce(client, dom, topic_announce))
                tasks.add(task)

                # state_publish

                task = asyncio.create_task(state_publish(client, conn, dom, topic_announce, topic_state, topic_command))
                tasks.add(task)

        await asyncio.gather(*tasks)

async def announce(client, dom, topic_config, topic_state, topic_command):
    while True:
        message = {
            "name": dom['Name'],
            "command_topic": topic_command,
            "state_topic": topic_state
        }
        await client.publish(topic_config, json.dumps(message), qos=1)
        await asyncio.sleep(ANNOUNCE_INTERVAL)

async def state_publish(client, conn, dom, topic_state):
    while True:
        domain = get_domain(conn, dom['Name'])
        if domain is None:
            raise Exception("Domain not found")
        message = 'on' if domain['state'] == 1 else 'off'
        await client.publish(topic_state, message, qos=1)
        await asyncio.sleep(STATE_PUBLISH_INTERVAL)

async def update_listener(client, conn, dom, messages):
    async for message in messages:
        print(f"Message for {dom['Name']} received: {message.payload.decode()}")

async def state_listener():
    pass

if __name__ == '__main__':
    asyncio.run(main())
