//#\programming\python\frappe_telegraf_ui\frappe_telegraf_ui\doctype\telegraf_host_log\telegraf_host_log_list.js
frappe.listview_settings['Telegraf Host Log'] = {
    add_fields: ["event_type", "host", "timestamp"],
    
    get_indicator: function(doc) {
        const event_colors = {
            "Status Change": "blue",
            "Config Update": "green", 
            "Connection Error": "red",
            "Service Restart": "orange"
        };
        
        return [__(doc.event_type), event_colors[doc.event_type] || "grey", "event_type,=," + doc.event_type];
    },
    
    onload: function(listview) {
        listview.page.add_menu_item(__("Cleanup Old Logs"), function() {
            frappe.prompt(
                {
                    label: __('Delete logs older than (days)'),
                    fieldname: 'days',
                    fieldtype: 'Int',
                    default: 30,
                    reqd: 1
                },
                function(values) {
                    frappe.call({
                        method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host_log.telegraf_host_log.cleanup_old_logs',
                        args: {
                            days: values.days
                        },
                        callback: function(r) {
                            if (r.message && r.message.status === 'success') {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                });
                                cur_list.refresh();
                            }
                        }
                    });
                },
                __('Cleanup Logs'),
                __('Delete')
            );
        });
        
        listview.page.add_menu_item(__("View Statistics"), function() {
            frappe.call({
                method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host_log.telegraf_host_log.get_log_statistics',
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        const stats = r.message.statistics;
                        
                        let html = `
                            <div class="row">
                                <div class="col-md-6">
                                    <h5>Overall Statistics</h5>
                                    <p><strong>Total Logs:</strong> ${stats.total_logs}</p>
                                    <p><strong>Recent Activity (24h):</strong> ${stats.recent_activity}</p>
                                    
                                    <h6>Event Types</h6>
                                    <ul>
                        `;
                        
                        stats.event_types.forEach(event => {
                            html += `<li>${event.event_type}: ${event.count}</li>`;
                        });
                        
                        html += `
                                    </ul>
                                </div>
                                <div class="col-md-6">
                                    <h6>Top Hosts by Log Count</h6>
                                    <ul>
                        `;
                        
                        stats.top_hosts.forEach(host => {
                            html += `<li>${host.host}: ${host.count}</li>`;
                        });
                        
                        html += `
                                    </ul>
                                </div>
                            </div>
                        `;
                        
                        frappe.msgprint({
                            title: __('Log Statistics'),
                            message: html,
                            wide: true
                        });
                    }
                }
            });
        });
    },
    
    formatters: {
        timestamp: function(value) {
            return frappe.datetime.comment_when(value);
        },
        
        response_time: function(value) {
            if (!value) return '-';
            return `${value.toFixed(2)} ms`;
        }
    }
};