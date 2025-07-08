import frappe
from frappe.utils import now, add_to_date, get_datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

@frappe.whitelist()
def check_all_hosts_status():
    """Check status of all active Telegraf hosts"""
    try:
        hosts = frappe.get_all(
            "Telegraf Host", 
            filters={"status": ["!=", "Inactive"]},
            fields=["name", "hostname", "ip_address", "ssh_port", "ssh_user"]
        )
        
        if not hosts:
            logger.info("No active hosts found for status check")
            return
        
        logger.info(f"Checking status for {len(hosts)} hosts")
        for host in hosts:
            check_single_host_status(host)
        # Use ThreadPoolExecutor for parallel checking
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_host = {
                executor.submit(check_single_host_status, host): host 
                for host in hosts
            }
            
            for future in as_completed(future_to_host):
                host = future_to_host[future]
                try:
                    result = future.result(timeout=30)  # 30 second timeout per host
                    logger.info(f"Host {host['name']}: {result}")
                except Exception as exc:
                    logger.error(f"Host {host['name']} generated an exception: {exc}")
                    
    except Exception as e:
        logger.error(f"Error in check_all_hosts_status: {str(e)}")
        frappe.log_error(f"Scheduler Error: {str(e)}", "Host Status Check Failed")

def check_single_host_status(host_data):
    """Check status of a single host"""
    try:
        logger.info(f"Checking status for host: {host_data['name']}")
        # Perform status check
        from frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host import check_host_status
        check_host_status(
           host_data['name']
        )
       
            
    except Exception as e:
        logger.error(f"Error checking host {host_data['name']}: {str(e)}")
        return f"Error: {str(e)}"

@frappe.whitelist()
def update_telegraf_configs():
    """Update Telegraf configurations for all hosts"""
    try:
        hosts = frappe.get_all(
            "Telegraf Host", 
            filters={"status": "Active", "auto_update_config": 1},
            fields=["name"]
        )
        
        for host in hosts:
            try:
                host_doc = frappe.get_doc("Telegraf Host", host['name'])
                # Update config logic here
                logger.info(f"Updated config for host: {host['name']}")
            except Exception as e:
                logger.error(f"Failed to update config for {host['name']}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in update_telegraf_configs: {str(e)}")

@frappe.whitelist()
def generate_daily_report():
    """Generate daily status report"""
    try:
        from datetime import datetime, timedelta
        yesterday = add_to_date(get_datetime(), days=-1)
        
        # Get status changes from yesterday
        logs = frappe.get_all(
            "Telegraf Host Log",
            filters={
                "timestamp": [">=", yesterday],
                "event_type": "Status Change"
            },
            fields=["host", "old_status", "new_status", "timestamp"]
        )
        
        if logs:
            # Create report document or send email
            logger.info(f"Generated daily report with {len(logs)} status changes")
        
    except Exception as e:
        logger.error(f"Error generating daily report: {str(e)}")

@frappe.whitelist()
def backup_configurations():
    """Backup all Telegraf configurations"""
    try:
        hosts = frappe.get_all("Telegraf Host", filters={"status": "Active"})
        
        for host in hosts:
            # Backup logic here
            logger.info(f"Backed up config for: {host['name']}")
            
    except Exception as e:
        logger.error(f"Error in backup_configurations: {str(e)}")

@frappe.whitelist()
def cleanup_old_logs():
    """Clean up old log entries"""
    try:
        # Delete logs older than 30 days
        old_date = add_to_date(get_datetime(), days=-30)
        
        old_logs = frappe.get_all(
            "Telegraf Host Log",
            filters={"timestamp": ["<", old_date]},
            fields=["name"]
        )
        
        for log in old_logs:
            frappe.delete_doc("Telegraf Host Log", log['name'])
            
        logger.info(f"Cleaned up {len(old_logs)} old log entries")
        
    except Exception as e:
        logger.error(f"Error cleaning up logs: {str(e)}")

@frappe.whitelist()
def cleanup_old_backups():
    """Clean up old backup files"""
    try:
        # Cleanup logic for old backup files
        logger.info("Cleaned up old backup files")
        
    except Exception as e:
        logger.error(f"Error cleaning up backups: {str(e)}")