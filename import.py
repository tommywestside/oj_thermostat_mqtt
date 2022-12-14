import requests
import yaml
import paho.mqtt.client as mqtt
import time
import json
import sched
import datetime

current_temperature_c = {}
current_temperature_f = {}
read_current_temp = {}
read_set_temp = {}
min_temp = {}
heating = {}
online = {}
temperature_c = {}
temperature_f = {}
temperature_has_changed = {}
weekday_schedules = {}
next_scheduled_time = {}
raw_data = {}
serials = []
sessionID = ""
s = sched.scheduler(time.time, time.sleep)

with open("/data/config.yaml", "r") as stream:
    try:
        secrets_yaml = yaml.safe_load(stream)
        username = secrets_yaml['username']
        password = secrets_yaml['password']
        mqttUser = secrets_yaml['mqttUser']
        mqttPassword = secrets_yaml['mqttPassword']
        brokerURL = secrets_yaml['brokerURL']
        brokerPort = secrets_yaml['brokerPort']
        clientName = secrets_yaml['clientName']
        BASE_URL = secrets_yaml['BASE_URL']
        LOGIN_URL = secrets_yaml['LOGIN_URL']
        THERMOSTATS_URL = secrets_yaml['THERMOSTATS_URL']
        THERMOSTATS_SET_URL = secrets_yaml['THERMOSTATS_SET_URL']
        MQTT_BASE_TOPIC = secrets_yaml['MQTT_BASE_TOPIC']
    except yaml.YAMLError as exc:
        print(exc)

def on_connect(client, userdata, flags, rc):  
    print("MQTT - Connected with result code {0}".format(str(rc)))  

def on_message(client, userdata, msg): 
    print("MQTT - Message received-> " + msg.topic + " " + str(msg.payload.decode("utf-8")))
    for serial in serials: 
        if (msg.topic == f"home/sensor/0x{serial}/temperature/set"):
            new_temperature = msg.payload.decode("utf-8")
            update_custom_temperature(new_temperature, serial, client)
        if (msg.topic == f"home/sensor/0x{serial}/state/set"):
            state_value = msg.payload.decode("utf-8")
            update_state(state_value, serial, client)

def update_custom_temperature(new_temperature, serial, client):
    print(f'THERMOSTAT - update device {serial} to new temperature: {new_temperature}')
    set_temperature(int(new_temperature), serial)
    update_thermostats(sessionID, client)
    update_mqtt(client)

def update_state(state_value, serial, client):
    print(f'THERMOSTAT - switch heating {"on" if state_value == 1 else "off"}')
    # set temperature +5 F if switched on
    if (state_value == 'heat'):
        set_temperature(current_temperature_f[serial] + 5, serial)
    # set temperature to minimum temp if switched off
    if (state_value == 'off'):
        set_temperature(min_temp[serial], serial)
    if (state_value == 'auto'):
        set_thermostat_auto(serial)
    update_thermostats(sessionID, client)
    update_mqtt(client)

def set_thermostat_auto(serial):
    print(f'THERMOSTAT - setting thermostat {serial} to auto schedule')
    url = f'{BASE_URL}{THERMOSTATS_SET_URL}?sessionid={sessionID}&serialnumber={serial}'
    payload = '{"RegulationMode":1,"VacationEnabled":false}'
    print("HTTP - POST payload to URL {url}:")
    print(payload)
    result = session_requests.post(
        url,
        data = payload,
        headers = {'Content-Type': 'application/json; charset=utf-8'}
    )
    print(f'HTTP - Result: {result.text}')
    try:
        set_temp_return = result.json()
        success = set_temp_return.get('Success')
        return success
    except:
        print("Error HTTP request set thermostat auto")
        return -1

def set_temperature(temperature, serial):
    print(f'THERMOSTAT - setting thermostat {serial} to {temperature}')
    url = f'{BASE_URL}{THERMOSTATS_SET_URL}?sessionid={sessionID}&serialnumber={serial}'
    temperature_c = int((temperature - 32) * 5.0/9.0 * 100)
    next_event_time = next_scheduled_time[serial].strftime("%Y/%m/%d %H:%M:%S")
    print(next_event_time)
    # RegulationMode 2: set custom time until next regular event from schedule kicks in
    # RegulationMode 3: set custom time forever, ignoring schedule (we don't do that)
    payload = f'{{"ComfortTemperature":"{str(temperature_c)}","RegulationMode":2,"ComfortEndTime":"{next_event_time}","VacationEnabled":false}}'
    print("HTTP - POST payload to URL {url}:")
    print(payload)
    result = session_requests.post(
        url,
        data = payload,
        headers = {'Content-Type': 'application/json; charset=utf-8'}
    )
    print(f'HTTP - Result: {result.text}')
    try:
        set_temp_return = result.json()
        success = set_temp_return.get('Success')
        return success
    except:
        return -1
    

def connect_mqtt():
    client = mqtt.Client(clientName)
    client.username_pw_set(mqttUser, mqttPassword)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(brokerURL, brokerPort)
    global isConnected
    isConnected = True
    return client

def publish_thermostat(client, serial):

    topic = f'{MQTT_BASE_TOPIC}/0x' + serial + '/temperature'
    current_temperature_f_str = str('%.2f' % current_temperature_f[serial])
    current_temperature_c_str = str('%.2f' % current_temperature_c[serial])
    temperature_f_str = str('%.2f' % temperature_f[serial])
    temperature_c_str = str('%.2f' % temperature_c[serial])
    payload = f'''{{    "current_temperature_f": {current_temperature_f_str}, 
                        "current_temperature_c": {current_temperature_c_str},
                        "temperature_f": {temperature_f_str},
                        "temperature": {temperature_c_str} 
                }}'''
    result = client.publish(topic, payload)
    status = result[0]
    if status == 0:
        print(f"MQTT - Send `{payload}` to topic `{topic}`")
    else:
        print(f"Faled to send message to topic `{topic}`")
        isConnected = False

