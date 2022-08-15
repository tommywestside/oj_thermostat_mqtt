import requests
import yaml
import paho.mqtt.client as mqtt
import time

BASE_URL = 'https://mythermostat.info'

LOGIN_URL = '/api/authenticate/user'
THERMOSTATS_URL = '/api/thermostats'

current_temperature_c = {}
current_temperature_f = {}
temperature_has_changed = {}
serials = []


with open("secrets.yaml", "r") as stream:
    try:
        secrets_yaml = yaml.safe_load(stream)
        username = secrets_yaml['username']
        password = secrets_yaml['password']
        mqttUser = secrets_yaml['mqttUser']
        mqttPassword = secrets_yaml['mqttPassword']
        brokerURL = secrets_yaml['brokerURL']
        brokerPort = secrets_yaml['brokerPort']
        clientName = secrets_yaml['clientName']
    except yaml.YAMLError as exc:
        print(exc)


def connect_mqtt():
	def on_connect(client, userdata, flags, rc):
		if rc == 0:
			print("Connected to MQTT Broker!")
		else:
			print("Failed to connect to MQTT Broker, return code %d\n", rc)

	client = mqtt.Client(clientName)
	client.username_pw_set(mqttUser, mqttPassword)
	client.on_connect = on_connect
	client.connect(brokerURL, brokerPort)
	return client

def publish_thermostat(client, serial):

    topic = 'home/sensor/0x' + serial + '/temperature'
    temperature_f_str = str('%.2f' % current_temperature_f[serial])
    temperature_c_str = str('%.2f' % current_temperature_c[serial])
    payload = '{ "temperature_f": ' + temperature_f_str + ', "temperature_c": ' + temperature_c_str + ' }'
    result = client.publish(topic, payload)
    status = result[0]
    if status == 0:
        print(f"Send `{payload}` to topic `{topic}`")
    else:
        print(f"Faled to send message to topic `{topic}`")
        print(result)


session_requests = requests.session()


login_payload = {
	"Username": username,
    "Email": username,
	"Password": password,
    "Application": 0,
}

def login():
    result = session_requests.post(
        BASE_URL + LOGIN_URL,
        data = login_payload,
        headers = dict(referer=BASE_URL + LOGIN_URL)
    )
    login_return = result.json()
    print(result.text)
    SESSION_ID = login_return.get('SessionId')
    return SESSION_ID


def update_thermostats(sessionID):
    thermostats_url_full = BASE_URL + THERMOSTATS_URL + '?sessionid=' + sessionID
    result_thermostats = session_requests.get(thermostats_url_full)
    print(result_thermostats.text)
    thermostats_data = result_thermostats.json()
    groups = thermostats_data.get('Groups')
    for group in groups:
        for thermostats in group.get('Thermostats'):
            serial = thermostats.get('SerialNumber')
            if (not serial in serials):
                serials.append(serial)
                temperature_has_changed[serial] = True
            else:
                if(thermostats.get('Temperature') / 100 != current_temperature_c[serial]):
                    temperature_has_changed[serial] = True
                else:
                    temperature_has_changed[serial] = False
            current_temperature_c[serial] = thermostats.get('Temperature') / 100
            current_temperature_f[serial] = current_temperature_c[serial]  * 1.8 + 32
            

def run():
    client = connect_mqtt()
    sessionID = login()
    while True:
        update_thermostats(sessionID)
        for serial in serials:
            if temperature_has_changed[serial]:
                publish_thermostat(client, serial)
        time.sleep(60)


run()