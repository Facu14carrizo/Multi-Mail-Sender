import sys
import os
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_responder.log'),
        logging.StreamHandler()
    ]
)

# Asegurar que los archivos se creen/lean en la carpeta del script o del .exe
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox, Listbox, Scrollbar, filedialog, colorchooser, simpledialog
import tkinter.font as tkfont
import threading
import imapclient
import email
import smtplib
import json
from email.mime.text import MIMEText
from email import utils
import ssl
import time

RESPONDIDOS_FILE = 'respondidos.txt'
ENVIADOS_FILE = 'enviados.txt'
CONFIG_FILE = 'config.json'
DESTINATARIOS_FILE = 'destinatarios.json'
SIGNATURE_BLOCK = "\n\nRocío Rodríguez\nRecursos Humanos"
SIGNATURE_HTML = "<br/><br/><span style=\"font-weight:600; font-size:90%\">Rocío Rodríguez<br/>Recursos Humanos</span>"

# Configuración de servidores de email
EMAIL_CONFIG = {
    'migusto': {
        'imap_server': 'mail.migusto.com.ar',
        'smtp_server': 'mail.migusto.com.ar',
        'smtp_port': 465
    },
    'gmail': {
        'imap_server': 'imap.gmail.com',
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587
    },
    'outlook': {
        'imap_server': 'outlook.office365.com',
        'smtp_server': 'smtp-mail.outlook.com',
        'smtp_port': 587
    }
}

