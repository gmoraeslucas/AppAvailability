import os
import requests
import json
import urllib3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
from threading import Thread
from PIL import Image, ImageTk

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

ZABBIX_URL = os.getenv('ZABBIX_URL')
ZABBIX_TOKEN = os.getenv('ZABBIX_TOKEN')
auth_token = ZABBIX_TOKEN
group_name = "UMS/APP/PRD/REDE-SEGURANCA"

class ZabbixAvailabilityApp:
    def __init__(self, root):
        self.stop_processing = False
        self.root = root
        self.root.title("Zabbix Availability Checker")
        self.root.geometry("800x600")
        self.style = ttk.Style("morph")

        self.logo_image = Image.open("logo-seguros.png")
        self.logo_image = self.logo_image.resize((150, 80)) 
        self.logo_photo = ImageTk.PhotoImage(self.logo_image)

        self.canvas = ttk.Canvas(root, width=800, height=600)
        self.canvas.pack(expand=True, fill=BOTH)
        self.canvas.create_image(400, 75, image=self.logo_photo, anchor=CENTER) 
        self.rounded_rectangle(self.canvas, 200, 25, 600, 575, 20, fill="navy", width=3) 

        self.frame = ttk.Frame(self.canvas, padding=10)
        self.frame.place(relx=0.5, rely=0.5, anchor=CENTER)

        self.inner_frame = ttk.Frame(self.canvas)
        self.canvas.create_window(400, 350, window=self.inner_frame, anchor=CENTER) 

        self.year_label = ttk.Label(self.inner_frame, text="ANO:", style='TLabel')
        self.year_label.pack(pady=5, anchor=CENTER)

        self.year_entry = ttk.Entry(self.inner_frame, width=15, style='TEntry')
        self.year_entry.pack(pady=5, anchor=CENTER)

        self.month_label = ttk.Label(self.inner_frame, text="MÊS (1-12):", style='TLabel')
        self.month_label.pack(pady=5, anchor=CENTER)

        self.month_entry = ttk.Entry(self.inner_frame, width=15, style='TEntry')
        self.month_entry.pack(pady=5, anchor=CENTER)

        self.process_button = ttk.Button(
            self.inner_frame, 
            text="PROCESSAR", 
            command=self.start_processing, 
            bootstyle=(OUTLINE, SUCCESS), 
            width=15, 
            padding=(20, 5)
        )
        self.process_button.pack(pady=20, anchor=CENTER)

        self.stop_button = ttk.Button(
            self.inner_frame, 
            text="PARAR", 
            command=self.stop_processing_thread, 
            bootstyle=(OUTLINE, DANGER), 
            width=15, 
            padding=(20, 5)
        )
        self.stop_button.pack(pady=5, anchor=CENTER)

        self.progress = ttk.Progressbar(self.inner_frame, mode='determinate', bootstyle="info-striped", length=200)
        self.progress.pack(pady=10, anchor=CENTER)

        self.progress_label = ttk.Label(self.inner_frame, text="0%", style='TLabel')
        self.progress_label.pack(pady=5, anchor=CENTER)

        self.style.configure('TButton', font=('Helvetica', 9, 'bold'), padding=10)
        self.style.configure('TLabel', font=('Helvetica', 9, 'bold'), foreground='navy')
        self.style.configure('TEntry', font=('Helvetica', 9, 'bold'))

    def stop_processing_thread(self):
        self.stop_processing = True

    def rounded_rectangle(self, canvas, x1, y1, x2, y2, radius=25, **kwargs):
        points = [
            (x1 + radius, y1),
            (x2 - radius, y1),
            (x2, y1),
            (x2, y1 + radius),
            (x2, y2 - radius),
            (x2, y2),
            (x2 - radius, y2),
            (x1 + radius, y2),
            (x1, y2),
            (x1, y2 - radius),
            (x1, y1 + radius),
            (x1, y1)
        ]
        canvas.create_arc(x1, y1, x1 + 2*radius, y1 + 2*radius, start=90, extent=90, style="arc", **kwargs)
        canvas.create_arc(x2 - 2*radius, y1, x2, y1 + 2*radius, start=0, extent=90, style="arc", **kwargs)
        canvas.create_arc(x2 - 2*radius, y2 - 2*radius, x2, y2, start=270, extent=90, style="arc", **kwargs)
        canvas.create_arc(x1, y2 - 2*radius, x1 + 2*radius, y2, start=180, extent=90, style="arc", **kwargs)

        canvas.create_line(points[0], points[1], **kwargs)
        canvas.create_line(points[3], points[4], **kwargs)
        canvas.create_line(points[6], points[7], **kwargs)
        canvas.create_line(points[9], points[10], **kwargs)

    def update_progress(self, value):
        self.progress['value'] = value
        percentage = (value / self.progress['maximum']) * 100
        self.progress_label.config(text=f"{percentage:.2f}%")
        self.root.update_idletasks()

    def start_processing(self):
        year = self.year_entry.get()
        month = self.month_entry.get()

        if not year.isdigit() or len(year) != 4:
            messagebox.showerror("Erro", "Por favor, insira um ano válido com 4 dígitos.")
            return

        if not month.isdigit() or not (1 <= int(month) <= 12):
            messagebox.showerror("Erro", "Por favor, insira um mês válido (1-12).")
            return

        self.stop_processing = False 
        messagebox.showinfo("Iniciado", "Processamento iniciado com sucesso.") 
        processing_thread = Thread(target=self.run_processing, args=(int(year), int(month)))
        processing_thread.start()

    def run_processing(self, year, month):
        success = self.process_data(year, month)
        if success:
            messagebox.showinfo("Sucesso", "Processamento concluído com sucesso.")
        else:
            messagebox.showerror("Erro", "Ocorreu um erro durante o processamento.")

    def get_month_date_range(self, year, month):
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        return start_date, end_date

    def get_hostgroup_id(self, auth_token, group_name):
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
            result = response.json().get('result')
            if result:
                return result[0].get('groupid')
        except requests.exceptions.RequestException as e:
            self.log(f"Erro na solicitação HTTP: {e}")
        except json.JSONDecodeError as e:
            self.log(f"Erro ao decodificar JSON: {e}")
        return None

    def get_hosts(self, auth_token, groupid):
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
            self.log(f"Erro na solicitação HTTP: {e}")
        except json.JSONDecodeError as e:
            self.log(f"Erro ao decodificar JSON: {e}")
        return None
    def get_events(self, auth_token, hostid, start_date, end_date):
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
                self.log(f"Erro na solicitação HTTP: {e}")
            except json.JSONDecodeError as e:
                self.log(f"Erro ao decodificar JSON: {e}")

            current_date += timedelta(days=1)

        return total_events

    def calculate_availability(self, events, start_date, end_date):
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

    def calculate_group_availability(self, availabilities):
        if not availabilities:
            return 0
        return sum(availabilities) / len(availabilities)
    
    def process_data(self, year, month):
        try:
            host_data = []
            pabx_hosts = []
            firewall_hosts = []
            switch_hosts = []
            output_data = {}

            start_date, end_date = self.get_month_date_range(year, month)

            if auth_token:
                groupid = self.get_hostgroup_id(auth_token, group_name)
                if not groupid:
                    raise ValueError(f"Falha ao obter o ID do grupo de hosts '{group_name}'")
                
                hosts = self.get_hosts(auth_token, groupid)
                if not hosts:
                    raise ValueError("Falha ao obter dados de hosts")
                
                self.progress['maximum'] = len(hosts)
                for i, host in enumerate(hosts):
                    if self.stop_processing: 
                        messagebox.showinfo("Parado", "Processamento interrompido pelo usuário.")
                        self.stop_processing = False 
                        self.update_progress(0)
                        return

                    hostid = host['hostid']
                    events = self.get_events(auth_token, hostid, start_date, end_date)
                    if events is None:
                        raise ValueError(f"Falha ao obter eventos para o host {host['name']}")
                    
                    if len(events) == 0:
                        availability = 100.0
                    else:
                        availability = self.calculate_availability(events, start_date, end_date)
                    
                    host_data.append({
                        "host": host['name'],
                        "availability": f"{availability:.4f}%"
                    })

                    if host['name'].startswith('S'):
                        switch_hosts.append(availability)
                    elif host['name'].startswith(('cluster', 'clt', 'R')):
                        pabx_hosts.append(availability)
                    elif host['name'].startswith('F'):
                        firewall_hosts.append(availability)

                    self.update_progress(i + 1)

            else:
                raise ValueError("Falha na autenticação")

            group_availability = {
                "PABX": f"{self.calculate_group_availability(pabx_hosts):.4f}%",
                "FIREWALL": f"{self.calculate_group_availability(firewall_hosts):.4f}%",
                "SWITCH": f"{self.calculate_group_availability(switch_hosts):.4f}%"
            }

            if not os.path.exists('data'):
                os.makedirs('data')

            filename = f"data/host_availability_{year}_{month:02d}.json"

            output_data["group_availability"] = group_availability
            output_data["hosts"] = host_data

            with open(filename, 'w') as f:
                json.dump(output_data, f, indent=4)

            self.progress['value'] = 0
            return True 

        except Exception as e:
            messagebox.showerror("Erro", str(e))
            self.progress['value'] = 0
            return False 



if __name__ == "__main__":
    root = ttk.Window()
    app = ZabbixAvailabilityApp(root)
    root.mainloop()