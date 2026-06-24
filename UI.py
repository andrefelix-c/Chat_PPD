import tkinter as tk
from tkinter import simpledialog, messagebox
from datetime import datetime
import customtkinter as ctk
import os
import json
from network_client import ChatNetworkClient, get_local_ip

BG_DARK      = "#0C0E14"   
BG_PANEL     = "#161824"   
BG_CARD      = "#202336"   
BG_BUBBLE    = "#3B5BDB"   
ACCENT       = "#3B5BDB"   
ACCENT_HOVER = "#4C6EF5"   
ONLINE_CLR   = "#2DD4BF"   
OFFLINE_CLR  = "#636E80"   
PENDING_CLR  = "#F59E0B"   
TEXT_PRI     = "#F1F5F9"   
TEXT_SEC     = "#94A3B8"   
TEXT_MUTED   = "#475569"   
DANGER       = "#EF4444"   
DANGER_HOVER = "#DC2626"   
INPUT_BG     = "#1A1B26"   
BORDER_COLOR = "#23283D"   

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.title("MessageNet")
        self.geometry("1000x680")
        self.minsize(800, 560)
        self.configure(fg_color=BG_DARK)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        print("[DEBUG] Pedindo nome do contato...")
        self.my_name = simpledialog.askstring("Login", "Seu Nome de Contato:", parent=self)
        if not self.my_name:
            print("[DEBUG] Nome de contato não fornecido, encerrando.")
            self.destroy()
            os._exit(0)
            
        print(f"[DEBUG] Nome definido: {self.my_name}")
        self.server_ip = simpledialog.askstring("Servidor", "IP do Servidor:", initialvalue=get_local_ip(), parent=self)
        if not self.server_ip:
            print("[DEBUG] IP do servidor não fornecido, encerrando.")
            self.destroy()
            os._exit(0)

        self.my_online = tk.BooleanVar(value=True)
        self._load_data()
        self.active_chat = tk.StringVar(value="")

        try:

            def on_message_received(sender, text, time):
                self.after(0, self.handle_incoming_message, sender, text, time)
                
            self.network = ChatNetworkClient(self.my_name, self.server_ip, on_message_received)
            print("[DEBUG] Conectando ao cliente de rede...")
            offline_msgs = self.network.connect()
            print(f"[DEBUG] Login efetuado. {len(offline_msgs)} mensagens offline recebidas.")
        except Exception as e:
            print(f"[DEBUG] Falha na conexão ou inicialização de rede: {e}")
            messagebox.showerror("Erro de Conexão", str(e))
            self.destroy()
            os._exit(0)

        print("[DEBUG] Construindo UI...")
        self._build_ui()
        print("[DEBUG] UI construída. Renderizando contatos...")
        self._render_contacts()

        print("[DEBUG] Processando mensagens offline...")
        for msg in offline_msgs:
            if isinstance(msg, dict) and "sender" in msg and "text" in msg and "time" in msg:
                self.handle_incoming_message(msg["sender"], msg["text"], msg["time"])

        print("[DEBUG] Iniciando polling de status...")

        self.after(1000, self._update_statuses)
        print("[DEBUG] Inicialização do __init__ concluída. Chamando mainloop.")

    def _get_save_path(self):
        return f"dados_{self.my_name}.json"

    def _load_data(self):
        filepath = self._get_save_path()
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.contacts = data.get("contacts", [])
                    self.messages = data.get("messages", {})
                    for c in self.contacts:
                        c["online"] = False
            except Exception as e:
                print(f"Erro ao carregar dados locais: {e}")
                self.contacts = []
                self.messages = {}
        else:
            self.contacts = []
            self.messages = {}

    def _save_data(self):
        filepath = self._get_save_path()
        data = {
            "contacts": self.contacts,
            "messages": self.messages
        }
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao salvar dados locais: {e}")

    def on_closing(self):
        if hasattr(self, 'network'):
            try:
                if self.my_online.get():
                    self.network.toggle_status(False)
                self.network.close()
            except:
                pass
        self._save_data()
        self.destroy()
        os._exit(0)

    def handle_incoming_message(self, sender, text, time):

        contact = next((c for c in self.contacts if c["name"].lower() == sender.lower()), None)
        
        if not contact:
            is_online = False
            try:
                is_online, _ = self.network.get_status(sender)
            except: pass

            self.contacts.append({"name": sender, "online": is_online, "unread": 0})
            self.messages[sender] = []
            chat_name = sender
        else:
            chat_name = contact["name"]
        
        msg = {"sender": sender, "text": text, "time": time, "pending": False}
        self.messages.setdefault(chat_name, []).append(msg)
        
        if self.active_chat.get().lower() == sender.lower():
            self._render_chat(chat_name)
        else:
            if contact:
                contact["unread"] = contact.get("unread", 0) + 1
            else:

                for c in self.contacts:
                    if c["name"].lower() == sender.lower():
                        c["unread"] = c.get("unread", 0) + 1
            self._render_contacts()
            
        self._save_data()

    def _update_statuses(self):

        if self.my_online.get() and hasattr(self, 'network'):
            try:
                self.network.ensure_login()
            except Exception as e:
                print(f"[DEBUG] Erro ao verificar auto-registro no servidor: {e}")

        changed = False
        active_name = self.active_chat.get()
        active_chat_status_changed = False
        active_chat_updated = False

        if hasattr(self, 'network'):
            for c in self.contacts:
                try:
                    is_online, _ = self.network.get_status(c["name"])
                    if c["online"] != is_online:
                        c["online"] = is_online
                        changed = True
                        if active_name and active_name.lower() == c["name"].lower():
                            active_chat_status_changed = True

                        if is_online:
                            contact_msgs = self.messages.get(c["name"], [])
                            updated_any = False
                            for m in contact_msgs:
                                if m.get("pending", False):
                                    m["pending"] = False
                                    updated_any = True
                            if updated_any:
                                self._save_data()
                                if active_name and active_name.lower() == c["name"].lower():
                                    active_chat_updated = True
                except Exception as e:
                    print(f"[DEBUG] Erro ao obter status do contato {c['name']}: {e}")
            
        if changed:
            self._render_contacts()
        if active_chat_status_changed:

            contact = next((con for con in self.contacts if con["name"].lower() == active_name.lower()), None)
            if contact:
                self._chat_status.configure(
                    text="● Online" if contact["online"] else "● Offline",
                    text_color=ONLINE_CLR if contact["online"] else OFFLINE_CLR)
        if active_chat_updated:
            self._render_chat(active_name)
            
        self.after(1000, self._update_statuses)

    def _build_ui(self):

        topbar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=60, corner_radius=0)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)

        ctk.CTkLabel(topbar, text="✉  MessageNet", font=("Segoe UI", 16, "bold"), text_color=ACCENT_HOVER).pack(side="left", padx=20)

        right = ctk.CTkFrame(topbar, fg_color="transparent")
        right.pack(side="right", padx=16)

        self._status_dot = ctk.CTkLabel(right, text="●", font=("Segoe UI", 14), text_color=ONLINE_CLR)
        self._status_dot.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(right, text=self.my_name, font=("Segoe UI", 12, "bold"), text_color=TEXT_PRI).pack(side="left", padx=(0, 12))

        self._status_btn = ctk.CTkButton(right, text="Online", font=("Segoe UI", 11, "bold"),
                                         fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=TEXT_PRI,
                                         width=80, height=28, corner_radius=6,
                                         command=self._toggle_my_status)
        self._status_btn.pack(side="left")

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(main, fg_color=BG_PANEL, width=260, corner_radius=0)
        sidebar.pack(fill="y", side="left")
        sidebar.pack_propagate(False)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._render_contacts())
        self._search_entry = ctk.CTkEntry(sidebar, textvariable=self._search_var,
                                          placeholder_text="Buscar contatos...",
                                          fg_color=INPUT_BG, border_color=BORDER_COLOR,
                                          text_color=TEXT_PRI, placeholder_text_color=TEXT_MUTED,
                                          font=("Segoe UI", 11), height=36, corner_radius=8)
        self._search_entry.pack(fill="x", padx=12, pady=(12, 6))

        hdr = ctk.CTkFrame(sidebar, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(hdr, text="CONTATOS", font=("Segoe UI", 9, "bold"), text_color=TEXT_MUTED).pack(side="left")
        
        ctk.CTkButton(hdr, text="+", font=("Segoe UI", 14, "bold"),
                      fg_color="transparent", text_color=ACCENT_HOVER, hover_color=BG_CARD,
                      width=24, height=24, corner_radius=12,
                      command=self._add_contact).pack(side="right")

        self._contacts_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent", corner_radius=0)
        self._contacts_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        chat_col = ctk.CTkFrame(main, fg_color=BG_DARK, corner_radius=0)
        chat_col.pack(fill="both", expand=True, side="left")

        self._chat_header = ctk.CTkFrame(chat_col, fg_color=BG_PANEL, height=60, corner_radius=0)
        self._chat_header.pack(fill="x")
        self._chat_header.pack_propagate(False)

        self._chat_title  = ctk.CTkLabel(self._chat_header, text="", font=("Segoe UI", 14, "bold"), text_color=TEXT_PRI)
        self._chat_title.pack(side="left", padx=20)

        self._chat_status = ctk.CTkLabel(self._chat_header, text="", font=("Segoe UI", 10), text_color=ONLINE_CLR)
        self._chat_status.pack(side="left", padx=(0, 12))

        self._remove_btn = ctk.CTkButton(self._chat_header, text="Remover contato",
                                         font=("Segoe UI", 11), fg_color=DANGER, hover_color=DANGER_HOVER,
                                         text_color=TEXT_PRI, width=120, height=28, corner_radius=6,
                                         command=self._remove_contact)
        self._remove_btn.pack(side="right", padx=16)

        self._msg_scrollable = ctk.CTkScrollableFrame(chat_col, fg_color=BG_DARK, corner_radius=0)
        self._msg_scrollable.pack(fill="both", expand=True, padx=0, pady=0)

        input_bar = ctk.CTkFrame(chat_col, fg_color=BG_PANEL, height=70, corner_radius=0)
        input_bar.pack(fill="x", side="bottom")
        input_bar.pack_propagate(False)

        self._msg_entry = ctk.CTkTextbox(input_bar, font=("Segoe UI", 11),
                                         fg_color=INPUT_BG, border_color=BORDER_COLOR,
                                         text_color=TEXT_PRI, border_width=1,
                                         corner_radius=8, wrap="word")
        self._msg_entry.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=12)
        self._msg_entry.bind("<Return>",      self._on_enter)
        self._msg_entry.bind("<Shift-Return>", lambda e: None)

        send_btn = ctk.CTkButton(input_bar, text="Enviar ➤", font=("Segoe UI", 11, "bold"),
                                 fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                 text_color=TEXT_PRI, width=90, height=36, corner_radius=8,
                                 command=self._send_message)
        send_btn.pack(side="right", padx=(0, 16), pady=16)

    def _render_contacts(self):
        for w in self._contacts_frame.winfo_children():
            w.destroy()

        query = self._search_var.get().lower()
        for c in self.contacts:
            if query and query not in c["name"].lower():
                continue
            self._make_contact_row(c)

    def _make_contact_row(self, c):
        name    = c["name"]
        online  = c["online"]
        unread  = c.get("unread", 0)
        active  = (self.active_chat.get() == name)
        row_bg  = BG_CARD if active else "transparent"

        row = ctk.CTkFrame(self._contacts_frame, fg_color=row_bg, corner_radius=8, cursor="hand2")
        row.pack(fill="x", pady=2, padx=4)

        avatar = ctk.CTkFrame(row, width=32, height=32, corner_radius=16, fg_color=ACCENT)
        avatar.pack_propagate(False)
        avatar.pack(side="left", padx=(8, 8), pady=8)

        avatar_lbl = ctk.CTkLabel(avatar, text=name[0].upper(), font=("Segoe UI", 11, "bold"), text_color=TEXT_PRI)
        avatar_lbl.place(relx=0.5, rely=0.5, anchor="center")

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=6)

        name_lbl = ctk.CTkLabel(info, text=name, font=("Segoe UI", 11, "bold"), text_color=TEXT_PRI, anchor="w")
        name_lbl.pack(fill="x")

        status_txt = "● Online" if online else "● Offline"
        status_clr = ONLINE_CLR if online else OFFLINE_CLR
        status_lbl = ctk.CTkLabel(info, text=status_txt, font=("Segoe UI", 9), text_color=status_clr, anchor="w")
        status_lbl.pack(fill="x")

        if unread:
            badge = ctk.CTkFrame(row, width=20, height=20, corner_radius=10, fg_color=ACCENT)
            badge.pack_propagate(False)
            badge.pack(side="right", padx=8)
            
            badge_lbl = ctk.CTkLabel(badge, text=str(unread), font=("Segoe UI", 9, "bold"), text_color=TEXT_PRI)
            badge_lbl.place(relx=0.5, rely=0.5, anchor="center")

        for widget in (row, avatar, avatar_lbl, info, name_lbl, status_lbl):
            widget.bind("<Button-1>", lambda e, n=name: self._open_chat(n))
        if unread:
            badge.bind("<Button-1>", lambda e, n=name: self._open_chat(n))
            badge_lbl.bind("<Button-1>", lambda e, n=name: self._open_chat(n))

        def on_enter(e):
            if self.active_chat.get() != name:
                row.configure(fg_color=BG_CARD)
        def on_leave(e):
            if self.active_chat.get() != name:
                row.configure(fg_color="transparent")
        row.bind("<Enter>", on_enter)
        row.bind("<Leave>", on_leave)

    def _open_chat(self, name):
        for c in self.contacts:
            if c["name"] == name:
                c["unread"] = 0
        self._save_data()
        self.active_chat.set(name)
        self._render_contacts()
        self._render_chat(name)

    def _render_chat(self, name):
        contact = next((c for c in self.contacts if c["name"] == name), None)
        if not contact:
            return
        self._chat_title.configure(text=name)
        self._chat_status.configure(
            text="● Online" if contact["online"] else "● Offline",
            text_color=ONLINE_CLR if contact["online"] else OFFLINE_CLR)

        for w in self._msg_scrollable.winfo_children():
            w.destroy()

        msgs = self.messages.get(name, [])
        if not msgs:
            ctk.CTkLabel(self._msg_scrollable, text="Nenhuma mensagem ainda. Diga olá! 👋",
                         font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(pady=40)
        else:
            for msg in msgs:
                self._render_bubble(msg)

        self._msg_scrollable.update_idletasks()
        self._msg_scrollable._parent_canvas.yview_moveto(1.0)

    def _render_bubble(self, msg):
        is_me   = (msg["sender"] == "me")
        pending = msg.get("pending", False)

        outer = ctk.CTkFrame(self._msg_scrollable, fg_color="transparent")
        outer.pack(fill="x", padx=16, pady=4)

        if is_me:
            bubble_bg = ACCENT
            align     = "e"
        else:
            bubble_bg = BG_CARD
            align     = "w"

        inner = ctk.CTkFrame(outer, fg_color=bubble_bg, corner_radius=12)
        inner.pack(anchor=align, padx=(80 if is_me else 0, 0 if is_me else 80))

        lbl = ctk.CTkLabel(inner, text=msg["text"], font=("Segoe UI", 11),
                           text_color=TEXT_PRI, justify="left", wraplength=360)
        lbl.pack(padx=12, pady=(8, 4), anchor="w")

        meta_line = ctk.CTkFrame(inner, fg_color="transparent", height=16)
        meta_line.pack(fill="x", padx=12, pady=(0, 6))

        time_lbl = ctk.CTkLabel(meta_line, text=msg["time"], font=("Segoe UI", 8), text_color=TEXT_SEC)
        time_lbl.pack(side="left")

        if pending:
            pending_lbl = ctk.CTkLabel(meta_line, text="⏳ pendente", font=("Segoe UI", 8, "italic"), text_color=PENDING_CLR)
            pending_lbl.pack(side="right")
        elif is_me:
            status_lbl = ctk.CTkLabel(meta_line, text="✓✓", font=("Segoe UI", 8), text_color=ONLINE_CLR)
            status_lbl.pack(side="right")

    def _toggle_my_status(self):
        self.my_online.set(not self.my_online.get())
        if self.my_online.get():
            self._status_dot.configure(text_color=ONLINE_CLR)
            self._status_btn.configure(text="Online", fg_color=ACCENT, hover_color=ACCENT_HOVER)
            try:
                offline_msgs = self.network.toggle_status(True)
                for msg in offline_msgs:
                    self.handle_incoming_message(msg["sender"], msg["text"], msg["time"])
            except:
                pass
        else:
            self._status_dot.configure(text_color=OFFLINE_CLR)
            self._status_btn.configure(text="Offline", fg_color=OFFLINE_CLR, hover_color="#4B5563")
            try:
                self.network.toggle_status(False)
            except:
                pass

    def _send_message(self):
        text = self._msg_entry.get("1.0", "end").strip()
        if not text:
            return
        self._msg_entry.delete("1.0", "end")

        name = self.active_chat.get()
        if not name:
            return

        try:
            now, pending = self.network.send_message(name, text)
        except Exception as e:
            messagebox.showerror("Erro de Envio", f"Erro de conexão com o servidor.\n{e}")
            return

        msg = {"sender": "me", "text": text, "time": now, "pending": pending}
        self.messages.setdefault(name, []).append(msg)
        self._render_chat(name)
        self._save_data()

    def _on_enter(self, event):
        if not (event.state & 0x1):
            self._send_message()
            return "break"

    def _add_contact(self):
        dialog = ctk.CTkInputDialog(text="Nome do novo contato:", title="Adicionar contato")
        name = dialog.get_input()
        if not name or not name.strip():
            return
        name = name.strip()
        if any(c["name"].lower() == name.lower() for c in self.contacts):
            messagebox.showwarning("Contato existente", f'"{name}" já está na sua lista.', parent=self)
            return
            
        try:
            is_online, _ = self.network.get_status(name)
        except:
            is_online = False
            
        self.contacts.append({"name": name, "online": is_online, "unread": 0})
        self.messages[name] = []
        self._render_contacts()
        self._save_data()

    def _remove_contact(self):
        name = self.active_chat.get()
        if not name:
            return
        if not messagebox.askyesno("Remover contato", f'Deseja remover "{name}" da sua lista de contatos?', parent=self):
            return
        self.contacts = [c for c in self.contacts if c["name"] != name]
        self.messages.pop(name, None)
        self.active_chat.set("")
        for w in self._msg_scrollable.winfo_children():
            w.destroy()
        self._chat_title.configure(text="")
        self._chat_status.configure(text="")
        self._render_contacts()
        self._save_data()

if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()