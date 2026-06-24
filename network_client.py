import socket
import threading
import Pyro5.api
from datetime import datetime

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class ChatNetworkClient:
    def __init__(self, my_name, server_ip, on_message_received):
        self.my_name = my_name
        self.server_ip = server_ip
        self.on_message_received = on_message_received
        
        self.server = None
        self.my_uri = None
        self.my_online = True
        self.daemon = None
        self.daemon_thread = None
        self.daemon_exception = None

    def connect(self):
        try:
            self.server = Pyro5.api.Proxy(f"PYRO:MessageServer@{self.server_ip}:9090")
            self.server._pyroBind()
        except Exception as e:
            raise Exception(f"Não foi possível conectar ao servidor.\n{e}")

        self.daemon_exception = None
        self.daemon_thread = threading.Thread(target=self._run_daemon, daemon=True)
        self.daemon_thread.start()

        import time as time_mod
        start_time = time_mod.time()
        while not self.my_uri:
            if self.daemon_exception:
                raise Exception(f"Falha ao iniciar o daemon local: {self.daemon_exception}")
            if time_mod.time() - start_time > 5.0:
                raise Exception("Tempo limite esgotado ao iniciar o daemon local.")
            time_mod.sleep(0.1)

        try:
            self.server.register_client(self.my_name)
            offline_msgs = self.server.login(self.my_name, self.my_uri)
            return offline_msgs
        except Exception as e:
            raise Exception(f"Erro de comunicação/login com o servidor:\n{e}")

    def _run_daemon(self):
        try:
            ip = get_local_ip()
            self.daemon = Pyro5.api.Daemon(host=ip, port=0)
            
            @Pyro5.api.expose
            class ClientNode(object):
                def __init__(self, client):
                    self.client = client
                
                def receive_message(self, sender, text, time):
                    self.client.on_message_received(sender, text, time)

            self.my_uri = self.daemon.register(ClientNode(self))
            self.daemon.requestLoop()
        except Exception as e:
            self.daemon_exception = e

    def send_message(self, target_name, text):
        now = datetime.now().strftime("%H:%M")
        pending = True
        if self.my_online:
            is_online, contact_uri = self.server.get_status(target_name)
            if is_online:
                try:
                    proxy = Pyro5.api.Proxy(contact_uri)
                    proxy.receive_message(self.my_name, text, now)
                    pending = False
                except Exception:
                    self.server.send_offline_message(self.my_name, target_name, text, now)
            else:
                self.server.send_offline_message(self.my_name, target_name, text, now)
        else:
            self.server.send_offline_message(self.my_name, target_name, text, now)
        return now, pending

    def toggle_status(self, online_state):
        self.my_online = online_state
        if self.my_online:
            return self.server.login(self.my_name, self.my_uri)
        else:
            self.server.logout(self.my_name)
            return []

    def get_status(self, name):
        return self.server.get_status(name)

    def ensure_login(self):
        if self.my_online:
            try:
                is_me_online, _ = self.server.get_status(self.my_name)
                if not is_me_online:
                    print(f"[DEBUG] Cliente '{self.my_name}' não registrado como online no servidor. Re-registrando...")
                    return self.server.login(self.my_name, self.my_uri)
            except Exception as e:
                print(f"[DEBUG] Erro ao verificar auto-registro no servidor: {e}")
        return None

    def close(self):
        if self.daemon:
            try:
                self.daemon.close()
            except:
                pass
