# frappe_telegraf_ui/doctype/telegraf_host/telegraf_host.py

import frappe
from frappe.model.document import Document
from frappe.utils import now
import paramiko
import io
import re

class TelegrafHost(Document):
    def validate(self):
        """Validate the document before saving."""
        self.validate_ssh_auth()
        self.validate_ip_address()
        self.validate_ssh_port()
    
    def validate_ssh_auth(self):
        """Validate SSH authentication settings."""
        if self.ssh_auth_method == "Password" and not self.ssh_password:
            frappe.throw("SSH Password is required when using Password authentication.")
        if self.ssh_auth_method == "Private Key" and not self.ssh_private_key:
            frappe.throw("SSH Private Key is required when using Private Key authentication.")
    
    def validate_ip_address(self):
        """Validate IP address format."""
        if self.ip_address:
            ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
            if not re.match(ip_pattern, self.ip_address):
                frappe.throw("Please enter a valid IP address format (e.g., 192.168.1.100)")
    
    def validate_ssh_port(self):
        """Validate SSH port range."""
        if self.ssh_port and (self.ssh_port < 1 or self.ssh_port > 65535):
            frappe.throw("SSH port must be between 1 and 65535")
    
    def before_save(self):
        """Called before saving the document."""
        # Set default values
        if not self.ssh_port:
            self.ssh_port = 22
        if not self.telegraf_config_path:
            self.telegraf_config_path = "/etc/telegraf/telegraf.conf"
        if not self.status:
            self.status = "Unknown"

def _get_ssh_client(hostname):
    """Get SSH client for the specified hostname."""
    host_doc = frappe.get_doc("Telegraf Host", hostname)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    auth_method = host_doc.ssh_auth_method or "Private Key"
    
    try:
        if auth_method == "Password":
            password = host_doc.get_password('ssh_password')
            if not password: 
                frappe.throw(f"SSH Password is not set for host '{hostname}'")
            client.connect(
                hostname=host_doc.ip_address, 
                port=host_doc.ssh_port or 22, 
                username=host_doc.ssh_user, 
                password=password, 
                timeout=10
            )
        elif auth_method == "Private Key":
            if not host_doc.ssh_private_key: 
                frappe.throw(f"SSH Private Key is not set for host '{hostname}'")
            private_key_file = io.StringIO(host_doc.ssh_private_key)
            private_key = paramiko.RSAKey.from_private_key(private_key_file)
            client.connect(
                hostname=host_doc.ip_address, 
                port=host_doc.ssh_port or 22, 
                username=host_doc.ssh_user, 
                pkey=private_key, 
                timeout=10
            )
        else:
            frappe.throw("Invalid SSH Authentication Method selected.")
    except Exception as e:
        frappe.throw(f"SSH connection to {host_doc.ip_address} failed: {e}")
    
    return client

@frappe.whitelist()
def get_telegraf_config(hostname):
    """Get Telegraf configuration from remote host."""
    client = None
    try:
        client = _get_ssh_client(hostname)
        host_doc = frappe.get_doc("Telegraf Host", hostname)
        config_path = host_doc.telegraf_config_path or "/etc/telegraf/telegraf.conf"
        
        # Read the configuration file
        command = f" cat {config_path}"
        stdin, stdout, stderr = client.exec_command(command)
        
        config_content = stdout.read().decode()
        error = stderr.read().decode()
        
        if error and "No such file" in error:
            frappe.throw(f"Configuration file not found at {config_path}")
        
        return config_content
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Telegraf Config Failed")
        frappe.throw(f"Failed to get config from {hostname}: {e}")
    finally:
        if client:
            client.close()

@frappe.whitelist()
def update_telegraf_config(hostname, new_config):
    """Update Telegraf configuration on remote host."""
    client = None
    try:
        client = _get_ssh_client(hostname)
        host_doc = frappe.get_doc("Telegraf Host", hostname)
        config_path = host_doc.telegraf_config_path or "/etc/telegraf/telegraf.conf"
        
        # Create a backup first
        backup_command = f" cp {config_path} {config_path}.backup.$(date +%Y%m%d_%H%M%S)"
        stdin, stdout, stderr = client.exec_command(backup_command)
        stdout.channel.recv_exit_status()  # Wait for completion
        
        # Write new configuration using a temporary file
        temp_file = f"/tmp/telegraf_config_{frappe.generate_hash(length=8)}.conf"
        
        # Write config to temp file
        write_command = f"echo '{new_config}' |  tee {temp_file} > /dev/null"
        stdin, stdout, stderr = client.exec_command(write_command)
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            raise Exception("Failed to write temporary config file")
        
        # Move temp file to actual config location
        move_command = f" mv {temp_file} {config_path}"
        stdin, stdout, stderr = client.exec_command(move_command)
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            raise Exception("Failed to update config file")
        
        # Set proper permissions
        chmod_command = f" chmod 644 {config_path}"
        stdin, stdout, stderr = client.exec_command(chmod_command)
        stdout.channel.recv_exit_status()
        
        return {"status": "success", "message": f"Configuration updated successfully on {hostname}"}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Telegraf Config Failed")
        frappe.throw(f"Failed to update config on {hostname}: {e}")
    finally:
        if client:
            client.close()

