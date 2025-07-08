frappe.listview_settings['Telegraf Host'] = {
    add_fields: ["status", "ip_address", "last_status_check"],
    
    get_indicator: function(doc) {
        const status_colors = {
            "Active": "green",
            "Down": "red", 
            "Inactive": "orange",
            "Unknown": "grey"
        };
        
        return [__(doc.status), status_colors[doc.status] || "grey", "status,=," + doc.status];
    },
    
    button: {
        show: function(doc) {
            return true;
        },
        get_label: function() {
            return __('Check Status');
        },
        get_description: function(doc) {
            return __('Check status of {0}', [doc.hostname || doc.name]);
        },
        action: function(doc) {
            frappe.call({
                method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.check_host_status',
                args: {
                    hostname: doc.name
                },
                btn: this,
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert({
                            message: __(r.message.message),
                            indicator: 'green'
                        });
                        // Refresh the list to show updated status
                        cur_list.refresh();
                    }
                },
                error: function(r) {
                    frappe.show_alert({
                        message: __('Failed to check status'),
                        indicator: 'red'
                    });
                }
            });
        }
    },
    
    onload: function(listview) {
        // Add bulk actions
        listview.page.add_menu_item(__("Check All Hosts Status"), function() {
            frappe.confirm(
                __('This will check status of all hosts. Continue?'),
                function() {
                    frappe.call({
                        method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.trigger_status_check',
                        callback: function(r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __(r.message.message),
                                    indicator: 'green'
                                });
                                // Refresh after a delay to show updated statuses
                                setTimeout(() => {
                                    cur_list.refresh();
                                }, 5000);
                            }
                        },
                        error: function() {
                            frappe.show_alert({
                                message: __('Failed to trigger status check'),
                                indicator: 'red'
                            });
                        }
                    });
                }
            );
        });
        
        listview.page.add_menu_item(__("Refresh Status"), function() {
            cur_list.refresh();
            frappe.show_alert({
                message: __('List refreshed'),
                indicator: 'blue'
            });
        });
        
        // Add filters
        listview.page.add_menu_item(__("Show Active Only"), function() {
            listview.filter_area.add([
                ["Telegraf Host", "status", "=", "Active"]
            ]);
        });
        
        listview.page.add_menu_item(__("Show Down Hosts"), function() {
            listview.filter_area.add([
                ["Telegraf Host", "status", "=", "Down"]
            ]);
        });
        
        // Auto refresh every 30 seconds
        if (!listview.auto_refresh_interval) {
            listview.auto_refresh_interval = setInterval(() => {
                if (cur_list && cur_list.doctype === 'Telegraf Host') {
                    cur_list.refresh();
                }
            }, 30000); // 30 seconds
        }
    },
    
    formatters: {
        status: function(value) {
            const colors = {
                "Active": "green",
                "Down": "red",
                "Inactive": "orange", 
                "Unknown": "grey"
            };
            
            return `<span class="indicator ${colors[value] || 'grey'}">${value}</span>`;
        },
        
        last_status_check: function(value) {
            if (!value) return '-';
            return frappe.datetime.comment_when(value);
        },
        
        ip_address: function(value, field, doc) {
            if (!value) return '-';
            return `<code>${value}</code>`;
        }
    }
};

// Custom actions for selected items
frappe.listview_settings['Telegraf Host'].bulk_operations = [
    {
        label: __('Check Status of Selected'),
        action: function(selected_docs) {
            if (selected_docs.length === 0) {
                frappe.msgprint(__('Please select hosts to check'));
                return;
            }
            
            frappe.confirm(
                __('Check status of {0} selected hosts?', [selected_docs.length]),
                function() {
                    let completed = 0;
                    let errors = 0;
                    
                    const progress_dialog = new frappe.ui.Dialog({
                        title: __('Checking Host Status'),
                        fields: [
                            {
                                fieldtype: 'HTML',
                                fieldname: 'progress_html'
                            }
                        ],
                        primary_action_label: __('Close'),
                        primary_action: function() {
                            progress_dialog.hide();
                        }
                    });
                    
                    progress_dialog.show();
                    
                    function update_progress() {
                        const progress_html = `
                            <div class="progress mb-3">
                                <div class="progress-bar" role="progressbar" 
                                     style="width: ${(completed/selected_docs.length)*100}%"
                                     aria-valuenow="${completed}" 
                                     aria-valuemin="0" 
                                     aria-valuemax="${selected_docs.length}">
                                    ${completed}/${selected_docs.length}
                                </div>
                            </div>
                            <p>Completed: ${completed} | Errors: ${errors}</p>
                        `;
                        progress_dialog.fields_dict.progress_html.$wrapper.html(progress_html);
                    }
                    
                    update_progress();
                    
                    selected_docs.forEach(function(doc_name) {
                        frappe.call({
                            method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.check_host_status',
                            args: {
                                hostname: doc_name
                            },
                            callback: function(r) {
                                completed++;
                                if (!r.message || r.message.status !== 'success') {
                                    errors++;
                                }
                                update_progress();
                                
                                if (completed === selected_docs.length) {
                                    setTimeout(() => {
                                        progress_dialog.hide();
                                        cur_list.refresh();
                                        frappe.show_alert({
                                            message: __('Status check completed. {0} successful, {1} errors', [completed - errors, errors]),
                                            indicator: errors > 0 ? 'orange' : 'green'
                                        });
                                    }, 1000);
                                }
                            },
                            error: function() {
                                completed++;
                                errors++;
                                update_progress();
                            }
                        });
                    });
                }
            );
        }
    },
    {
        label: __('Restart Telegraf Service'),
        action: function(selected_docs) {
            if (selected_docs.length === 0) {
                frappe.msgprint(__('Please select hosts'));
                return;
            }
            
            frappe.confirm(
                __('Restart Telegraf service on {0} selected hosts?', [selected_docs.length]),
                function() {
                    selected_docs.forEach(function(doc_name) {
                        frappe.call({
                            method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.manage_telegraf_service',
                            args: {
                                hostname: doc_name,
                                action: 'restart'
                            },
                            callback: function(r) {
                                if (r.message && r.message.status === 'success') {
                                    frappe.show_alert({
                                        message: __('Service restarted on {0}', [doc_name]),
                                        indicator: 'green'
                                    });
                                }
                            }
                        });
                    });
                }
            );
        }
    }
];
