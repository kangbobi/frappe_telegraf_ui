// frappe_telegraf_ui/doctype/telegraf_host/telegraf_host.js

frappe.ui.form.on('Telegraf Host', {
    refresh: function(frm) {
        // Hapus tombol-tombol lama agar tidak menumpuk saat refresh
        frm.remove_custom_button(__('Get Config'));
        frm.remove_custom_button(__('Update Config'));
        frm.remove_custom_button(__('Test Config'));
        frm.remove_custom_button(__('Service'));

        // Tombol untuk mengambil konfigurasi dari host
        frm.add_custom_button(__('Get Config'), function() {
            frm.call('get_telegraf_config', { hostname: frm.doc.name })
                .then(r => {
                    frm.set_value('telegraf_config', r.message);
                    frappe.msgprint(__('Telegraf config fetched successfully.'));
                    frm.refresh_field('telegraf_config');
                });
        }).addClass('btn-primary');

        // Tombol untuk memperbarui konfigurasi di host
        frm.add_custom_button(__('Update Config'), function() {
            if (!frm.doc.telegraf_config) {
                frappe.msgprint(__('Config field is empty. Fetch config first.'));
                return;
            }
            frappe.confirm('Are you sure you want to overwrite the config on the host?', () => {
                frm.call('update_telegraf_config', {
                    hostname: frm.doc.name,
                    new_config: frm.doc.telegraf_config
                }).then(r => {
                    if (r.message) frappe.msgprint(r.message.message);
                });
            });
        });

        // Tombol BARU untuk Test Config
        frm.add_custom_button(__('Test Config'), function() {
            frappe.show_alert({ message: 'Running test...', indicator: 'gray' });
            frm.call('test_telegraf_config', { hostname: frm.doc.name })
                .then(r => {
                    frappe.hide_alert();
                    frappe.msgprint({
                        title: __('Telegraf Test Result'),
                        indicator: 'green',
                        message: `<pre style="white-space: pre-wrap; word-break: break-all;">${r.message}</pre>`
                    });
                });
        });

        // Grup Tombol BARU untuk Service Management
        let service_actions = ['Start', 'Stop', 'Restart', 'Reload'];
        let service_group = frm.add_custom_button(__('Service'), null, "btn-secondary");

        service_group.parent().addClass("btn-group");

        let dropdown_menu = $(`
            <ul class="dropdown-menu" role="menu">
                ${service_actions.map(action => `
                    <li><a class="dropdown-item" href="#" data-action="${action.toLowerCase()}">${__ (action)}</a></li>
                `).join("")}
            </ul>
        `);

        service_group.parent().append(dropdown_menu);
        service_group.attr("data-bs-toggle", "dropdown");

        dropdown_menu.find("a").on("click", function(e) {
            e.preventDefault();
            let action = $(this).data("action");

            frappe.confirm(`Are you sure you want to <b>${action}</b> the Telegraf service on ${frm.doc.name}?`, () => {
                frm.call('manage_telegraf_service', {
                    hostname: frm.doc.name,
                    action: action
                }).then(r => {
                    if (r.message) frappe.msgprint(r.message.message);
                });
            });
        });
    }
});