@frappe.whitelist()
def test_telegraf_config(hostname):
    """Test Telegraf configuration on remote host."""
    client = None
    try:
        client = _get_ssh_client(hostname)
        host_doc = frappe.get_doc("Telegraf Host", hostname)
        config_path = host_doc.telegraf_config_path or "/etc/telegraf/telegraf.conf"
        
        # Run telegraf --test command
        command = f" /usr/bin/telegraf --config {config_path} --test"
        stdin, stdout, stderr = client.exec_command(command)
        
        output = stdout.read().decode()
        error = stderr.read().decode()
        
        # Telegraf often outputs to stderr even on success
        result = f"OUTPUT:\n{output}\n\nSTDERR:\n{error}" if error else output
        
        return result or "Test command executed successfully. No output received."
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Test Telegraf Config Failed")
        frappe.throw(f"Failed to test config on {hostname}: {e}")
    finally:
        if client:
            client.close()

@frappe.whitelist()
def manage_telegraf_service(hostname, action):
    """Manage Telegraf service (start, stop, restart, reload)."""
    allowed_actions = ['start', 'stop', 'restart', 'reload']
    if action not in allowed_actions:
        frappe.throw(f"Invalid action '{action}'. Allowed actions: {', '.join(allowed_actions)}")

    client = None
    try:
        client = _get_ssh_client(hostname)
        command = f" systemctl {action} telegraf"
        stdin, stdout, stderr = client.exec_command(command)
        
        exit_code = stdout.channel.recv_exit_status()
        error = stderr.read().decode()

        if exit_code != 0:
            raise Exception(f"Command failed with exit code {exit_code}: {error}")

        return {"status": "success", "message": f"Telegraf service {action} completed on {hostname}"}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Manage Telegraf Service Failed")
        frappe.throw(f"Failed to {action} service on {hostname}: {e}")
    finally:
        if client:
            client.close()

@frappe.whitelist()
def check_host_status(hostname):
    """Check the status of Telegraf service on host."""
    try:
        host_doc = frappe.get_doc("Telegraf Host", hostname)
        client = None
        
        try:
            client = _get_ssh_client(hostname)
            # Check if telegraf service is active
            stdin, stdout, stderr = client.exec_command(" systemctl is-active telegraf")
            status_output = stdout.read().decode().strip()
            
            if status_output == "active":
                host_doc.status = "Active"
            elif status_output == "inactive":
                host_doc.status = "Inactive"
            else:
                host_doc.status = "Down"
                
        except Exception as e:
            host_doc.status = "Down"
            frappe.log_error(f"Failed to check status for {hostname}: {str(e)}", "Host Status Check")
            
        finally:
            if client:
                client.close()
        
        host_doc.last_status_check = now()
        host_doc.save(ignore_permissions=True)
        
        return {
            "status": "success",
            "message": f"Status updated to {host_doc.status}",
            "host_status": host_doc.status
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Check Host Status Failed")
        frappe.throw(f"Failed to check status for {hostname}: {str(e)}")

@frappe.whitelist()
def trigger_status_check():
    """Manual trigger for status check - for testing"""
    from frappe_telegraf_ui.tasks import check_all_hosts_status
    frappe.enqueue(
        check_all_hosts_status,
        queue='short',
        timeout=300,
        is_async=True
    )
    return {"message": "Status check triggered successfully"}

def on_update(doc, method):
    """Hook function called when document is updated."""
    # Auto-check status when document is saved (only for existing documents)
    if not doc.is_new():
        try:
            # Run status check in background to avoid blocking the save
            frappe.enqueue(
                'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.check_host_status',
                hostname=doc.name,
                queue='short',
                timeout=30
            )
        except Exception as e:
            # Don't fail the save if background job fails
            frappe.log_error(f"Failed to enqueue status check: {str(e)}", "On Update Hook")


def check_host_connectivity(ip_address, port=22, timeout=5):
    """Optimized connectivity check for realtime monitoring"""
    import socket
    import time
    
    start_time = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)  # Short timeout for realtime
        result = sock.connect_ex((ip_address, int(port)))
        sock.close()
        
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        return result == 0, response_time
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return False, response_time

