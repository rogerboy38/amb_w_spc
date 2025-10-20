// Copyright (c) 2025, AMB-Wellness and contributors
// For license information, please see license.txt

frappe.ui.form.on('Material Assessment Log', {
	refresh: function(frm) {
		// Style the zone status field
		style_zone_status(frm);
		
		// Add custom buttons
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('View Work Order'), function() {
				if (frm.doc.work_order) {
					frappe.set_route('Form', 'Work Order', frm.doc.work_order);
				}
			});
			
			if (frm.doc.mrp_planning) {
				frm.add_custom_button(__('View MRP Planning'), function() {
					frappe.set_route('Form', 'MRP Planning', frm.doc.mrp_planning);
				});
			}
			
			frm.add_custom_button(__('Show Missing Materials'), function() {
				show_missing_materials_dialog(frm);
			});
			
			frm.add_custom_button(__('Assessment Summary'), function() {
				show_assessment_summary(frm);
			}, __('Reports'));
			
			if (frm.doc.plant_code) {
				frm.add_custom_button(__('Warehouse Status'), function() {
					show_warehouse_status(frm);
				}, __('Reports'));
			}
			
			// Add create stock entry button if work order exists and zone is green
			if (frm.doc.work_order && frm.doc.zone_status === 'Green Zone' && frm.doc.docstatus === 1) {
				frm.add_custom_button(__('Create Stock Entry'), function() {
					create_stock_entry_from_assessment(frm);
				}, __('Actions'));
			}
		}
		
		// Auto-populate items from work order if empty
		if (frm.doc.work_order && (!frm.doc.items || frm.doc.items.length === 0) && frm.doc.__islocal) {
			frm.add_custom_button(__('Load Items from Work Order'), function() {
				load_items_from_work_order(frm);
			}, __('Actions'));
		}
	},
	
	work_order: function(frm) {
		if (frm.doc.work_order) {
			// Get current zone status from Work Order
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Work Order',
					name: frm.doc.work_order,
					fieldname: ['custom_current_zone_status', 'custom_material_completion_percentage', 'custom_missing_materials_json']
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('zone_status', r.message.custom_current_zone_status);
						frm.set_value('completion_percentage', r.message.custom_material_completion_percentage);
						frm.set_value('missing_materials', r.message.custom_missing_materials_json);
					}
				}
			});
		}
	},
	
	zone_status: function(frm) {
		style_zone_status(frm);
	},
	
	onload: function(frm) {
		// Initialize custom CSS for Material Assessment Log
		initialize_assessment_css();
	}
});

function initialize_assessment_css() {
	// Only add CSS once
	if ($('#material-assessment-custom-css').length) return;
	
	$('<style id="material-assessment-custom-css">')
		.prop('type', 'text/css')
		.html(`
			.zone-red .control-input {
				border-left: 4px solid #dc3545 !important;
				background-color: rgba(220, 53, 69, 0.1);
			}
			.zone-green .control-input {
				border-left: 4px solid #28a745 !important;
				background-color: rgba(40, 167, 69, 0.1);
			}
			.assessment-summary {
				padding: 20px;
				max-height: 600px;
				overflow-y: auto;
			}
			.summary-header {
				margin-bottom: 20px;
				padding-bottom: 10px;
				border-bottom: 2px solid #e0e0e0;
			}
			.summary-meta {
				display: flex;
				gap: 20px;
				flex-wrap: wrap;
				margin-top: 10px;
				font-size: 13px;
			}
			.zone-badge {
				padding: 3px 8px;
				border-radius: 12px;
				color: white;
				font-weight: bold;
				font-size: 11px;
			}
			.zone-badge.green {
				background-color: #28a745;
			}
			.zone-badge.red {
				background-color: #dc3545;
			}
			.items-summary {
				margin: 20px 0;
			}
			.completion-stats {
				margin-top: 20px;
				padding: 15px;
				background-color: #f8f9fa;
				border-radius: 6px;
			}
			.stat-item {
				margin-bottom: 8px;
				font-size: 14px;
			}
			.warehouse-status-display {
				padding: 15px;
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
				gap: 15px;
			}
			.warehouse-zone {
				padding: 15px;
				border: 1px solid #e0e0e0;
				border-radius: 8px;
				background-color: #ffffff;
				text-align: center;
			}
			.warehouse-zone h5 {
				margin-bottom: 10px;
				color: #2e3c4d;
				font-size: 14px;
			}
			.warehouse-name {
				margin-bottom: 10px;
				font-weight: bold;
				color: #007bff;
			}
			.stock-status {
				padding: 15px;
			}
			.stock-status h5 {
				margin-bottom: 15px;
				color: #2e3c4d;
			}
		`)
		.appendTo('head');
}