# ------------------- Configuración persistente -------------------
def guardar_configuracion(email, password, subject, mensaje, servidor='migusto'):
    config = {
        'email': email,
        'password': password,
        'subject': subject,
        'mensaje': mensaje,
        'servidor': servidor
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logging.info("Configuración guardada exitosamente")
    except Exception as e:
        logging.error(f"Error guardando configuración: {e}")
        messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")

def cargar_configuracion():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Asegurar compatibilidad con versiones anteriores
                if 'servidor' not in config:
                    config['servidor'] = 'migusto'
                return config
        except Exception as e:
            logging.error(f"Error cargando configuración: {e}")
            messagebox.showerror("Error", f"No se pudo cargar la configuración: {e}")
    return {'email': '', 'password': '', 'subject': '', 'mensaje': '', 'servidor': 'migusto'}

def guardar_configuracion_parcial(subject, mensaje, servidor='migusto'):
    try:
        actual = cargar_configuracion()
        config = {
            'email': actual.get('email', ''),
            'password': actual.get('password', ''),
            'subject': subject,
            'mensaje': mensaje,
            'servidor': 'migusto'
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logging.info("Configuración (parcial) guardada exitosamente")
    except Exception as e:
        logging.error(f"Error guardando configuración parcial: {e}")
        messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")

# ------------------- Lógica de auto-respuesta -------------------
def cargar_respondidos():
    try:
        with open(RESPONDIDOS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f.readlines() if line.strip())
    except FileNotFoundError:
        logging.info("Archivo de respondidos no encontrado, creando uno nuevo")
        return set()
    except Exception as e:
        logging.error(f"Error cargando respondidos: {e}")
        return set()

def guardar_respondido(email):
    try:
        with open(RESPONDIDOS_FILE, 'a', encoding='utf-8') as f:
            f.write(email + '\n')
        logging.info(f"Email {email} agregado al historial")
    except Exception as e:
        logging.error(f"Error guardando email respondido: {e}")

def guardar_enviado(email):
    try:
        with open(ENVIADOS_FILE, 'a', encoding='utf-8') as f:
            f.write(email + '\n')
        logging.info(f"Email {email} agregado a enviados")
    except Exception as e:
        logging.error(f"Error guardando email enviado: {e}")

def cargar_destinatarios_guardados():
    try:
        if os.path.exists(DESTINATARIOS_FILE):
            with open(DESTINATARIOS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception as e:
        logging.error(f"Error cargando destinatarios guardados: {e}")
    return []

def guardar_destinatarios_guardados(lista):
    try:
        with open(DESTINATARIOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error guardando destinatarios: {e}")

def actualizar_historial():
    try:
        # Si no existe el listbox (UI sin panel de historial), no hacer nada
        if 'historial_listbox' not in globals():
            return
        responded = cargar_respondidos()
        historial_listbox.delete(0, tk.END)
        for mail in sorted(responded):
            historial_listbox.insert(tk.END, mail)
    except Exception as e:
        logging.error(f"Error actualizando historial: {e}")

def enviar_respuesta(smtp_conn, destinatario, email_account, subject, mensaje_auto, is_html=False):
    try:
        subtype = 'html' if is_html else 'plain'
        mensaje = MIMEText(mensaje_auto, subtype, 'utf-8')
        mensaje['Subject'] = subject
        mensaje['From'] = email_account
        mensaje['To'] = destinatario
        mensaje['Date'] = utils.formatdate(localtime=True)
        
        smtp_conn.sendmail(email_account, destinatario, mensaje.as_string())
        logging.info(f"Respuesta enviada exitosamente a {destinatario}")
        return True
    except Exception as e:
        logging.error(f"Error enviando respuesta a {destinatario}: {e}")
        return False

def enviar_masivo(email_account, email_password, subject, mensaje_auto, servidor, destinatarios, status_callback, is_html=False):
    try:
        if servidor not in EMAIL_CONFIG:
            error_msg = f"Servidor '{servidor}' no configurado"
            logging.error(error_msg)
            status_callback(error_msg)
            return

        config = EMAIL_CONFIG[servidor]
        SMTP_SERVER = config['smtp_server']
        SMTP_PORT = config['smtp_port']

        # Configurar SSL context
        context = ssl.create_default_context()
        if servidor == 'migusto':
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        # Conectar SMTP
        status_callback("Conectando al servidor SMTP...")
        if SMTP_PORT == 587:
            smtp = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            smtp.starttls(context=context)
        else:
            smtp = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)

        smtp.login(email_account, email_password)
        logging.info("Conexión SMTP establecida para envío masivo")

        exitosos = 0
        fallidos = 0
        total = len(destinatarios)
        for i, destinatario in enumerate(destinatarios, 1):
            status_callback(f"Enviando a {destinatario} ({i}/{total})")
            ok = enviar_respuesta(smtp, destinatario, email_account, subject, mensaje_auto, is_html=is_html)
            if ok:
                exitosos += 1
                guardar_enviado(destinatario)
            else:
                fallidos += 1

        try:
            smtp.quit()
        except:
            pass

        resumen = f"Envío finalizado. Exitosos: {exitosos} | Fallidos: {fallidos}"
        status_callback(resumen)
        messagebox.showinfo("Resumen de envío", resumen)
    except smtplib.SMTPAuthenticationError:
        error_msg = "Error de autenticación SMTP. Verifica email y contraseña."
        logging.error(error_msg)
        status_callback(error_msg)
        messagebox.showerror("Error", error_msg)
    except Exception as e:
        error_msg = f"Error en envío masivo: {e}"
        logging.error(error_msg)
        status_callback(error_msg)
        messagebox.showerror("Error", error_msg)

def auto_responder(email_account, email_password, subject, mensaje_auto, servidor, status_callback):
    logging.info("Iniciando auto-responder")
    
    if servidor not in EMAIL_CONFIG:
        error_msg = f"Servidor '{servidor}' no configurado"
        logging.error(error_msg)
        status_callback(error_msg)
        return
    
    config = EMAIL_CONFIG[servidor]
    IMAP_SERVER = config['imap_server']
    SMTP_SERVER = config['smtp_server']
    SMTP_PORT = config['smtp_port']

    respondidos = cargar_respondidos()
    imap = None
    smtp = None
    
    try:
        # Configurar SSL context
        context = ssl.create_default_context()
        if servidor == 'migusto':
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        # Conectar IMAP
        status_callback("Conectando al servidor IMAP...")
        imap = imapclient.IMAPClient(IMAP_SERVER, ssl=True, ssl_context=context)
        imap.login(email_account, email_password)
        imap.select_folder('INBOX')
        logging.info("Conexión IMAP establecida")

        # Conectar SMTP
        status_callback("Conectando al servidor SMTP...")
        if SMTP_PORT == 587:
            smtp = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            smtp.starttls(context=context)
        else:
            smtp = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
        
        smtp.login(email_account, email_password)
        logging.info("Conexión SMTP establecida")

        # Buscar mensajes no leídos
        mensajes = imap.search('UNSEEN')
        status_callback(f'Correos no leídos encontrados: {len(mensajes)}')
        logging.info(f"Encontrados {len(mensajes)} correos no leídos")

        if not mensajes:
            status_callback("No hay correos nuevos para responder")
            return

        # Procesar cada mensaje
        for i, msgid in enumerate(mensajes, 1):
            try:
                raw = imap.fetch(msgid, ['RFC822'])[msgid][b'RFC822']
                if isinstance(raw, bytes):
                    msg = email.message_from_bytes(raw)
                    sender = utils.parseaddr(msg.get('From') or '')[1]
                else:
                    logging.warning(f"El mensaje {msgid} no es de tipo bytes, se omite")
                    continue

                if not sender:
                    logging.warning(f"No se pudo obtener el remitente del mensaje {msgid}")
                    continue

                if sender.lower() in respondidos:
                    status_callback(f'Ya se respondió a {sender}, salteando.')
                    imap.add_flags(msgid, [imapclient.SEEN])
                    continue

                # Enviar respuesta
                status_callback(f'Enviando respuesta a {sender} ({i}/{len(mensajes)})')
                if enviar_respuesta(smtp, sender, email_account, subject, mensaje_auto):
                    guardar_respondido(sender.lower())
                    imap.add_flags(msgid, [imapclient.SEEN])
                    status_callback(f'✓ Respuesta enviada a {sender}')
                else:
                    status_callback(f'✗ Error enviando a {sender}')

            except Exception as e:
                logging.error(f"Error procesando mensaje {msgid}: {e}")
                status_callback(f'Error procesando mensaje: {e}')

        status_callback('Proceso finalizado exitosamente.')
        logging.info("Proceso de auto-respuesta completado")

    except imapclient.exceptions.LoginError:
        error_msg = "Error de autenticación. Verifica email y contraseña."
        logging.error(error_msg)
        status_callback(error_msg)
    except Exception as e:
        error_msg = f'Error general en la ejecución: {e}'
        logging.error(error_msg)
        status_callback(error_msg)
    finally:
        # Cerrar conexiones
        try:
            if smtp:
                smtp.quit()
                logging.info("Conexión SMTP cerrada")
        except:
            pass
        try:
            if imap:
                imap.logout()
                logging.info("Conexión IMAP cerrada")
        except:
            pass

# ------------------- Interfaz gráfica mejorada -------------------
animando = False
modo_continuo = False
hilo_continuo = None

def iniciar():
    global animando, modo_continuo
    logging.info("Botón Iniciar presionado")
    
    conf = cargar_configuracion()
    email_account = conf.get('email', '').strip()
    email_password = conf.get('password', '')
    subject = entry_subject.get().strip()
    mensaje_auto = entry_mensaje.get("1.0", tk.END)
    if 'Rocío Rodríguez' not in mensaje_auto:
        mensaje_auto = mensaje_auto.rstrip() + SIGNATURE_BLOCK
    servidor = 'migusto'
    
    if not email_account or not email_password:
        messagebox.showerror("Error", "Configura email y contraseña en config.json (no se muestran en la UI).")
        return
    if not subject or not mensaje_auto:
        messagebox.showerror("Error", "Completa asunto y mensaje.")
        return
    
    guardar_configuracion_parcial(subject, mensaje_auto, servidor)
    btn_iniciar.config(state=tk.DISABLED)
    btn_continuo.config(state=tk.DISABLED)
    status_var.set("Procesando...")
    
    def set_estado_final(msg):
        status_var.set(msg)
        btn_iniciar.config(state=tk.NORMAL)
        btn_continuo.config(state=tk.NORMAL)
        actualizar_historial()
    
    def run():
        auto_responder(email_account, email_password, subject, mensaje_auto, servidor, set_estado_final)
    
    threading.Thread(target=run, daemon=True).start()

def toggle_continuo():
    global modo_continuo, animando, hilo_continuo
    if not modo_continuo:
        modo_continuo = True
        btn_continuo.config(text="Detener Modo Continuo")
        btn_iniciar.config(state=tk.DISABLED)
        
        conf = cargar_configuracion()
        email_account = conf.get('email', '').strip()
        email_password = conf.get('password', '')
        subject = entry_subject.get().strip()
        mensaje_auto = entry_mensaje.get("1.0", tk.END).strip()
        servidor = 'migusto'
        
        if not email_account or not email_password:
            messagebox.showerror("Error", "Configura email y contraseña en config.json (no se muestran en la UI).")
            modo_continuo = False
            btn_continuo.config(text="Modo Continuo (esperar correos)")
            btn_iniciar.config(state=tk.NORMAL)
            return
        if not subject or not mensaje_auto:
            messagebox.showerror("Error", "Completa asunto y mensaje.")
            modo_continuo = False
            btn_continuo.config(text="Modo Continuo (esperar correos)")
            btn_iniciar.config(state=tk.NORMAL)
            return
        
        guardar_configuracion_parcial(subject, mensaje_auto, servidor)
        status_var.set("Esperando correos nuevos...")
        
        def set_estado_final(msg):
            if not modo_continuo:
                status_var.set("Modo continuo detenido.")
            else:
                status_var.set(msg)
            actualizar_historial()
        
        def run_continuo():
            global modo_continuo
            while modo_continuo:
                try:
                    status_var.set("Buscando correos...")
                    auto_responder(email_account, email_password, subject, mensaje_auto, servidor, set_estado_final)
                    if modo_continuo:
                        status_var.set("Esperando próximos correos...")
                    for _ in range(60):
                        if not modo_continuo:
                            break
                        time.sleep(1)
                except Exception as e:
                    logging.error(f"Error en modo continuo: {e}")
                    if modo_continuo:
                        status_var.set(f"Error: {e}")
                        time.sleep(10)  # Esperar antes de reintentar
            
            status_var.set("Modo continuo detenido.")
            btn_iniciar.config(state=tk.NORMAL)
            btn_continuo.config(text="Modo Continuo (esperar correos)")
        
        hilo_continuo = threading.Thread(target=run_continuo, daemon=True)
        hilo_continuo.start()
    else:
        modo_continuo = False
        btn_continuo.config(text="Modo Continuo (esperar correos)")
        btn_iniciar.config(state=tk.NORMAL)
        status_var.set("Modo continuo detenido.")

def limpiar_historial():
    try:
        if messagebox.askyesno("Confirmar", "¿Estás seguro de que quieres limpiar el historial?"):
            with open(RESPONDIDOS_FILE, 'w', encoding='utf-8') as f:
                f.write('')
            actualizar_historial()
            logging.info("Historial limpiado")
            messagebox.showinfo("Éxito", "Historial limpiado correctamente")
    except Exception as e:
        logging.error(f"Error limpiando historial: {e}")
        messagebox.showerror("Error", f"No se pudo limpiar el historial: {e}")

def on_close():
    # Guardar configuración al cerrar
    try:
        guardar_configuracion_parcial(
            entry_subject.get(), 
            entry_mensaje.get("1.0", tk.END).strip(),
            'migusto'
        )
        logging.info("Aplicación cerrada")
    except Exception as e:
        logging.error(f"Error al cerrar: {e}")
    root.destroy()

def cargar_destinatarios_desde_archivo():
    try:
        path = filedialog.askopenfilename(
            title="Seleccionar archivo de destinatarios",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        with open(path, 'r', encoding='utf-8') as f:
            lineas = [l.strip() for l in f.readlines() if l.strip()]
        for l in lineas:
            # formato simple: email[,nombre]
            partes = [p.strip() for p in l.split(',')]
            email_txt = partes[0]
            nombre_txt = partes[1] if len(partes) > 1 else ''
            if '@' in email_txt and '.' in email_txt:
                if email_txt.lower() not in {r["email"].lower() for r in recipients_list}:
                    recipients_list.append({"email": email_txt, "nombre": nombre_txt})
        refresh_dest_list()
        logging.info(f"Destinatarios cargados desde archivo: {path}")
    except Exception as e:
        logging.error(f"Error cargando archivo de destinatarios: {e}")
        messagebox.showerror("Error", f"No se pudo cargar el archivo: {e}")

def obtener_lista_destinatarios():
    seleccionados = []
    for i, r in enumerate(recipients_list):
        selected = r.get("selected", True)
        if i < len(recipient_vars):
            try:
                selected = bool(recipient_vars[i].get())
            except Exception:
                pass
        recipients_list[i]["selected"] = selected
    guardar_destinatarios_guardados(recipients_list)
    for r in recipients_list:
        if r.get("selected", True):
            seleccionados.append(r["email"])
    return seleccionados

def _to_html(text_widget: tk.Text) -> str:
    try:
        content = text_widget.get("1.0", tk.END)
        # mapa de posiciones a etiquetas activas
        html = ""
        idx = "1.0"
        open_tags = []
        def open_tag(tag):
            nonlocal html
            if tag == 'bold':
                html += '<b>'
            elif tag == 'italic':
                html += '<i>'
            elif tag == 'underline':
                html += '<u>'
            elif tag.startswith('fg_'):
                color = tag.split('_',1)[1]
                html += f'<span style="color:{color}">'
            elif tag.startswith('fs_'):
                size = tag.split('_',1)[1]
                html += f'<span style="font-size:{size}px">'
        def close_tag(tag):
            nonlocal html
            if tag == 'bold':
                html += '</b>'
            elif tag == 'italic':
                html += '</i>'
            elif tag == 'underline':
                html += '</u>'
            elif tag.startswith('fg_'):
                html += '</span>'
            elif tag.startswith('fs_'):
                html += '</span>'
        while True:
            next_idx = text_widget.index(f"{idx} +1c")
            if next_idx == idx:
                break
            ch = text_widget.get(idx, next_idx)
            tags = text_widget.tag_names(idx)
            # cerrar tags que ya no aplican
            for t in list(open_tags):
                if t not in tags:
                    close_tag(t)
                    open_tags.remove(t)
            # abrir tags nuevos
            for t in tags:
                if t in ('bold','italic','underline') or t.startswith('fg_'):
                    if t not in open_tags:
                        open_tag(t)
                        open_tags.append(t)
            # escapar html básico
            if ch == '<':
                html += '&lt;'
            elif ch == '>':
                html += '&gt;'
            elif ch == '&':
                html += '&amp;'
            elif ch == '\n':
                html += '<br/>'
            else:
                html += ch
            idx = next_idx
        # cerrar tags abiertos
        for t in reversed(open_tags):
            close_tag(t)
        return html
    except Exception:
        return text_widget.get("1.0", tk.END)

def on_enviar_destinatarios():
    conf = cargar_configuracion()
    email_account = conf.get('email', '').strip()
    email_password = conf.get('password', '')
    subject = entry_subject.get().strip()
    mensaje_auto = entry_mensaje.get("1.0", tk.END)
    if 'Rocío Rodríguez' not in mensaje_auto:
        mensaje_auto = mensaje_auto.rstrip() + SIGNATURE_BLOCK
    servidor = 'migusto'

    destinatarios = obtener_lista_destinatarios()
    if not email_account or not email_password:
        messagebox.showerror("Error", "Configura email y contraseña en config.json (no se muestran en la UI).")
        return
    if not subject or not mensaje_auto:
        messagebox.showerror("Error", "Completa asunto y mensaje.")
        return
    if not destinatarios:
        messagebox.showerror("Error", "Agrega al menos un destinatario (uno por línea).")
        return

    if not messagebox.askyesno("Confirmar envío", f"Se enviará a {len(destinatarios)} destinatario(s). ¿Continuar?"):
        return

    # Deshabilitar botones durante envío y cambiar texto
    btn_enviar.config(state=tk.DISABLED, text="⏳ Enviando…")
    try:
        btn_iniciar.config(state=tk.DISABLED)
        btn_continuo.config(state=tk.DISABLED)
    except Exception:
        pass

    def set_estado(msg):
        status_var.set(msg)

    def run_envio():
        try:
            # Detectar si hay tags ricas para enviar como HTML simple
            is_html = any(name in entry_mensaje.tag_names() for name in ['bold','italic','underline'])
            html = mensaje_auto
            if is_html:
                # Convertir tags a HTML mínimo
                html = _to_html(entry_mensaje)
                if 'Rocío Rodríguez' not in html:
                    html = html.rstrip() + SIGNATURE_HTML
            enviar_masivo(email_account, email_password, subject, html if is_html else mensaje_auto, servidor, destinatarios, set_estado, is_html=is_html)
        finally:
            btn_enviar.config(state=tk.NORMAL, text="✈ Enviar")
            try:
                btn_iniciar.config(state=tk.NORMAL)
                btn_continuo.config(state=tk.NORMAL)
            except Exception:
                pass

    threading.Thread(target=run_envio, daemon=True).start()

# Cargar configuración previa
config = cargar_configuracion()

root = tk.Tk()
root.title("Auto-Responder Email")
root.geometry("1280x800")
root.minsize(1000, 600)
root.configure(bg="#23272f")
root.resizable(True, True)
try:
    root.state('zoomed')  # Windows: pantalla completa (maximizada)
except Exception:
    pass

# Estilos modo oscuro
DARK_BG = "#23272f"
DARK_FRAME = "#2c313c"
DARK_ENTRY = "#23272f"
DARK_LABEL = "#e0e6f0"
DARK_BUTTON = "#4f8cff"
DARK_BUTTON_HOVER = "#357ae8"
DARK_STATUS = "#7ecfff"
FONT = ("Segoe UI", 13)
FONT_BOLD = ("Segoe UI", 14, "bold")

style = {
    "label": {"font": FONT, "bg": DARK_FRAME, "fg": DARK_LABEL},
    "entry": {"font": FONT, "bg": DARK_ENTRY, "fg": DARK_LABEL, "insertbackground": DARK_LABEL, "relief": "flat", "highlightthickness": 1, "highlightbackground": "#444"},
    "text": {"font": FONT, "bg": DARK_ENTRY, "fg": DARK_LABEL, "insertbackground": DARK_LABEL, "relief": "flat", "highlightthickness": 1, "highlightbackground": "#444"},
    "button": {"font": FONT_BOLD, "bg": DARK_BUTTON, "fg": "white", "activebackground": DARK_BUTTON_HOVER, "activeforeground": "white", "relief": "flat", "bd": 0, "cursor": "hand2", "padx": 24, "pady": 10}
}

# Tooltip simple para widgets
class _Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    def show(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, bg="#333", fg="white", bd=0, padx=8, pady=4, font=("Segoe UI", 10))
        label.pack()
    def hide(self, event=None):
        tw = self.tipwindow
        if tw:
            tw.destroy()
        self.tipwindow = None

def create_tooltip(widget, text):
    _Tooltip(widget, text)

# Placeholders para entradas (con color tenue y restauración en blur)
PLACEHOLDER_COLOR = "#7e8795"
def add_placeholder(entry: tk.Entry, text: str):
    normal_fg = style["entry"]["fg"]
    def _set():
        if not entry.get():
            entry.insert(0, text)
            entry.config(fg=PLACEHOLDER_COLOR)
            entry._is_placeholder = True
    def _clear(_=None):
        if getattr(entry, "_is_placeholder", False):
            entry.delete(0, tk.END)
            entry.config(fg=normal_fg)
            entry._is_placeholder = False
    def _restore(_=None):
        if not entry.get():
            _set()
    entry.bind("<FocusIn>", _clear)
    entry.bind("<FocusOut>", _restore)
    _set()

# Layout principal
main_frame = tk.Frame(root, bg=DARK_BG)
main_frame.pack(fill="both", expand=True)

# Contenedor centrado
container = tk.Frame(main_frame, bg=DARK_BG)
container.pack(fill="both", expand=True)
container.grid_columnconfigure(0, weight=1)
container.grid_rowconfigure(0, weight=1)

# Panel izquierdo: formulario
form_frame = tk.Frame(container, bg=DARK_FRAME, highlightthickness=1, highlightbackground="#3b4252")
form_frame.grid(row=0, column=0, sticky="nsew", padx=48, pady=32)

# Panel derecho removido

"""
Formulario simplificado: ocultamos servidor/email/contraseña en la UI.
El servidor se fija a 'migusto' y las credenciales se leen de config.json
"""
row = 0
form_frame.grid_columnconfigure(0, minsize=180)
form_frame.grid_columnconfigure(1, weight=1)

tk.Label(form_frame, text="Destinatarios:", **style["label"]).grid(row=row, column=0, sticky="ne", pady=10, padx=8)

# Entrada para agregar destinatarios (email + nombre opcional)
dest_input_frame = tk.Frame(form_frame, bg=DARK_FRAME)
dest_input_frame.grid(row=row, column=1, pady=10, padx=8, sticky="ew")
dest_input_frame.grid_columnconfigure(0, weight=1)
dest_input_frame.grid_columnconfigure(1, weight=1)

entry_dest_email = tk.Entry(dest_input_frame, width=20, **style["entry"])
entry_dest_email.grid(row=0, column=0, padx=(0,8), pady=(0,8), sticky="ew")
add_placeholder(entry_dest_email, "email@ejemplo.com")

entry_dest_nombre = tk.Entry(dest_input_frame, width=20, **style["entry"])
entry_dest_nombre.grid(row=0, column=1, padx=(0,8), pady=(0,8), sticky="ew")
add_placeholder(entry_dest_nombre, "Nombre (opcional)")

def _clear_placeholder(event, widget, placeholder):
    try:
        if widget.get() == placeholder:
            widget.delete(0, tk.END)
    except Exception:
        pass

# removido: usamos add_placeholder

dest_btn_frame = tk.Frame(dest_input_frame, bg=DARK_FRAME)
dest_btn_frame.grid(row=0, column=2, sticky="e")

recipients_list = cargar_destinatarios_guardados()  # [{"email": str, "nombre": str, "selected": bool}]
recipient_vars = []

def refresh_dest_list():
    for w in dest_list_frame.winfo_children():
        w.destroy()
    recipient_vars.clear()
    for idx, r in enumerate(recipients_list):
        rowf = tk.Frame(dest_list_frame, bg=DARK_FRAME)
        rowf.pack(fill="x", pady=6)
        rowf.grid_columnconfigure(0, weight=1)
        rowf.grid_columnconfigure(1, weight=0)
        rowf.grid_columnconfigure(2, weight=0)
        nombre = (r.get("nombre") or "").strip()
        display_name = nombre if nombre else r["email"].split("@")[0]
        texto_izq = tk.Frame(rowf, bg=DARK_FRAME)
        texto_izq.grid(row=0, column=0, sticky="w")
        tk.Label(texto_izq, text=display_name, font=("Segoe UI", 11, "bold"), bg=DARK_FRAME, fg=DARK_LABEL).pack(anchor="w")
        tk.Label(texto_izq, text=r["email"], font=("Segoe UI", 10), bg=DARK_FRAME, fg=DARK_LABEL).pack(anchor="w")

        var = tk.BooleanVar(value=r.get("selected", True))
        recipient_vars.append(var)
        def on_toggle(i=idx, v=var):
            try:
                recipients_list[i]["selected"] = bool(v.get())
                guardar_destinatarios_guardados(recipients_list)
            except Exception:
                pass
        chk = tk.Checkbutton(rowf, variable=var, command=on_toggle, text="Enviar", bg=DARK_FRAME, fg=DARK_LABEL, selectcolor=DARK_FRAME, activebackground=DARK_FRAME)
        chk.grid(row=0, column=1, padx=8)

        btn_del = tk.Button(rowf, text="🗑", command=lambda i=idx: remove_recipient(i), **style["button"])
        btn_del.configure(padx=6, pady=4, font=("Segoe UI", 12))
        btn_del.grid(row=0, column=2)
        create_tooltip(btn_del, "Borrar destinatario")

def remove_recipient(index):
    try:
        del recipients_list[index]
        guardar_destinatarios_guardados(recipients_list)
        refresh_dest_list()
    except Exception:
        pass

def add_recipient():
    email_txt = entry_dest_email.get().strip()
    nombre_txt = entry_dest_nombre.get().strip()
    if not email_txt or '@' not in email_txt or '.' not in email_txt:
        messagebox.showerror("Error", "Ingresá un email válido.")
        return
    existing = {r["email"].lower() for r in recipients_list}
    if email_txt.lower() in existing:
        messagebox.showinfo("Info", "Ese email ya está en la lista.")
        return
    recipients_list.append({"email": email_txt, "nombre": nombre_txt, "selected": True})
    entry_dest_email.delete(0, tk.END)
    entry_dest_nombre.delete(0, tk.END)
    guardar_destinatarios_guardados(recipients_list)
    refresh_dest_list()

btn_agregar = tk.Button(dest_btn_frame, text="+", command=add_recipient, **style["button"])
btn_agregar.configure(padx=6, pady=4, font=("Segoe UI", 12, "bold"))
btn_agregar.pack()
create_tooltip(btn_agregar, "Agregar destinatario")

# Definir fuentes para formatos (se aplican después de crear entry_mensaje)
default_font = tkfont.nametofont("TkDefaultFont")
bold_font = default_font.copy(); bold_font.configure(weight="bold")
italic_font = default_font.copy(); italic_font.configure(slant="italic")

# Lista de destinatarios con posibilidad de borrar
dest_scroll_container = tk.Frame(form_frame, bg=DARK_FRAME)
dest_scroll_container.grid(row=row+1, column=1, pady=(0,10), padx=8, sticky="ew")

# Canvas con scrollbar para la lista de destinatarios
dest_canvas = tk.Canvas(dest_scroll_container, bg=DARK_FRAME, highlightthickness=0, height=240)
dest_scrollbar = Scrollbar(dest_scroll_container, orient="vertical", command=dest_canvas.yview)
dest_canvas.configure(yscrollcommand=dest_scrollbar.set)
dest_canvas.pack(side="left", fill="both", expand=True)
dest_scrollbar.pack(side="right", fill="y")

# Frame interno donde se renderizan los destinatarios
dest_list_frame = tk.Frame(dest_canvas, bg=DARK_FRAME)
dest_canvas.create_window((0, 0), window=dest_list_frame, anchor="nw")

def _on_frame_configure(event):
    try:
        dest_canvas.configure(scrollregion=dest_canvas.bbox("all"))
    except Exception:
        pass

dest_list_frame.bind("<Configure>", _on_frame_configure)

def _on_mousewheel(event):
    try:
        dest_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    except Exception:
        pass

dest_canvas.bind_all("<MouseWheel>", _on_mousewheel)

row += 2
refresh_dest_list()

# Asunto después de la sección de destinatarios
tk.Label(form_frame, text="Asunto:", **style["label"]).grid(row=row, column=0, sticky="e", pady=10, padx=8)
entry_subject = tk.Entry(form_frame, width=38, **style["entry"])
entry_subject.grid(row=row, column=1, pady=10, padx=8, sticky="ew")
entry_subject.insert(0, config.get('subject', ''))
row += 1

# Mensaje: toolbar + editor al final
tk.Label(form_frame, text="Mensaje:", **style["label"]).grid(row=row, column=0, sticky="ne", pady=10, padx=8)

toolbar = tk.Frame(form_frame, bg=DARK_FRAME)
toolbar.grid(row=row, column=1, sticky="w", padx=8)

SMALL_BTN = {"padx": 10, "pady": 6}

def apply_tag(tag):
    try:
        start = entry_mensaje.index("sel.first")
        end = entry_mensaje.index("sel.last")
        if tag == 'fg':
            color = colorchooser.askcolor(title="Elegir color de texto")[1]
            if not color:
                return
            tagname = f"fg_{color}"
            if not tagname in entry_mensaje.tag_names():
                entry_mensaje.tag_configure(tagname, foreground=color)
            entry_mensaje.tag_add(tagname, start, end)
        elif tag == 'size':
            try:
                size = simpledialog.askinteger("Tamaño de letra", "Ingrese tamaño (8-48):", minvalue=8, maxvalue=48, parent=root)
                if not size:
                    return
                tagname = f"fs_{size}"
                if tagname not in entry_mensaje.tag_names():
                    f = default_font.copy()
                    f.configure(size=size)
                    entry_mensaje.tag_configure(tagname, font=f)
                entry_mensaje.tag_add(tagname, start, end)
            except Exception:
                pass
        else:
            entry_mensaje.tag_add(tag, start, end)
    except tk.TclError:
        # Si no hay selección, aplicar al "palabra actual" donde está el cursor
        try:
            start = entry_mensaje.index("insert wordstart")
            end = entry_mensaje.index("insert wordend")
            if start != end:
                if tag == 'fg':
                    color = colorchooser.askcolor(title="Elegir color de texto")[1]
                    if not color:
                        return
                    tagname = f"fg_{color}"
                    if tagname not in entry_mensaje.tag_names():
                        entry_mensaje.tag_configure(tagname, foreground=color)
                    entry_mensaje.tag_add(tagname, start, end)
                elif tag == 'size':
                    size = simpledialog.askinteger("Tamaño de letra", "Ingrese tamaño (8-48):", minvalue=8, maxvalue=48, parent=root)
                    if not size:
                        return
                    tagname = f"fs_{size}"
                    if tagname not in entry_mensaje.tag_names():
                        f = default_font.copy(); f.configure(size=size)
                        entry_mensaje.tag_configure(tagname, font=f)
                    entry_mensaje.tag_add(tagname, start, end)
                else:
                    entry_mensaje.tag_add(tag, start, end)
            else:
                messagebox.showinfo("Selección requerida", "Seleccioná texto o ubicá el cursor sobre una palabra.")
        except Exception:
            messagebox.showinfo("Selección requerida", "Seleccioná texto o ubicá el cursor sobre una palabra.")

btn_b = tk.Button(toolbar, text="B", **style["button"], command=lambda: apply_tag('bold'))
btn_b.configure(padx=SMALL_BTN["padx"], pady=SMALL_BTN["pady"]) 
btn_b.pack(side="left", padx=(0,6))
btn_i = tk.Button(toolbar, text="I", **style["button"], command=lambda: apply_tag('italic'))
btn_i.configure(padx=SMALL_BTN["padx"], pady=SMALL_BTN["pady"]) 
btn_i.pack(side="left", padx=(0,6))
btn_u = tk.Button(toolbar, text="U", **style["button"], command=lambda: apply_tag('underline'))
btn_u.configure(padx=SMALL_BTN["padx"], pady=SMALL_BTN["pady"]) 
btn_u.pack(side="left", padx=(0,6))
btn_color = tk.Button(toolbar, text="A", **style["button"], command=lambda: apply_tag('fg'))
btn_color.configure(padx=SMALL_BTN["padx"], pady=SMALL_BTN["pady"]) 
btn_color.pack(side="left", padx=(0,6))
btn_size = tk.Button(toolbar, text="A±", **style["button"], command=lambda: apply_tag('size'))
btn_size.configure(padx=SMALL_BTN["padx"], pady=SMALL_BTN["pady"]) 
btn_size.pack(side="left")

entry_mensaje = tk.Text(form_frame, height=10, width=36, **style["text"])
entry_mensaje.grid(row=row+1, column=1, pady=6, padx=8, sticky="ew")
# Prefill: comenzar SIEMPRE con tres saltos de línea y luego asegurar firma
mensaje_inicial = config.get('mensaje', '')
leading = "\n\n\n"
# Forzar exactamente tres saltos al inicio
if not mensaje_inicial.startswith(leading):
    mensaje_inicial = leading + mensaje_inicial.lstrip("\n")
# Asegurar firma al final (sin duplicar)
if 'Rocío Rodríguez' not in mensaje_inicial:
    mensaje_inicial = mensaje_inicial.rstrip() + SIGNATURE_BLOCK
entry_mensaje.insert("1.0", mensaje_inicial)
entry_mensaje.tag_configure('bold', font=bold_font)
entry_mensaje.tag_configure('italic', font=italic_font)
entry_mensaje.tag_configure('underline', underline=1)
row += 2

# Botón de envío al final
btn_enviar = tk.Button(form_frame, text="✈ Enviar", command=on_enviar_destinatarios, **style["button"])
btn_enviar.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12,6))
try:
    create_tooltip(btn_enviar, "Enviar a destinatarios")
except Exception:
    pass
row += 1

status_var = tk.StringVar()
status_label = tk.Label(form_frame, textvariable=status_var, fg=DARK_STATUS, bg=DARK_FRAME, font=("Segoe UI", 12, "italic"))
status_label.grid(row=row, column=0, columnspan=2, pady=(6, 18), sticky="ew")
row += 1

# Botones secundarios eliminados para una UI más simple

# Cerrar guardando
root.protocol("WM_DELETE_WINDOW", on_close)

# Cargar historial inicial
actualizar_historial()

root.mainloop()
