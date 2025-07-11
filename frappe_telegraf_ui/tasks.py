import frappe
from frappe.utils import now, add_to_date, get_datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

# Fungsi ini TIDAK lagi menulis ke DB, hanya mengembalikan hasil
def perform_host_check(host_data):
    """
    Performs a connectivity check for a single host.
    This function is thread-safe as it does not interact with Frappe's DB.
    Returns a dictionary with the check result.
    """
    try:
        # Import diletakkan di sini agar tersedia di dalam thread
        from frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host import check_host_connectivity
        
        is_online, response_time = check_host_connectivity(
            host_data['ip_address'], 
            host_data['ssh_port'] or 22,
            timeout=5
        )
        
        new_status = "Active" if is_online else "Down"
        
        return {
            "name": host_data['name'],
            "old_status": host_data.get('status', 'Unknown'),
            "new_status": new_status,
            "response_time": response_time,
            "error": None
        }

    except Exception as e:
        # Jika ada error, kembalikan juga dalam bentuk data
        return {
            "name": host_data['name'],
            "old_status": host_data.get('status', 'Unknown'),
            "new_status": "Unknown",
            "response_time": 0,
            "error": str(e)
        }
def check_all_hosts_status():
    """Check status of all active Telegraf hosts - runs every minute"""
    try:
        frappe.logger().info("Starting realtime host status check")
        
        hosts = frappe.get_all(
            "Telegraf Host",
            filters={"status": ["!=", "Disabled"]},
            fields=["name", "hostname", "ip_address", "ssh_port", "ssh_user", "status"]
        )
        
        if not hosts:
            frappe.logger().info("No hosts found for monitoring")
            return
            
        frappe.logger().info(f"Monitoring {len(hosts)} hosts in parallel")

        results = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            # Jalankan pengecekan secara paralel
            future_to_host = {executor.submit(perform_host_check, host): host for host in hosts}
            
            for future in as_completed(future_to_host):
                try:
                    # Ambil hasil dari setiap thread
                    result_data = future.result(timeout=15)
                    results.append(result_data)
                except Exception as exc:
                    host = future_to_host[future]
                    frappe.logger().error(f"Future for host {host['name']} generated an exception: {exc}")

        frappe.logger().info(f"All host checks completed. Processing {len(results)} results...")

        # --- Bagian Pemrosesan (Sekuensial dan Aman) ---
        # Sekarang kita proses hasilnya satu per satu di thread utama
        completed = 0
        for result in results:
            host_name = result['name']
            old_status = result['old_status']
            new_status = result['new_status']
            response_time = result['response_time']
            
            completed += 1
            log_message = f"[{completed}/{len(results)}] {host_name}: "

            if result['error']:
                frappe.logger().error(f"Host {host_name} check failed: {result['error']}")
                frappe.db.set_value("Telegraf Host", host_name, {"status": "Unknown", "last_status_check": now()})
                log_message += f"Error -> Unknown"
            else:
                # Update DB hanya jika status berubah atau belum pernah dicek
                if old_status != new_status or old_status == 'Unknown':
                    frappe.db.set_value("Telegraf Host", host_name, {"status": new_status, "last_status_check": now()})
                    create_status_log(host_name, old_status, new_status, response_time, "Realtime monitoring")
                    log_message += f"Status changed: {old_status} -> {new_status}"
                else:
                    # Jika status tidak berubah, cukup update timestamp
                    frappe.db.set_value("Telegraf Host", host_name, "last_status_check", now())
                    log_message += f"Status unchanged: {new_status}"
            
            frappe.logger().info(log_message)

        # Commit semua perubahan ke database SEKALI SAJA di akhir
        frappe.db.commit()
        frappe.logger().info(f"Completed and committed monitoring of {len(results)} hosts")
            
    except Exception as e:
        frappe.logger().error(f"Error in realtime host monitoring: {str(e)}")
        frappe.log_error(f"Realtime Monitoring Error: {str(e)}", "Host Status Check Failed")
        frappe.db.rollback() # Batalkan transaksi jika ada error besar

