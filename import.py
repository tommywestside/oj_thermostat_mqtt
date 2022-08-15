import requests
import yaml

BASE_URL = 'https://mythermostat.info'

LOGIN_URL = '/api/authenticate/user'
THERMOSTATS_URL = '/api/thermostats'
# /api/thermostats?sessionid=s0fgZ_kIWUmJ0PDYVAwGaA

with open("secrets.yaml", "r") as stream:
    try:
        secrets_yaml = yaml.safe_load(stream)
        username = secrets_yaml['username']
        password = secrets_yaml['password']
    except yaml.YAMLError as exc:
        print(exc)


session_requests = requests.session()


login_payload = {
	"Username": username,
    "Email": username,
	"Password": password,
    "Application": 0,
}

result = session_requests.post(
	BASE_URL + LOGIN_URL,
	data = login_payload,
	headers = dict(referer=BASE_URL + LOGIN_URL)
)

login_return = result.json()

print(result.text)
sessionID = login_return.get('SessionId')

thermostats_url_full = BASE_URL + THERMOSTATS_URL + '?sessionid=' + sessionID

result_thermostats = session_requests.get(thermostats_url_full)

print(result_thermostats.text)

thermostats_data = result_thermostats.json()

groups = thermostats_data.get('Groups')

for group in groups:
    for thermostats in group.get('Thermostats'):
        print(thermostats.get('SerialNumber'))
        print(thermostats.get('Temperature') / 100)
