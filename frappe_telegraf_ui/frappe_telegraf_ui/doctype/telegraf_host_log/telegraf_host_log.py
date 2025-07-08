import frappe
from frappe.model.document import Document

class TelegrafHostLog(Document):
    def validate(self):
        """Validate log entry before saving"""
        if not self.timestamp:
            self.timestamp = frappe.utils.now()
            
        # Ensure host exists
        if self.host and not frappe.db.exists("Telegraf Host", self.host):
            frappe.throw(f"Host '{self.host}' does not exist")
    
    def before_insert(self):
        """Set timestamp if not already set"""
        if not self.timestamp:
            self.timestamp = frappe.utils.now()
    
    def on_update(self):
        """Handle post-save operations"""
        pass
    
    def on_trash(self):
        """Handle before delete operations"""
        pass

@frappe.whitelist()
def get_host_logs(hostname, limit=50):
    """Get logs for a specific host"""
    try:
        logs = frappe.get_all(
            "Telegraf Host Log",
            filters={"host": hostname},
            fields=["name", "event_type", "old_status", "new_status", "response_time", "timestamp", "details"],
            order_by="timestamp desc",
            limit=limit
        )
        return {"status": "success", "logs": logs}
    except Exception as e:
        frappe.log_error(f"Error getting host logs: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_recent_status_changes(days=7):
    """Get recent status changes across all hosts"""
    try:
        from frappe.utils import add_to_date, get_datetime
        
        since_date = add_to_date(get_datetime(), days=-days)
        
        logs = frappe.get_all(
            "Telegraf Host Log",
            filters={
                "event_type": "Status Change",
                "timestamp": [">=", since_date]
            },
            fields=["host", "old_status", "new_status", "timestamp", "response_time"],
            order_by="timestamp desc"
        )
        
        return {"status": "success", "logs": logs}
    except Exception as e:
        frappe.log_error(f"Error getting recent status changes: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def cleanup_old_logs(days=30):
    """Clean up logs older than specified days"""
    try:
        from frappe.utils import add_to_date, get_datetime
        
        cutoff_date = add_to_date(get_datetime(), days=-days)
        
        old_logs = frappe.get_all(
            "Telegraf Host Log",
            filters={"timestamp": ["<", cutoff_date]},
            fields=["name"]
        )
        
        count = 0
        for log in old_logs:
            frappe.delete_doc("Telegraf Host Log", log.name, ignore_permissions=True)
            count += 1
        
        frappe.db.commit()
        
        return {
            "status": "success", 
            "message": f"Cleaned up {count} log entries older than {days} days"
        }
    except Exception as e:
        frappe.log_error(f"Error cleaning up logs: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_log_statistics():
    """Get statistics about logs"""
    try:
        # Count by event type
        event_stats = frappe.db.sql("""
            SELECT event_type, COUNT(*) as count
            FROM `tabTelegraf Host Log`
            GROUP BY event_type
            ORDER BY count DESC
        """, as_dict=True)
        
        # Count by host
        host_stats = frappe.db.sql("""
            SELECT host, COUNT(*) as count
            FROM `tabTelegraf Host Log`
            GROUP BY host
            ORDER BY count DESC
            LIMIT 10
        """, as_dict=True)
        
        # Recent activity (last 24 hours)
        from frappe.utils import add_to_date, get_datetime
        yesterday = add_to_date(get_datetime(), hours=-24)
        
        recent_count = frappe.db.count(
            "Telegraf Host Log",
            filters={"timestamp": [">=", yesterday]}
        )
        
        total_logs = frappe.db.count("Telegraf Host Log")
        
        return {
            "status": "success",
            "statistics": {
                "total_logs": total_logs,
                "recent_activity": recent_count,
                "event_types": event_stats,
                "top_hosts": host_stats
            }
        }
    except Exception as e:
        frappe.log_error(f"Error getting log statistics: {str(e)}")
        return {"status": "error", "message": str(e)}