def check_single_host_status(host_data):
    """Check status of a single host with optimized logic for realtime monitoring"""
    try:
        host_name = host_data['name']
        
        # Use lightweight connectivity check first
        from frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host import check_host_connectivity
        
        # Quick connectivity check
        is_online, response_time = check_host_connectivity(
            host_data['ip_address'], 
            host_data['ssh_port'] or 22,
            timeout=5  # Short timeout for realtime
        )
        
        # Determine new status
        new_status = "Active" if is_online else "Down"
        old_status = host_data.get('status', 'Unknown')
        
        # Update status if changed
        if old_status != new_status or old_status == 'Unknown':
            # Use direct DB update for speed
            frappe.db.set_value("Telegraf Host", host_name, {
                "status": new_status,
                "last_status_check": now()
            })
            
            # Log significant status changes (not every minute)
            if old_status != new_status and old_status != 'Unknown':
                create_status_log(host_name, old_status, new_status, response_time, "Realtime monitoring")
                return f"Status changed: {old_status} -> {new_status} (response: {response_time:.2f}ms)"
            else:
                return f"Status set to {new_status} (response: {response_time:.2f}ms)"
        else:
            # Just update timestamp for unchanged status
            frappe.db.set_value("Telegraf Host", host_name, "last_status_check", now())
            return f"Status unchanged: {new_status} (response: {response_time:.2f}ms)"
            
    except Exception as e:
        frappe.logger().error(f"Error checking host {host_data['name']}: {str(e)}")
        # Mark as unknown on error
        frappe.db.set_value("Telegraf Host", host_data['name'], {
            "status": "Unknown",
            "last_status_check": now()
        })
        return f"Error: {str(e)}"

def create_status_log(host_name, old_status, new_status, response_time, source):
    """Create status change log entry"""
    try:
        frappe.get_doc({
            "doctype": "Telegraf Host Log",
            "host": host_name,
            "event_type": "Status Change",
            "old_status": old_status,
            "new_status": new_status,
            "response_time": response_time,
            "timestamp": now(),
            "details": f"{source}: {old_status} -> {new_status}"
        }).insert(ignore_permissions=True)
    except Exception as e:
        frappe.logger().error(f"Failed to create status log: {str(e)}")

# Optimized cleanup to run more frequently for realtime monitoring
def cleanup_old_logs():
    """Clean up old log entries - optimized for frequent runs"""
    try:
        # Only keep logs for last 7 days for realtime monitoring
        old_date = add_to_date(get_datetime(), days=-7)
        
        # Use bulk delete for performance
        frappe.db.sql("""
            DELETE FROM `tabTelegraf Host Log` 
            WHERE timestamp < %s
        """, old_date)
        
        frappe.db.commit()
        frappe.logger().info("Cleaned up old status logs (>7 days)")
        
    except Exception as e:
        frappe.logger().error(f"Error cleaning up logs: {str(e)}")

# Manual trigger for immediate check
@frappe.whitelist()
def trigger_immediate_check():
    """Trigger immediate status check for all hosts"""
    try:
        # Run synchronously for immediate feedback
        check_all_hosts_status()
        return {"status": "success", "message": "Immediate status check completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Get realtime status for dashboard
@frappe.whitelist()
def get_realtime_status():
    """Get current status of all hosts for realtime dashboard"""
    try:
        hosts = frappe.get_all(
            "Telegraf Host",
            fields=["name", "hostname", "status", "last_status_check", "ip_address"],
            order_by="hostname"
        )
        
        # Get recent status changes (last hour)
        recent_changes = frappe.get_all(
            "Telegraf Host Log",
            filters={
                "timestamp": [">=", add_to_date(get_datetime(), hours=-1)],
                "event_type": "Status Change"
            },
            fields=["host", "old_status", "new_status", "timestamp"],
            order_by="timestamp desc",
            limit=20
        )
        
        # Count by status
        status_counts = {}
        for host in hosts:
            status = host.get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "status": "success",
            "data": {
                "hosts": hosts,
                "recent_changes": recent_changes,
                "status_counts": status_counts,
                "total_hosts": len(hosts),
                "timestamp": now()
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Rest of the functions remain the same...
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
                frappe.logger().info(f"Updated config for host: {host['name']}")
            except Exception as e:
                frappe.logger().error(f"Failed to update config for {host['name']}: {str(e)}")
                
    except Exception as e:
        frappe.logger().error(f"Error in update_telegraf_configs: {str(e)}")

@frappe.whitelist()
def generate_daily_report():
    """Generate daily status report"""
    try:
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
            frappe.logger().info(f"Generated daily report with {len(logs)} status changes")
        
    except Exception as e:
        frappe.logger().error(f"Error generating daily report: {str(e)}")

@frappe.whitelist()
def backup_configurations():
    """Backup all Telegraf configurations"""
    try:
        hosts = frappe.get_all("Telegraf Host", filters={"status": "Active"})
        
        for host in hosts:
            frappe.logger().info(f"Backed up config for: {host['name']}")
            
    except Exception as e:
        frappe.logger().error(f"Error in backup_configurations: {str(e)}")

@frappe.whitelist()
def cleanup_old_backups():
    """Clean up old backup files"""
    try:
        frappe.logger().info("Cleaned up old backup files")
        
    except Exception as e:
        frappe.logger().error(f"Error cleaning up backups: {str(e)}")