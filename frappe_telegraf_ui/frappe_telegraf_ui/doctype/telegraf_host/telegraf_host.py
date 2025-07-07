# frappe_telegraf_ui/doctype/telegraf_host/telegraf_host.py

import frappe
from frappe.model.document import Document
from frappe.utils import now
import paramiko
import io

class TelegrafHost(Document):
    # ... (kode validasi dari versi sebelumnya)
    def validate(self):
        if self.ssh_auth_method == "Password" and not self.ssh_password:
            frappe.throw("SSH Password is required for Password authentication.")
        if self.ssh_auth_method == "Private Key" and not self.ssh_private_key:
            frappe.throw("SSH Private Key is required for Private Key authentication.")

# Helper function _get_ssh_client tidak berubah
def _get_ssh_client(hostname):
    # ... (kode dari versi sebelumnya tetap sama)
    host_doc = frappe.get_doc("Telegraf Host", hostname)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    auth_method = host_doc.ssh_auth_method or "Private Key"
    try:
        if auth_method == "Password":
            password = host_doc.get_password('ssh_password')
            if not password: frappe.throw(f"SSH Password is not set for host '{hostname}'")
            client.connect(hostname=host_doc.ip_address, port=host_doc.ssh_port or 22, username=host_doc.ssh_user, password=password, timeout=10)
        elif auth_method == "Private Key":
            if not host_doc.ssh_private_key: frappe.throw(f"SSH Private Key is not set for host '{hostname}'")
            private_key_file = io.StringIO(host_doc.ssh_private_key)
            private_key = paramiko.RSAKey.from_private_key(private_key_file)
            client.connect(hostname=host_doc.ip_address, port=host_doc.ssh_port or 22, username=host_doc.ssh_user, pkey=private_key, timeout=10)
        else:
            frappe.throw("Invalid SSH Authentication Method selected.")
    except Exception as e:
        frappe.throw(f"SSH connection to {host_doc.ip_address} failed: {e}")
    return client

# Fungsi get_telegraf_config dan update_telegraf_config tidak berubah

@frappe.whitelist()
def get_telegraf_config(hostname):
    # ... (kode tidak berubah)
    pass

@frappe.whitelist()
def update_telegraf_config(hostname, new_config):
    # ... (kode tidak berubah)
    pass

# --- FUNGSI BARU DAN YANG DIPERBARUI ---

@frappe.whitelist()
def test_telegraf_config(hostname):
    """Runs 'telegraf --test' on the remote host."""
    client = None
    try:
        client = _get_ssh_client(hostname)
        host_doc = frappe.get_doc("Telegraf Host", hostname)
        config_path = host_doc.telegraf_config_path or "/etc/telegraf/telegraf.conf"
        
        # Jalankan perintah telegraf --test menggunakan sudo untuk konsistensi izin
        command = f"sudo /usr/bin/telegraf --config {config_path} --test"
        stdin, stdout, stderr = client.exec_command(command)
        
        output = stdout.read().decode()
        error = stderr.read().decode()
        
        if error and "Error" in error:
             # Telegraf sering mengeluarkan output error ke stderr bahkan saat berhasil
             # Kita akan gabungkan keduanya untuk output yang lengkap
             return f"OUTPUT:\n{output}\n\nERROR/INFO:\n{error}"

        return output or "Test command executed. No output received, which usually means success."
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Test Telegraf Config Failed")
        frappe.throw(f"Failed to run test on {hostname}: {e}")
    finally:
        if client:
            client.close()

@frappe.whitelist()
def manage_telegraf_service(hostname, action):
    """Manages the telegraf service (start, stop, restart, reload)."""
    
    # Validasi aksi untuk keamanan
    allowed_actions = ['start', 'stop', 'restart', 'reload']
    if action not in allowed_actions:
        frappe.throw(f"Invalid action '{action}'. Allowed actions are: {', '.join(allowed_actions)}")

    client = None
    try:
        client = _get_ssh_client(hostname)
        command = f"sudo systemctl {action} telegraf"
        stdin, stdout, stderr = client.exec_command(command)
        
        exit_code = stdout.channel.recv_exit_status()
        error = stderr.read().decode()

        if exit_code != 0:
            raise Exception(f"Command failed with exit code {exit_code}: {error}")

        return {"status": "success", "message": f"Action '{action}' sent to Telegraf service on {hostname}."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Manage Telegraf Service Failed")
        frappe.throw(f"Failed to {action} service on {hostname}: {e}")
    finally:
        if client:
            client.close()
