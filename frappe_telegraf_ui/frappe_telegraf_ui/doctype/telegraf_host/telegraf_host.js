frappe.ui.form.on('Telegraf Host', {
    refresh: function(frm) {
        frm.clear_custom_buttons();

        // Status Indicator
        if (frm.doc.status) {
            let color = frm.doc.status === 'Active' ? 'green' :
                       frm.doc.status === 'Down' ? 'red' :
                       frm.doc.status === 'Inactive' ? 'orange' : 'grey';

            frm.dashboard.add_indicator(__('Status: {0}', [frm.doc.status]), color);
        }

        // IP & Check Time Indicator
        if (frm.doc.ip_address) {
            frm.dashboard.add_indicator(__('IP: {0}', [frm.doc.ip_address]), 'blue');
        }

        if (frm.doc.last_status_check) {
            frm.dashboard.add_indicator(__('Last Check: {0}', [frappe.datetime.comment_when(frm.doc.last_status_check)]), 'grey');
        }

        if (!frm.is_new()) {
            // Get Config
            frm.add_custom_button(__('Get Config'), function () {
                frappe.show_alert({ message: __('Fetching Telegraf configuration...'), indicator: 'blue' });

                frappe.call({
                    method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.get_telegraf_config',
                    args: { hostname: frm.doc.name },
                    callback: function (r) {
                        if (r.message) {
                            frm.set_value('telegraf_config', r.message);
                            frappe.show_alert({ message: __('Configuration fetched successfully'), indicator: 'green' });
                            frm.refresh_field('telegraf_config');
                        }
                    },
                    error: function (err) {
                        frappe.show_alert({ message: __('Failed to fetch configuration'), indicator: 'red' });
                        console.error(err);
                    }
                });
            }, __('Configuration'));

            // Update Config
            frm.add_custom_button(__('Update Config'), function () {
                if (!frm.doc.telegraf_config || frm.doc.telegraf_config.trim() === '') {
                    frappe.msgprint({
                        title: __('Configuration Required'),
                        message: __('Configuration field is empty. Please fetch or enter a configuration first.'),
                        indicator: 'orange'
                    });
                    return;
                }

                frappe.confirm(__('Are you sure you want to overwrite the Telegraf configuration on host <b>{0}</b>?', [frm.doc.hostname]), function () {
                    frappe.show_alert({ message: __('Updating configuration...'), indicator: 'blue' });

                    frappe.call({
                        method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.update_telegraf_config',
                        args: {
                            hostname: frm.doc.name,
                            new_config: frm.doc.telegraf_config
                        },
                        callback: function (r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: r.message.message || __('Configuration updated successfully'),
                                    indicator: 'green'
                                });
                            }
                        },
                        error: function (err) {
                            frappe.show_alert({ message: __('Failed to update configuration'), indicator: 'red' });
                        }
                    });
                });
            }, __('Configuration'));

            // Test Config
            frm.add_custom_button(__('Test Config'), function () {
                frappe.show_alert({ message: __('Running Telegraf configuration test...'), indicator: 'blue' });

                frappe.call({
                    method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.test_telegraf_config',
                    args: { hostname: frm.doc.name },
                    callback: function (r) {
                        frappe.hide_alert();
                        const result_dialog = new frappe.ui.Dialog({
                            title: __('Telegraf Test Result for {0}', [frm.doc.hostname]),
                            fields: [
                                {
                                    fieldtype: 'Code',
                                    fieldname: 'test_output',
                                    label: __('Test Output'),
                                    options: 'Text',
                                    default: r.message || __('No output received'),
                                    read_only: 1
                                }
                            ],
                            primary_action_label: __('Close'),
                            primary_action: function () {
                                result_dialog.hide();
                            }
                        });
                        result_dialog.show();
                    },
                    error: function (err) {
                        frappe.hide_alert();
                        frappe.msgprint({
                            title: __('Test Failed'),
                            message: __('Failed to run configuration test'),
                            indicator: 'red'
                        });
                    }
                });
            }, __('Diagnostics'));

            // Check Status
            frm.add_custom_button(__('Check Status'), function () {
                frappe.show_alert({ message: __('Checking host status...'), indicator: 'blue' });

                frappe.call({
                    method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.check_host_status',
                    args: { hostname: frm.doc.name },
                    callback: function (r) {
                        if (r.message) {
                            frm.reload_doc();
                            frappe.show_alert({ message: __('Status updated'), indicator: 'green' });
                        }
                    },
                    error: function (err) {
                        frappe.show_alert({ message: __('Failed to check status'), indicator: 'red' });
                    }
                });
            }, __('Diagnostics'));

            // Service Management
            const service_actions = [
                { action: 'start', label: __('Start'), color: 'green' },
                { action: 'stop', label: __('Stop'), color: 'red' },
                { action: 'restart', label: __('Restart'), color: 'orange' },
                { action: 'reload', label: __('Reload'), color: 'blue' }
            ];

            frm.add_custom_button(__('Service Management'), function () {
                let service_dialog = new frappe.ui.Dialog({
                    title: __('Manage Telegraf Service on {0}', [frm.doc.hostname]),
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'service_info',
                            options: `<div class="alert alert-info">
                                <strong>${__('Service Management')}</strong><br>
                                ${__('Choose an action to perform on the Telegraf service:')}
                            </div>`
                        }
                    ]
                });

                service_actions.forEach(item => {
                    service_dialog.add_custom_action(item.label, function () {
                        service_dialog.hide();

                        frappe.confirm(__('Are you sure you want to <b>{0}</b> the Telegraf service on {1}?', [item.label.toLowerCase(), frm.doc.hostname]), function () {
                            frappe.show_alert({ message: __('Executing {0} command...', [item.label.toLowerCase()]), indicator: 'blue' });

                            frappe.call({
                                method: 'frappe_telegraf_ui.frappe_telegraf_ui.doctype.telegraf_host.telegraf_host.manage_telegraf_service',
                                args: {
                                    hostname: frm.doc.name,
                                    action: item.action
                                },
                                callback: function (r) {
                                    if (r.message) {
                                        frappe.show_alert({
                                            message: r.message.message || __('Service {0} completed', [item.label.toLowerCase()]),
                                            indicator: 'green'
                                        });
                                    }
                                },
                                error: function (err) {
                                    frappe.show_alert({
                                        message: __('Failed to {0} service', [item.label.toLowerCase()]),
                                        indicator: 'red'
                                    });
                                }
                            });
                        });
                    }, `btn-${item.color === 'orange' ? 'warning' : item.color}`);
                });

                service_dialog.show();
            }, __('Service'));
        }
    },

    // Field triggers
    hostname: function (frm) {
        if (frm.doc.hostname && frm.is_new() && !frm.doc.name) {
            frm.set_value('name', frm.doc.hostname);
        }
    },

    ssh_auth_method: function (frm) {
        if (frm.doc.ssh_auth_method === 'Password') {
            frm.set_value('ssh_private_key', '');
        } else if (frm.doc.ssh_auth_method === 'Private Key') {
            frm.set_value('ssh_password', '');
        }
    },

    ip_address: function (frm) {
        const ip_pattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
        if (frm.doc.ip_address && !ip_pattern.test(frm.doc.ip_address)) {
            frappe.msgprint({
                title: __('Invalid IP Address'),
                message: __('Please enter a valid IP address format (e.g., 192.168.1.100)'),
                indicator: 'orange'
            });
        }
    },

    ssh_port: function (frm) {
        if (frm.doc.ssh_port && (frm.doc.ssh_port < 1 || frm.doc.ssh_port > 65535)) {
            frappe.msgprint({
                title: __('Invalid Port'),
                message: __('SSH port must be between 1 and 65535'),
                indicator: 'orange'
            });
            frm.set_value('ssh_port', 22);
        }
    }
});

// Add monospace styling
frappe.ui.form.on('Telegraf Host', {
    onload: function (frm) {
        if (!$('#telegraf-host-custom-css').length) {
            $('head').append(`
                <style id="telegraf-host-custom-css">
                    .form-dashboard .form-dashboard-section .indicator {
                        margin-right: 10px;
                    }
                    .telegraf-config-field textarea {
                        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace !important;
                        font-size: 12px;
                    }
                </style>
            `);
        }

        setTimeout(() => {
            $('[data-fieldname="telegraf_config"] textarea').addClass('telegraf-config-field');
        }, 500);
    }
});