function style_zone_status(frm) {
	if (frm.doc.zone_status) {
		const zone_field = frm.get_field('zone_status');
		if (zone_field) {
			const zone_wrapper = zone_field.$wrapper;
			
			// Remove existing classes
			zone_wrapper.removeClass('zone-red zone-green');
			
			// Add appropriate class
			if (frm.doc.zone_status === 'Red Zone') {
				zone_wrapper.addClass('zone-red');
			} else if (frm.doc.zone_status === 'Green Zone') {
				zone_wrapper.addClass('zone-green');
			}
		}
	}
}

function show_missing_materials_dialog(frm) {
	if (!frm.doc.missing_materials) {
		frappe.msgprint(__('No missing materials data available'));
		return;
	}
	
	try {
		const missing_materials = JSON.parse(frm.doc.missing_materials);
		
		const dialog = new frappe.ui.Dialog({
			title: __('Missing Materials'),
			fields: [
				{
					fieldname: 'materials_html',
					fieldtype: 'HTML'
				}
			]
		});
		
		// Generate HTML table
		let html = '<table class="table table-bordered"><thead><tr>';
		html += '<th>Item Code</th><th>Item Name</th><th>Required</th><th>Available</th><th>Missing</th><th>Warehouse</th>';
		html += '</tr></thead><tbody>';
		
		missing_materials.forEach(function(item) {
			html += `<tr>`;
			html += `<td>${item.item_code}</td>`;
			html += `<td>${item.item_name}</td>`;
			html += `<td>${item.required_qty}</td>`;
			html += `<td>${item.available_qty}</td>`;
			html += `<td class="text-danger">${item.missing_qty}</td>`;
			html += `<td>${item.warehouse}</td>`;
			html += `</tr>`;
		});
		
		html += '</tbody></table>';
		
		dialog.fields_dict.materials_html.$wrapper.html(html);
		dialog.show();
		
	} catch (e) {
		frappe.msgprint(__('Error parsing missing materials data'));
	}
}

function load_items_from_work_order(frm) {
	if (!frm.doc.work_order) {
		frappe.msgprint(__('Please select a Work Order first'));
		return;
	}
	
	frappe.call({
		method: 'amb_w_spc.sfc_manufacturing.doctype.material_assessment_log.material_assessment_log.create_assessment_from_work_order',
		args: {
			work_order_name: frm.doc.work_order
		},
		callback: function(r) {
			if (r.message && r.message.status === 'success') {
				frappe.msgprint(__('Items loaded successfully from Work Order'));
				frm.reload_doc();
			} else {
				frappe.msgprint(__('Failed to load items: {0}', [r.message.message || 'Unknown error']));
			}
		}
	});
}