def publish_thermostat_data(client, serial): 
    topic = f'{MQTT_BASE_TOPIC}/0x' + serial + '/data'
    payload = json.dumps(raw_data[serial])
    result = client.publish(topic, payload)
    status = result[0]
    if status == 0:
        print(f"Send payload `{payload}` to topic `{topic}`")
    else:
        print(f"Faled to send message to topic `{topic}`")
        isConnected = False

def publish_termostat_state(client, serial):
    topic = f'{MQTT_BASE_TOPIC}/0x' + serial + '/state'
    payload = f'''{{"power": "{heating[serial]}"}}'''
    result = client.publish(topic, payload)
    status = result[0]
    if status == 0:
        print(f"Send `{payload}` to topic `{topic}`")
    else:
        print(f"Faled to send message to topic `{topic}`")
        isConnected = False

session_requests = requests.session()

login_payload = {
	"Username": username,
    "Email": username,
	"Password": password,
    "Application": 0,
}

def login():
    print(f'HTTP - POST request to URL {BASE_URL + LOGIN_URL} with payload:')
    print(login_payload)
    result = session_requests.post(
        BASE_URL + LOGIN_URL,
        data = login_payload,
        headers = dict(referer=BASE_URL + LOGIN_URL)
    )
    print(f'HTTP - Result: {result.text}')
    try:
        login_return = result.json()
        SESSION_ID = login_return.get('SessionId')
        return SESSION_ID
    except:
        print("Error with login HTTP request")
        return -1

def getNextScheduledTime(serial):
    day = datetime.datetime.today().weekday() + 1
    time_now = datetime.datetime.today()
    time_tomorrow = time_now + datetime.timedelta(days=1)
    nextday = day + 1 if day < 7 else 1
    closest_next_event = time_now
    for schedule in weekday_schedules[serial]:
        if (schedule["WeekDayGrpNo"] == day or schedule["WeekDayGrpNo"] == nextday):
            for event in schedule["Events"]:
                event_time_array = event.get("Clock").split(":")
                # print(event_time_array)
                if (schedule["WeekDayGrpNo"] == day):
                    event_time = datetime.datetime(time_now.year, time_now.month, time_now.day, int(event_time_array[0]), int(event_time_array[1]), int(event_time_array[2]), 0)
                else:
                    event_time = datetime.datetime(time_tomorrow.year, time_tomorrow.month, time_tomorrow.day, int(event_time_array[0]), int(event_time_array[1]), int(event_time_array[2]), 0)
                event_active = event.get("Active")
                if (event_active and event_time > time_now):
                    if (closest_next_event > event_time or closest_next_event == time_now):
                        closest_next_event = event_time       
                    # print(f'{event} : {event_time} OK')
    print(f'THERMOSTAT - closest next event: {closest_next_event}')     
    return closest_next_event           


def update_thermostats(sessionID, client):
    # TODO: if regulationMode=2: use ComfortTemp, if =1 use below
    print("THERMOSTAT - update thermostats")
    thermostats_url_full = BASE_URL + THERMOSTATS_URL + '?sessionid=' + sessionID
    result_thermostats = session_requests.get(thermostats_url_full)
    print(result_thermostats.text)
    thermostats_data = result_thermostats.json()
    groups = thermostats_data.get('Groups')
    for group in groups:
        for thermostat in group.get('Thermostats'):
            serial = thermostat.get('SerialNumber')
            read_current_temp = thermostat.get('Temperature') / 100
            read_set_temp = thermostat.get('SetPointTemp') / 100
            read_custom_temp = thermostat.get('ComfortTemperature') / 100
            read_heating = thermostat.get("Heating")
            read_online = thermostat.get("Online")
            read_weekly_schedule = thermostat.get("Schedules")
            read_regulation_mode = thermostat.get("RegulationMode")
            read_min_temp = thermostat.get("MinTemp") / 100

            if (not serial in serials):
                serials.append(serial)
                client.subscribe(f"{MQTT_BASE_TOPIC}/0x{serial}/temperature/set")
                client.subscribe(f"{MQTT_BASE_TOPIC}/0x{serial}/state/set")
                temperature_has_changed[serial] = True

            current_temperature_c[serial] = read_current_temp
            current_temperature_f[serial] = current_temperature_c[serial]  * 1.8 + 32
            min_temp[serial] = read_min_temp * 1.8 + 32
            temperature_c[serial] = read_set_temp if read_regulation_mode == 1 else read_custom_temp
            temperature_f[serial] = temperature_c[serial]  * 1.8 + 32
            heating[serial] = "ON" if read_heating else "OFF"
            online[serial] = "Online" if read_online else "Offline"
            weekday_schedules[serial] = read_weekly_schedule
            next_scheduled_time[serial] = getNextScheduledTime(serial)
            raw_data[serial] = thermostat
            

def update_mqtt(client): 
    if(not isConnected):
        client = connect_mqtt()
    update_thermostats(sessionID, client)
    for serial in serials:
        if temperature_has_changed[serial]:
            publish_thermostat(client, serial)
            publish_thermostat_data(client, serial)
            publish_termostat_state(client, serial)

def run():
    client = connect_mqtt()
    global sessionID
    sessionID = login()

    client.loop_start()

    while(True):
        update_mqtt(client)
        time.sleep(60)

run()