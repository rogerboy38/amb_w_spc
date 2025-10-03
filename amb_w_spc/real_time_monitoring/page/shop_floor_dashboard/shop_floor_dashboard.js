// Copyright (c) 2025, MiniMax Agent and contributors
// Shop Floor Dashboard - Real-time monitoring interface

frappe.pages['shop-floor-dashboard'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Shop Floor Dashboard',
        single_column: false
    });
    
    new ShopFloorDashboard(page);
};

class ShopFloorDashboard {
    constructor(page) {
        this.page = page;
        this.refresh_interval = 30000; // 30 seconds
        this.chart_data = {};
        this.init();
    }
    
    init() {
        this.setup_page_actions();
        this.setup_realtime_updates();
        this.make_dashboard();
        this.refresh_data();
        this.start_auto_refresh();
    }
    
    setup_page_actions() {
        // Add refresh button
        this.page.add_action_icon("fa fa-refresh", () => {
            this.refresh_data();
        });
        
        // Add settings button
        this.page.add_action_icon("fa fa-cog", () => {
            this.show_settings_dialog();
        });
        
        // Add fullscreen button
        this.page.add_action_icon("fa fa-expand", () => {
            this.toggle_fullscreen();
        });
    }
    
    setup_realtime_updates() {
        // Listen for real-time sensor data updates
        frappe.realtime.on('sensor_data_update', (data) => {
            this.update_sensor_display(data);
        });
        
        // Listen for station status changes
        frappe.realtime.on('station_status_change', (data) => {
            this.update_station_status(data);
        });
        
        // Listen for new alerts
        frappe.realtime.on('new_alert', (data) => {
            this.add_alert_to_display(data);
            this.play_alert_sound(data.priority);
        });
        
        // Listen for alert acknowledgments
        frappe.realtime.on('alert_acknowledged', (data) => {
            this.update_alert_status(data.alert, 'Acknowledged');
        });
        
        // Listen for alert resolutions
        frappe.realtime.on('alert_resolved', (data) => {
            this.update_alert_status(data.alert, 'Resolved');
        });
        
        // Join monitoring room
        frappe.realtime.publish_realtime({
            event: 'join_room',
            room: 'shop_floor_monitoring'
        });
    }
    