function show_assessment_summary(frm) {
	let summary_html = '<div class="assessment-summary">';
	
	// Header
	summary_html += `<div class="summary-header">
		<h4>Assessment Summary</h4>
		<div class="summary-meta">
			<span><strong>Assessment Type:</strong> ${frm.doc.assessment_type || 'N/A'}</span>
			<span><strong>Plant Code:</strong> ${frm.doc.plant_code || 'N/A'}</span>
			<span><strong>Zone Status:</strong> 
				<span class="zone-badge ${frm.doc.zone_status === 'Green Zone' ? 'green' : 'red'}">
					${frm.doc.zone_status || 'Unknown'}
				</span>
			</span>
		</div>
	</div>`;
	
	// Items summary
	if (frm.doc.items && frm.doc.items.length > 0) {
		summary_html += '<div class="items-summary">';
		summary_html += '<h5>Material Status</h5>';
		summary_html += '<table class="table table-bordered">';
		summary_html += '<thead><tr><th>Item</th><th>Required</th><th>Available</th><th>Status</th></tr></thead><tbody>';
		
		frm.doc.items.forEach(function(item) {
			let status_class = item.status === 'Available' ? 'text-success' : (item.status === 'Partial' ? 'text-warning' : 'text-danger');
			summary_html += `<tr>
				<td>${item.item_code}<br><small class="text-muted">${item.item_name || ''}</small></td>
				<td>${item.required_qty || 0} ${item.uom || ''}</td>
				<td>${item.available_qty || 0} ${item.uom || ''}</td>
				<td><span class="${status_class}">${item.status || 'Unknown'}</span></td>
			</tr>`;
		});
		
		summary_html += '</tbody></table></div>';
	}
	
	// Completion stats
	summary_html += `<div class="completion-stats">
		<h5>Completion Statistics</h5>
		<div class="stat-item">
			<strong>Material Completion:</strong> ${(frm.doc.completion_percentage || 0).toFixed(1)}%
		</div>
		<div class="stat-item">
			<strong>Total Items:</strong> ${frm.doc.total_requirements || (frm.doc.items ? frm.doc.items.length : 0)}
		</div>
		<div class="stat-item">
			<strong>Assessment Date:</strong> ${frappe.datetime.str_to_user(frm.doc.assessment_date)}
		</div>
	</div>`;
	
	summary_html += '</div>';
	
	let dialog = new frappe.ui.Dialog({
		title: __('Assessment Summary - {0}', [frm.doc.name]),
		size: 'large',
		fields: [{
			fieldtype: 'HTML',
			fieldname: 'summary_html',
			options: summary_html
		}],
		primary_action_label: __('Close'),
		primary_action: function() {
			dialog.hide();
		}
	});
	
	dialog.show();
}

function show_warehouse_status(frm) {
	if (!frm.doc.plant_code) {
		frappe.msgprint(__('Plant Code is required to show warehouse status'));
		return;
	}
	
	// Get warehouse zones for this plant
	frappe.call({
		method: 'amb_w_spc.sfc_manufacturing.doctype.mrp_planning.mrp_planning.get_warehouse_zones_mapping',
		callback: function(r) {
			if (r.message && r.message.status === 'success') {
				let plant_warehouses = r.message.warehouse_mapping[frm.doc.plant_code];
				if (plant_warehouses) {
					display_warehouse_status_dialog(plant_warehouses, frm);
				} else {
					frappe.msgprint(__('No warehouse mapping found for plant: {0}', [frm.doc.plant_code]));
				}
			} else {
				frappe.msgprint(__('Failed to load warehouse mapping'));
			}
		}
	});
}

function display_warehouse_status_dialog(warehouses, frm) {
	let warehouse_html = '<div class="warehouse-status-display">';
	
	Object.keys(warehouses).forEach(function(zone_type) {
		let warehouse_name = warehouses[zone_type];
		warehouse_html += `<div class="warehouse-zone">
			<h5>${zone_type.replace('_', ' ').toUpperCase()}</h5>
			<div class="warehouse-name">${warehouse_name}</div>
			<button class="btn btn-sm btn-primary" onclick="check_warehouse_stock('${warehouse_name}')">
				Check Stock
			</button>
		</div>`;
	});
	
	warehouse_html += '</div>';
	
	let dialog = new frappe.ui.Dialog({
		title: __('Warehouse Status - {0} Plant', [frm.doc.plant_code.toUpperCase()]),
		size: 'large',
		fields: [{
			fieldtype: 'HTML',
			fieldname: 'warehouse_html',
			options: warehouse_html
		}],
		primary_action_label: __('Close'),
		primary_action: function() {
			dialog.hide();
		}
	});
	
	dialog.show();
	
	// Make check_warehouse_stock globally available
	window.check_warehouse_stock = function(warehouse_name) {
		// Get item codes from assessment items
		let item_codes = [];
		if (frm.doc.items) {
			item_codes = frm.doc.items.map(item => item.item_code);
		}
		
		frappe.call({
			method: 'amb_w_spc.sfc_manufacturing.doctype.material_assessment_log.material_assessment_log.get_warehouse_material_status',
			args: {
				warehouse: warehouse_name,
				item_codes: JSON.stringify(item_codes)
			},
			callback: function(r) {
				if (r.message && r.message.status === 'success') {
					display_stock_status(r.message.material_status, warehouse_name);
				} else {
					frappe.msgprint(__('Failed to load stock status'));
				}
			}
		});
	};
}

