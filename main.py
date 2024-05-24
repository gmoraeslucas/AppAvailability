import os
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

ZABBIX_URL = os.getenv('ZABBIX_URL')
ZABBIX_TOKEN = os.getenv('ZABBIX_TOKEN')
auth_token = ZABBIX_TOKEN

group_name = "UMS/APP/PRD/REDE-SEGURANCA"
year = int(input("Digite o ano (ex. 2024): "))
month = int(input("Digite o mês (1-12): "))
host_data = []
pabx_hosts = []
firewall_hosts = []
switch_hosts = []
output_data = {}

def get_month_date_range(year, month):
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
    return start_date, end_date

start_date, end_date = get_month_date_range(year, month)

def get_hostgroup_id(auth_token, group_name):
    payload = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {
            "output": ["groupid"],
            "filter": {
                "name": [group_name]
            }
        },
        "auth": auth_token,
        "id": 1
    }
    try:
        response = requests.post(ZABBIX_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json-rpc'}, verify=False)
        response.raise_for_status() 
        print(f"Grupos de hosts: {response.text}")
        result = response.json().get('result')
        if result:
            return result[0].get('groupid')
    except requests.exceptions.RequestException as e:
        print(f"Erro na solicitação HTTP: {e}")
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON: {e}")
    return None

def get_hosts(auth_token, groupid):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "name", "status"],
            "groupids": groupid,
            "filter": {
                "status": "0"
            }
        },
        "auth": auth_token,
        "id": 1
    }
    try:
        response = requests.post(ZABBIX_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json-rpc'}, verify=False)
        response.raise_for_status()
        return response.json().get('result')
    except requests.exceptions.RequestException as e:
        print(f"Erro na solicitação HTTP: {e}")
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON: {e}")
    return None

def get_events(auth_token, hostid, start_date, end_date):
    total_events = []

    current_date = start_date
    while current_date <= end_date:
        period_start = current_date.replace(hour=0, minute=0, second=0)
        period_end = current_date.replace(hour=23, minute=59, second=59)

        payload = {
            "jsonrpc": "2.0",
            "method": "event.get",
            "params": {
                "output": ["eventid", "clock", "value"],
                "hostids": hostid,
                "time_from": int(period_start.timestamp()),
                "time_till": int(period_end.timestamp()),
                "sortfield": ["clock"],
                "sortorder": "ASC",
                "value": [0, 1] 
            },
            "auth": auth_token,
            "id": 1
        }
        try:
            response = requests.post(ZABBIX_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json-rpc'}, verify=False)
            response.raise_for_status()
            total_events.extend(response.json().get('result'))
        except requests.exceptions.RequestException as e:
            print(f"Erro na solicitação HTTP: {e}")
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON: {e}")

        current_date += timedelta(days=1)

    return total_events

def calculate_availability(events, start_date, end_date):
    if not events:
        return 100.0

    total_time = int(end_date.timestamp()) - int(start_date.timestamp())
    down_time = 0
    last_down_time = None

    for event in events:
        if event['value'] == '1': 
            last_down_time = int(event['clock'])
        elif event['value'] == '0' and last_down_time:
            down_time += int(event['clock']) - last_down_time
            last_down_time = None

    if last_down_time:
        down_time += int(end_date.timestamp()) - last_down_time

    uptime = total_time - down_time
    availability = (uptime / total_time) * 100
    return availability

if auth_token:
    groupid = get_hostgroup_id(auth_token, group_name)
    if groupid:
        hosts = get_hosts(auth_token, groupid)
        if hosts:
            print(f"Total de hosts: {len(hosts)}")
            for host in hosts:
                print(f"Processando host: {host['name']}")
                hostid = host['hostid']
                events = get_events(auth_token, hostid, start_date, end_date)
                if events is not None:
                    if len(events) == 0:
                        availability = 100.0
                    else:
                        availability = calculate_availability(events, start_date, end_date)
                    # Adicione os dados do host à lista com formatação para 4 casas decimais
                    host_data.append({
                        "host": host['name'],
                        "availability": f"{availability:.4f}%"
                    })
                    
                    # Classificar os hosts em grupos e acumular disponibilidade
                    if host['name'].startswith('S'):
                        switch_hosts.append(availability)
                    elif host['name'].startswith(('cluster', 'clt', 'R')):
                        pabx_hosts.append(availability)
                    elif host['name'].startswith('F'):
                        firewall_hosts.append(availability)
                else:
                    print(f"Falha ao obter eventos para o host {host['name']}")
        else:
            print("Falha ao obter dados de hosts")
    else:
        print(f"Falha ao obter o ID do grupo de hosts '{group_name}'")
else:
    print("Falha na autenticação")

def calculate_group_availability(availabilities):
    if not availabilities:
        return 0
    return sum(availabilities) / len(availabilities)

group_availability = {
    "PABX": f"{calculate_group_availability(pabx_hosts):.2f}%",
    "FIREWALL": f"{calculate_group_availability(firewall_hosts):.2f}%",
    "SWITCH": f"{calculate_group_availability(switch_hosts):.2f}%"
}

if not os.path.exists('data'):
    os.makedirs('data')

filename = f"data/host_availability_{year}_{month:02d}.json"

output_data["group_availability"] = group_availability

output_data["hosts"] = host_data

with open(filename, 'w') as f:
    json.dump(output_data, f, indent=4)