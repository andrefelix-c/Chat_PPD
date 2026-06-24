import Pyro5.api
import pika
import socket
import threading
import json
from datetime import datetime
import traceback

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

@Pyro5.api.expose
class MessageServer(object):
    def __init__(self):
        self.online_users = {}
        self.lock = threading.Lock()

    def _get_channel(self):
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters('127.0.0.1'))
            return conn, conn.channel()
        except Exception:
            conn = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            return conn, conn.channel()

    def register_client(self, client_name):
        try:
            with self.lock:
                conn, channel = self._get_channel()
                try:
                    queue_name = client_name.lower()
                    channel.queue_declare(queue=queue_name, durable=True)
                    print(f"[RabbitMQ] Fila verificada/criada para: {queue_name}")
                finally:
                    conn.close()
        except Exception as e:
            print(f"[ERRO] Falha ao registrar cliente '{client_name}': {e}")
            traceback.print_exc()
            raise Exception(f"Erro de conexão com o RabbitMQ no servidor: {e}")

    def login(self, client_name, uri):
        key = client_name.lower()
        self.online_users[key] = (client_name, uri)
        print(f"[{client_name}] entrou. URI: {uri}")
        
        messages = []
        try:
            with self.lock:
                conn, channel = self._get_channel()
                try:
                    while True:
                        method_frame, header_frame, body = channel.basic_get(queue=key, auto_ack=True)
                        if method_frame:
                            try:
                                msg = json.loads(body)
                                messages.append(msg)
                            except Exception as json_err:
                                print(f"[AVISO] Mensagem não-JSON na fila de {key}: {body}. Erro: {json_err}")
                                text_content = body
                                if isinstance(body, bytes):
                                    text_content = body.decode('utf-8', errors='ignore')
                                messages.append({
                                    "sender": "Sistema (Offline)",
                                    "text": text_content,
                                    "time": datetime.now().strftime("%H:%M"),
                                    "pending": False
                                })
                        else:
                            break
                finally:
                    conn.close()
        except Exception as e:
            print(f"[ERRO] Falha no login/recuperação de mensagens de {client_name}: {e}")
            traceback.print_exc()
            raise Exception(f"Erro ao recuperar mensagens offline do RabbitMQ: {e}")
            
        if messages:
            print(f"Entregando {len(messages)} mensagens offline para {client_name}")
        return messages

    def logout(self, client_name):
        key = client_name.lower()
        if key in self.online_users:
            del self.online_users[key]
            print(f"[{client_name}] saiu.")

    def get_status(self, contact_name):
        key = contact_name.lower()
        if key in self.online_users:
            return True, self.online_users[key][1]
        return False, None

    def send_offline_message(self, sender, target, text, time):
        msg = {
            "sender": sender,
            "text": text,
            "time": time,
            "pending": False
        }
        try:
            with self.lock:
                conn, channel = self._get_channel()
                try:
                    queue_name = target.lower()
                    channel.queue_declare(queue=queue_name, durable=True)
                    channel.basic_publish(
                        exchange='',
                        routing_key=queue_name,
                        body=json.dumps(msg),
                        properties=pika.BasicProperties(
                            delivery_mode=pika.DeliveryMode.Persistent
                        )
                    )
                finally:
                    conn.close()
            print(f"Mensagem offline de {sender} guardada para {target}")
        except Exception as e:
            print(f"[ERRO] Falha ao enviar mensagem offline de {sender} para {target}: {e}")
            traceback.print_exc()
            raise Exception(f"Erro ao salvar mensagem offline no RabbitMQ: {e}")

if __name__ == "__main__":
    ip = get_local_ip()
    port = 9090
    daemon = Pyro5.api.Daemon(host=ip, port=port)
    server_instance = MessageServer()
    uri = daemon.register(server_instance, "MessageServer")
    
    print("=" * 50)
    print(" Servidor de Mensagens Offline Iniciado ")
    print(f" IP do Servidor: {ip}")
    print("=" * 50)
    
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