    make_dashboard() {
        this.page.main.html(`
            <div class="dashboard-container">
                <!-- Header Metrics -->
                <div class="row mb-3">
                    <div class="col-12">
                        <div class="card bg-primary text-white">
                            <div class="card-body">
                                <div class="row" id="header-metrics">
                                    <div class="col-md-2">
                                        <h6>Active Stations</h6>
                                        <h3 id="active-stations-count">0</h3>
                                    </div>
                                    <div class="col-md-2">
                                        <h6>Average OEE</h6>
                                        <h3 id="average-oee">0%</h3>
                                    </div>
                                    <div class="col-md-2">
                                        <h6>Online Stations</h6>
                                        <h3 id="online-stations">0</h3>
                                    </div>
                                    <div class="col-md-2">
                                        <h6>Active Alerts</h6>
                                        <h3 id="active-alerts-count">0</h3>
                                    </div>
                                    <div class="col-md-2">
                                        <h6>Production Today</h6>
                                        <h3 id="production-today">0</h3>
                                    </div>
                                    <div class="col-md-2">
                                        <h6>Data Points</h6>
                                        <h3 id="data-points-today">0</h3>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Main Dashboard Content -->
                <div class="row">
                    <!-- Stations Grid -->
                    <div class="col-lg-8">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">Manufacturing Stations</h5>
                                <div class="btn-group" role="group">
                                    <button type="button" class="btn btn-sm btn-outline-primary" onclick="dashboard.toggle_view('grid')">Grid</button>
                                    <button type="button" class="btn btn-sm btn-outline-primary" onclick="dashboard.toggle_view('list')">List</button>
                                </div>
                            </div>
                            <div class="card-body" id="stations-container">
                                <div id="stations-grid" class="row">
                                    <!-- Stations will be populated here -->
                                </div>
                                <div id="stations-list" class="d-none">
                                    <table class="table table-striped" id="stations-table">
                                        <thead>
                                            <tr>
                                                <th>Station</th>
                                                <th>Type</th>
                                                <th>Status</th>
                                                <th>OEE</th>
                                                <th>Operators</th>
                                                <th>Alerts</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody></tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Sensor Readings Chart -->
                        <div class="card mt-3">
                            <div class="card-header">
                                <h5 class="mb-0">Real-time Sensor Readings</h5>
                            </div>
                            <div class="card-body">
                                <div id="sensor-chart"></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Sidebar -->
                    <div class="col-lg-4">
                        <!-- Active Alerts -->
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">Active Alerts</h5>
                                <button class="btn btn-sm btn-outline-danger" onclick="dashboard.acknowledge_all_alerts()">
                                    Ack All
                                </button>
                            </div>
                            <div class="card-body p-0" style="max-height: 400px; overflow-y: auto;">
                                <div id="alerts-panel">
                                    <!-- Alerts will be populated here -->
                                </div>
                            </div>
                        </div>
                        
                        <!-- Production Metrics -->
                        <div class="card mt-3">
                            <div class="card-header">
                                <h5 class="mb-0">Production Metrics</h5>
                            </div>
                            <div class="card-body">
                                <div id="production-metrics">
                                    <!-- Production metrics will be populated here -->
                                </div>
                            </div>
                        </div>
                        
                        <!-- System Status -->
                        <div class="card mt-3">
                            <div class="card-header">
                                <h5 class="mb-0">System Status</h5>
                            </div>
                            <div class="card-body">
                                <div id="system-status">
                                    <!-- System status will be populated here -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        // Store reference for global access
        window.dashboard = this;
    }
    
    refresh_data() {
        frappe.call({
            method: 'amb_w_spc.real_time_monitoring.page.shop_floor_dashboard.shop_floor_dashboard.get_dashboard_data',
            callback: (r) => {
                if (r.message && !r.message.error) {
                    this.update_dashboard(r.message);
                } else {
                    this.show_error('Failed to load dashboard data');
                }
            }
        });
    }
    
    update_dashboard(data) {
        this.update_header_metrics(data.production_metrics);
        this.update_stations_display(data.stations);
        this.update_alerts_display(data.alerts);
        this.update_production_metrics_display(data.production_metrics);
        this.update_sensor_chart(data.sensor_readings);
        this.update_system_status_display(data.system_status);
        
        // Update last refresh time
        this.page.set_secondary_action(__('Last Updated: {0}', [moment().format('HH:mm:ss')]));
    }
    
    update_header_metrics(metrics) {
        $('#active-stations-count').text(metrics.active_stations || 0);
        $('#average-oee').text(`${(metrics.average_oee || 0).toFixed(1)}%`);
        $('#online-stations').text(metrics.stations_online || 0);
        $('#active-alerts-count').text(metrics.active_alerts || 0);
        $('#production-today').text(metrics.total_production_today || 0);
        $('#data-points-today').text(metrics.total_data_points_today || 0);
    }
    
    update_stations_display(stations) {
        this.update_stations_grid(stations);
        this.update_stations_table(stations);
    }
    
    update_stations_grid(stations) {
        const container = document.getElementById('stations-grid');
        let html = '';
        
        stations.forEach(station => {
            const statusColor = this.get_status_color(station.status);
            const commColor = this.get_status_color(station.communication_status);
            const oeePercentage = station.current_oee || 0;
            const progressColor = oeePercentage >= 85 ? 'success' : oeePercentage >= 70 ? 'warning' : 'danger';
            
            html += `
                <div class="col-md-6 col-xl-4 mb-3">
                    <div class="card border-${statusColor} station-card" data-station="${station.name}">
                        <div class="card-header bg-${statusColor} text-white d-flex justify-content-between align-items-center">
                            <h6 class="mb-0">${station.station_name}</h6>
                            <small>${station.station_type}</small>
                        </div>
                        <div class="card-body p-2">
                            <div class="row mb-2">
                                <div class="col-6">
                                    <small class="text-muted">Status</small><br>
                                    <span class="badge badge-${statusColor}">${station.status}</span>
                                </div>
                                <div class="col-6">
                                    <small class="text-muted">Connection</small><br>
                                    <span class="badge badge-${commColor}">${station.communication_status}</span>
                                </div>
                            </div>
                            
                            <div class="mb-2">
                                <small class="text-muted">OEE: ${oeePercentage.toFixed(1)}% (Target: ${station.oee_target || 85}%)</small>
                                <div class="progress" style="height: 8px;">
                                    <div class="progress-bar bg-${progressColor}" style="width: ${oeePercentage}%"></div>
                                </div>
                            </div>
                            
                            <div class="row text-center">
                                <div class="col-4">
                                    <small class="text-muted">Operators</small><br>
                                    <strong>${station.active_operators || 0}</strong>
                                </div>
                                <div class="col-4">
                                    <small class="text-muted">Sensors</small><br>
                                    <strong>${station.sensor_count || 0}</strong>
                                </div>
                                <div class="col-4">
                                    <small class="text-muted">Alerts</small><br>
                                    <strong class="${station.active_alerts > 0 ? 'text-danger' : ''}">${station.active_alerts || 0}</strong>
                                </div>
                            </div>
                            
                            ${station.current_work_order ? `
                                <hr class="my-2">
                                <small class="text-muted">Current Job</small><br>
                                <small><strong>${station.current_item}</strong></small>
                                <div class="progress mt-1" style="height: 6px;">
                                    <div class="progress-bar" style="width: ${station.production_progress || 0}%"></div>
                                </div>
                            ` : ''}
                        </div>
                        <div class="card-footer p-1">
                            <div class="btn-group btn-group-sm w-100">
                                <button class="btn btn-outline-primary btn-sm" onclick="dashboard.show_station_details('${station.name}')">
                                    Details
                                </button>
                                <button class="btn btn-outline-secondary btn-sm" onclick="dashboard.show_station_chart('${station.name}')">
                                    Charts
                                </button>
                                <div class="btn-group">
                                    <button class="btn btn-outline-secondary btn-sm dropdown-toggle" data-toggle="dropdown">
                                        Actions
                                    </button>
                                    <div class="dropdown-menu">
                                        <a class="dropdown-item" onclick="dashboard.toggle_station_status('${station.name}', 'Maintenance')">Maintenance</a>
                                        <a class="dropdown-item" onclick="dashboard.toggle_station_status('${station.name}', 'Active')">Activate</a>
                                        <a class="dropdown-item" onclick="dashboard.test_station_connection('${station.name}')">Test Connection</a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
    
    update_stations_table(stations) {
        const tbody = document.querySelector('#stations-table tbody');
        let html = '';
        
        stations.forEach(station => {
            const statusColor = this.get_status_color(station.status);
            const oeePercentage = station.current_oee || 0;
            
            html += `
                <tr data-station="${station.name}">
                    <td>
                        <strong>${station.station_name}</strong><br>
                        <small class="text-muted">${station.station_id}</small>
                    </td>
                    <td>${station.station_type}</td>
                    <td><span class="badge badge-${statusColor}">${station.status}</span></td>
                    <td>
                        ${oeePercentage.toFixed(1)}%
                        <div class="progress mt-1" style="height: 4px;">
                            <div class="progress-bar" style="width: ${oeePercentage}%"></div>
                        </div>
                    </td>
                    <td>${station.active_operators || 0}</td>
                    <td>
                        <span class="${station.active_alerts > 0 ? 'text-danger' : ''}">${station.active_alerts || 0}</span>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="dashboard.show_station_details('${station.name}')">
                            Details
                        </button>
                    </td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    }
    
    update_alerts_display(alerts) {
        const container = document.getElementById('alerts-panel');
        
        if (!alerts || alerts.length === 0) {
            container.innerHTML = `
                <div class="p-3 text-center text-muted">
                    <i class="fa fa-check-circle fa-2x mb-2"></i><br>
                    No active alerts
                </div>
            `;
            return;
        }
        
        let html = '';
        alerts.forEach(alert => {
            const priorityColor = alert.priority === 'High' ? 'danger' : alert.priority === 'Medium' ? 'warning' : 'info';
            const timeAgo = moment(alert.triggered_at).fromNow();
            
            html += `
                <div class="alert alert-${priorityColor} alert-dismissible m-2" data-alert="${alert.name}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${alert.station_name || alert.station}</h6>
                            <p class="mb-1">${alert.message}</p>
                            <small class="text-muted">${timeAgo} • ${alert.sensor_name || alert.sensor}</small>
                        </div>
                        <div class="ml-2">
                            <button class="btn btn-sm btn-outline-secondary" onclick="dashboard.acknowledge_alert('${alert.name}')">
                                Ack
                            </button>
                            <button class="btn btn-sm btn-outline-success ml-1" onclick="dashboard.resolve_alert('${alert.name}')">
                                Resolve
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
    
    update_production_metrics_display(metrics) {
        const container = document.getElementById('production-metrics');
        
        html = `
            <div class="row">
                <div class="col-6 mb-3">
                    <h6 class="text-muted mb-1">Work Orders</h6>
                    <h4>${metrics.active_work_orders || 0}</h4>
                    <small class="text-success">${(metrics.average_completion || 0).toFixed(1)}% avg completion</small>
                </div>
                <div class="col-6 mb-3">
                    <h6 class="text-muted mb-1">Quality Rate</h6>
                    <h4>${(metrics.within_spec_percentage || 0).toFixed(1)}%</h4>
                    <small class="text-muted">${metrics.total_readings_today || 0} readings today</small>
                </div>
                <div class="col-12">
                    <h6 class="text-muted mb-1">Production Progress</h6>
                    <div class="progress mb-2">
                        <div class="progress-bar" style="width: ${(metrics.average_completion || 0)}%">
                            ${(metrics.average_completion || 0).toFixed(1)}%
                        </div>
                    </div>
                    <small class="text-muted">${metrics.total_produced_qty || 0} / ${metrics.total_planned_qty || 0} units</small>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
    }
    
    update_sensor_chart(sensorReadings) {
        // Implementation for real-time sensor chart using Chart.js or similar
        // This would create a line chart showing recent sensor trends
        if (!sensorReadings || sensorReadings.length === 0) return;
        
        // Group readings by sensor
        const sensorGroups = {};
        sensorReadings.forEach(reading => {
            if (!sensorGroups[reading.sensor]) {
                sensorGroups[reading.sensor] = [];
            }
            sensorGroups[reading.sensor].push(reading);
        });
        
        // Create simple table for now (can be enhanced with Chart.js)
        const container = document.getElementById('sensor-chart');
        let html = '<div class="table-responsive"><table class="table table-sm">';
        html += '<thead><tr><th>Sensor</th><th>Value</th><th>Status</th><th>Time</th></tr></thead><tbody>';
        
        sensorReadings.slice(0, 10).forEach(reading => {
            const statusColor = this.get_status_color(reading.status);
            html += `
                <tr>
                    <td><strong>${reading.sensor_name}</strong><br><small>${reading.station_name}</small></td>
                    <td>${reading.value} ${reading.unit_of_measure || ''}</td>
                    <td><span class="badge badge-${statusColor}">${reading.status}</span></td>
                    <td><small>${moment(reading.timestamp).format('HH:mm:ss')}</small></td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        container.innerHTML = html;
    }
    
    update_system_status_display(status) {
        const container = document.getElementById('system-status');
        
        const dataCollectionStatus = status.data_collection_running ? 'success' : 'danger';
        const dbHealthStatus = status.database_health === 'healthy' ? 'success' : 'danger';
        
        const html = `
            <div class="row">
                <div class="col-12 mb-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <span>Data Collection</span>
                        <span class="badge badge-${dataCollectionStatus}">
                            ${status.data_collection_running ? 'Running' : 'Stopped'}
                        </span>
                    </div>
                </div>
                <div class="col-12 mb-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <span>Database</span>
                        <span class="badge badge-${dbHealthStatus}">
                            ${status.database_health}
                        </span>
                    </div>
                </div>
                <div class="col-12 mb-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <span>Alert System</span>
                        <span class="badge badge-success">
                            ${status.alert_system_status.status}
                        </span>
                    </div>
                </div>
                <div class="col-12">
                    <small class="text-muted">
                        ${status.total_data_points_today} data points collected today
                    </small>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
    }
    
    // Real-time update handlers
    update_sensor_display(data) {
        // Update individual sensor reading in real-time
        const sensorElements = document.querySelectorAll(`[data-sensor="${data.sensor}"]`);
        sensorElements.forEach(element => {
            const valueElement = element.querySelector('.sensor-value');
            const statusElement = element.querySelector('.sensor-status');
            
            if (valueElement) {
                valueElement.textContent = `${data.value} ${data.unit || ''}`;
            }
            if (statusElement) {
                statusElement.className = `badge badge-${this.get_status_color(data.status)}`;
                statusElement.textContent = data.status;
            }
        });
    }
    
    update_station_status(data) {
        const stationElements = document.querySelectorAll(`[data-station="${data.station}"]`);
        stationElements.forEach(element => {
            // Update status badge
            const statusBadge = element.querySelector('.badge');
            if (statusBadge) {
                statusBadge.className = `badge badge-${this.get_status_color(data.new_status)}`;
                statusBadge.textContent = data.new_status;
            }
        });
    }
    
    add_alert_to_display(data) {
        const alertsPanel = document.getElementById('alerts-panel');
        const priorityColor = data.priority === 'High' ? 'danger' : data.priority === 'Medium' ? 'warning' : 'info';
        
        const alertHtml = `
            <div class="alert alert-${priorityColor} alert-dismissible m-2" data-alert="${data.alert_id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${data.station}</h6>
                        <p class="mb-1">${data.message}</p>
                        <small class="text-muted">Just now • ${data.sensor}</small>
                    </div>
                    <div class="ml-2">
                        <button class="btn btn-sm btn-outline-secondary" onclick="dashboard.acknowledge_alert('${data.alert_id}')">
                            Ack
                        </button>
                        <button class="btn btn-sm btn-outline-success ml-1" onclick="dashboard.resolve_alert('${data.alert_id}')">
                            Resolve
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        alertsPanel.insertAdjacentHTML('afterbegin', alertHtml);
        
        // Update alert counter
        const alertCounter = document.getElementById('active-alerts-count');
        alertCounter.textContent = parseInt(alertCounter.textContent) + 1;
    }
    
    update_alert_status(alertId, newStatus) {
        const alertElement = document.querySelector(`[data-alert="${alertId}"]`);
        if (alertElement) {
            if (newStatus === 'Resolved') {
                alertElement.remove();
                // Update counter
                const alertCounter = document.getElementById('active-alerts-count');
                alertCounter.textContent = Math.max(0, parseInt(alertCounter.textContent) - 1);
            } else {
                alertElement.classList.add('alert-secondary');
                alertElement.classList.remove('alert-danger', 'alert-warning', 'alert-info');
            }
        }
    }
    
    // Utility methods
    get_status_color(status) {
        const colors = {
            'Active': 'success',
            'Online': 'success',
            'Normal': 'success',
            'Warning': 'warning',
            'Alarm': 'danger',
            'Maintenance': 'info',
            'Failed': 'danger',
            'Inactive': 'secondary',
            'Offline': 'secondary',
            'Error': 'danger'
        };
        return colors[status] || 'secondary';
    }
    
    play_alert_sound(priority) {
        if (priority === 'High') {
            // Play high priority alert sound
            this.play_sound('high-alert');
        } else if (priority === 'Medium') {
            // Play medium priority alert sound
            this.play_sound('medium-alert');
        }
    }
    
    play_sound(type) {
        // Implementation for playing alert sounds
        // Could use Web Audio API or HTML5 audio elements
        try {
            const audio = new Audio(`/assets/amb_w_spc/sounds/${type}.mp3`);
            audio.play().catch(e => console.log('Audio play failed:', e));
        } catch (e) {
            console.log('Audio not supported or file not found');
        }
    }
    
    // Action methods
    toggle_view(viewType) {
        const gridView = document.getElementById('stations-grid');
        const listView = document.getElementById('stations-list');
        
        if (viewType === 'grid') {
            gridView.classList.remove('d-none');
            listView.classList.add('d-none');
        } else {
            gridView.classList.add('d-none');
            listView.classList.remove('d-none');
        }
    }
    
    show_station_details(stationName) {
        frappe.call({
            method: 'amb_w_spc.real_time_monitoring.page.shop_floor_dashboard.shop_floor_dashboard.get_station_details',
            args: { station_name: stationName },
            callback: (r) => {
                if (r.message && !r.message.error) {
                    this.show_station_details_dialog(r.message);
                }
            }
        });
    }
    
    show_station_details_dialog(data) {
        const dialog = new frappe.ui.Dialog({
            title: `Station Details: ${data.station.station_name}`,
            size: 'large',
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'station_details'
                }
            ]
        });
        
        // Populate dialog with station details
        let html = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Station Information</h6>
                    <table class="table table-sm">
                        <tr><td>Station ID</td><td>${data.station.station_id}</td></tr>
                        <tr><td>Type</td><td>${data.station.station_type}</td></tr>
                        <tr><td>Status</td><td><span class="badge badge-${this.get_status_color(data.station.status)}">${data.station.status}</span></td></tr>
                        <tr><td>OEE</td><td>${(data.station.current_oee || 0).toFixed(1)}%</td></tr>
                        <tr><td>Communication</td><td><span class="badge badge-${this.get_status_color(data.station.communication_status)}">${data.station.communication_status}</span></td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Recent Sensor Data</h6>
                    <div style="max-height: 200px; overflow-y: auto;">
                        <table class="table table-sm">
                            <thead><tr><th>Sensor</th><th>Value</th><th>Status</th></tr></thead>
                            <tbody>
        `;
        
        data.sensor_data.forEach(sensor => {
            html += `
                <tr>
                    <td>${sensor.sensor_name}</td>
                    <td>${sensor.value || 'N/A'}</td>
                    <td><span class="badge badge-${this.get_status_color(sensor.status)}">${sensor.status || 'Unknown'}</span></td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div></div></div>';
        
        dialog.fields_dict.station_details.$wrapper.html(html);
        dialog.show();
    }
    
    acknowledge_alert(alertId) {
        frappe.call({
            method: 'amb_w_spc.real_time_monitoring.page.shop_floor_dashboard.shop_floor_dashboard.acknowledge_alert',
            args: { alert_name: alertId },
            callback: (r) => {
                if (r.message.status === 'success') {
                    frappe.show_alert('Alert acknowledged', 'green');
                }
            }
        });
    }
    
    resolve_alert(alertId) {
        const dialog = new frappe.ui.Dialog({
            title: 'Resolve Alert',
            fields: [
                {
                    fieldtype: 'Text',
                    fieldname: 'resolution_notes',
                    label: 'Resolution Notes',
                    reqd: 1
                }
            ],
            primary_action_label: 'Resolve',
            primary_action: (values) => {
                frappe.call({
                    method: 'amb_w_spc.real_time_monitoring.page.shop_floor_dashboard.shop_floor_dashboard.resolve_alert',
                    args: {
                        alert_name: alertId,
                        resolution_notes: values.resolution_notes
                    },
                    callback: (r) => {
                        if (r.message.status === 'success') {
                            frappe.show_alert('Alert resolved', 'green');
                            dialog.hide();
                        }
                    }
                });
            }
        });
        
        dialog.show();
    }
    
    acknowledge_all_alerts() {
        frappe.confirm('Acknowledge all active alerts?', () => {
            // Implementation for bulk alert acknowledgment
            frappe.call({
                method: 'amb_w_spc.real_time_monitoring.api.acknowledge_all_alerts',
                callback: (r) => {
                    if (r.message.status === 'success') {
                        frappe.show_alert('All alerts acknowledged', 'green');
                        this.refresh_data();
                    }
                }
            });
        });
    }
    
    toggle_station_status(stationName, newStatus) {
        frappe.call({
            method: 'amb_w_spc.real_time_monitoring.page.shop_floor_dashboard.shop_floor_dashboard.toggle_station_status',
            args: {
                station_name: stationName,
                new_status: newStatus
            },
            callback: (r) => {
                if (r.message.status === 'success') {
                    frappe.show_alert(r.message.message, 'green');
                } else {
                    frappe.show_alert(r.message.message, 'red');
                }
            }
        });
    }
    
    test_station_connection(stationName) {
        frappe.call({
            method: 'amb_w_spc.shop_floor_control.doctype.manufacturing_station.manufacturing_station.test_station_connection',
            args: { station_name: stationName },
            callback: (r) => {
                if (r.message.status === 'success') {
                    frappe.show_alert('Connection successful', 'green');
                } else {
                    frappe.show_alert('Connection failed: ' + r.message.message, 'red');
                }
            }
        });
    }
    
    show_settings_dialog() {
        const dialog = new frappe.ui.Dialog({
            title: 'Dashboard Settings',
            fields: [
                {
                    fieldtype: 'Int',
                    fieldname: 'refresh_interval',
                    label: 'Refresh Interval (seconds)',
                    default: this.refresh_interval / 1000
                },
                {
                    fieldtype: 'Check',
                    fieldname: 'enable_sounds',
                    label: 'Enable Alert Sounds',
                    default: 1
                },
                {
                    fieldtype: 'Select',
                    fieldname: 'default_view',
                    label: 'Default Station View',
                    options: 'Grid\nList',
                    default: 'Grid'
                }
            ],
            primary_action_label: 'Save',
            primary_action: (values) => {
                this.refresh_interval = values.refresh_interval * 1000;
                this.start_auto_refresh();
                dialog.hide();
                frappe.show_alert('Settings saved', 'green');
            }
        });
        
        dialog.show();
    }
    
    toggle_fullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }
    
    show_error(message) {
        const container = this.page.main;
        container.html(`
            <div class="alert alert-danger">
                <h4>Error Loading Dashboard</h4>
                <p>${message}</p>
                <button class="btn btn-primary" onclick="dashboard.refresh_data()">Retry</button>
            </div>
        `);
    }
    
    start_auto_refresh() {
        // Clear existing interval
        if (this.refresh_timer) {
            clearInterval(this.refresh_timer);
        }
        
        // Start new interval
        this.refresh_timer = setInterval(() => {
            this.refresh_data();
        }, this.refresh_interval);
    }
    
    destroy() {
        // Clean up when page is destroyed
        if (this.refresh_timer) {
            clearInterval(this.refresh_timer);
        }
        
        // Leave real-time rooms
        frappe.realtime.publish_realtime({
            event: 'leave_room',
            room: 'shop_floor_monitoring'
        });
    }
}

// Make dashboard globally available
window.ShopFloorDashboard = ShopFloorDashboard;