function display_stock_status(stock_data, warehouse_name) {
	let stock_html = `<div class="stock-status">
		<h5>Stock Status - ${warehouse_name}</h5>
		<table class="table table-bordered table-striped">
			<thead>
				<tr>
					<th>Item Code</th>
					<th>Item Name</th>
					<th>Actual Qty</th>
					<th>Reserved</th>
					<th>Ordered</th>
					<th>Projected</th>
				</tr>
			</thead>
			<tbody>`;
	
	stock_data.forEach(function(item) {
		stock_html += `<tr>
			<td>${item.item_code}</td>
			<td>${item.item_name}</td>
			<td>${item.actual_qty} ${item.uom}</td>
			<td>${item.reserved_qty} ${item.uom}</td>
			<td>${item.ordered_qty} ${item.uom}</td>
			<td>${item.projected_qty} ${item.uom}</td>
		</tr>`;
	});
	
	stock_html += '</tbody></table></div>';
	
	let stock_dialog = new frappe.ui.Dialog({
		title: __('Stock Status - {0}', [warehouse_name]),
		size: 'extra-large',
		fields: [{
			fieldtype: 'HTML',
			fieldname: 'stock_html',
			options: stock_html
		}],
		primary_action_label: __('Close'),
		primary_action: function() {
			stock_dialog.hide();
		}
	});
	
	stock_dialog.show();
}

function create_stock_entry_from_assessment(frm) {
	if (!frm.doc.work_order) {
		frappe.msgprint(__('Work Order is required to create Stock Entry'));
		return;
	}
	
	frappe.confirm(
		__('This will create a Stock Entry for Material Issue based on this assessment. Continue?'),
		function() {
			frappe.call({
				method: 'amb_w_spc.sfc_manufacturing.warehouse_management.stock_entry.make_custom_stock_entry',
				args: {
					work_order: frm.doc.work_order,
					purpose: 'Material Issue'
				},
				callback: function(r) {
					if (r.message) {
						frappe.msgprint(__('Stock Entry created successfully'));
						frappe.set_route('Form', 'Stock Entry', r.message.name);
					} else {
						frappe.msgprint(__('Failed to create Stock Entry'));
					}
				}
			});
		}
	);
}

// Enhanced field events
frappe.ui.form.on('Material Assessment Log Item', {
	item_code: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_code) {
			// Auto-fetch item details
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Item',
					name: row.item_code,
					fieldname: ['item_name', 'stock_uom']
				},
				callback: function(r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
						frappe.model.set_value(cdt, cdn, 'uom', r.message.stock_uom);
					}
				}
			});
			
			// Get available quantity if warehouse is set
			if (row.warehouse) {
				get_available_qty_for_item(frm, cdt, cdn);
			}
		}
	},
	
	warehouse: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_code && row.warehouse) {
			get_available_qty_for_item(frm, cdt, cdn);
		}
	},
	
	required_qty: function(frm, cdt, cdn) {
		calculate_shortage(frm, cdt, cdn);
	},
	
	available_qty: function(frm, cdt, cdn) {
		calculate_shortage(frm, cdt, cdn);
	}
});

function get_available_qty_for_item(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	
	frappe.call({
		method: 'frappe.client.get_value',
		args: {
			doctype: 'Bin',
			filters: {
				item_code: row.item_code,
				warehouse: row.warehouse
			},
			fieldname: 'actual_qty'
		},
		callback: function(r) {
			if (r.message && r.message.actual_qty !== undefined) {
				frappe.model.set_value(cdt, cdn, 'available_qty', r.message.actual_qty);
			} else {
				frappe.model.set_value(cdt, cdn, 'available_qty', 0);
			}
		}
	});
}

function calculate_shortage(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let shortage = Math.max(0, (row.required_qty || 0) - (row.available_qty || 0));
	frappe.model.set_value(cdt, cdn, 'shortage_qty', shortage);
	
	// Update status
	let status;
	if ((row.available_qty || 0) >= (row.required_qty || 0)) {
		status = 'Available';
	} else if ((row.available_qty || 0) > 0) {
		status = 'Partial';
	} else {
		status = 'Shortage';
	}
	frappe.model.set_value(cdt, cdn, 'status', status);
}
