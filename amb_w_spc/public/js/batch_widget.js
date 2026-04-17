
// =============================================================================
// ENHANCED BATCH NAVBAR WIDGET - v2.0
// Features: Responsive, Draggable, Close Duration Options
// =============================================================================

frappe.provide('frappe.ui');
frappe.provide('amb.batch_widget');

// Initialize when page loads AND on Frappe SPA route changes
$(document).ready(function() {
    initializeBatchWidget();
});

// Re-initialize on Frappe SPA page changes (route transitions)
if (typeof frappe !== 'undefined' && frappe.router) {
    frappe.router.on('change', function() {
        setTimeout(function() {
            if (frappe.session && frappe.session.user !== 'Guest' && !isWidgetHidden()) {
                if ($('.batch-announcement-widget').length === 0) {
                    console.log('\ud83d\udd04 SPA route change detected, re-initializing widget...');
                    update_batch_announcements();
                    addGlobalRefreshButton();
					                    createStarterPill();
                }
            }
        }, 2000);
    });
}

// Enhanced Configuration
amb.batch_widget.config = {
    refreshInterval: 300000, // 5 minutes (300,000 ms)
    autoMinimizeDelay: 120000, // 2 minutes
    maxRetries: 3,
    retryDelay: 10000, // 10 seconds
    cacheDuration: 120000, // 2 minutes cache
    storageKey: 'amb_batch_widget_hidden_until',
    positionKey: 'amb_batch_widget_position',
    plantColors: {
        '1': '#3498db', '2': '#e74c3c', '3': '#2ecc71', '4': '#f39c12', '5': '#9b59b6'
    },
    companyColors: {
        'AMB-Wellness': '#1abc9c', 'Juice': '#3498db', 'Dry Plant Company': '#e74c3c'
    }
};

// State management
amb.batch_widget.state = {
    isFetching: false,
    retryCount: 0,
    lastFetchTime: null,
    cache: null,
    cacheTimestamp: null,
    refreshTimer: null,
    isOnline: true,
    isDragging: false
};

// =============================================================================
// RESPONSIVE WIDTH CALCULATION
// =============================================================================

function getResponsiveWidth() {
    const screenWidth = window.innerWidth;
    if (screenWidth < 576) return screenWidth - 20; // Mobile: full width with margin
    if (screenWidth < 768) return Math.min(400, screenWidth - 40); // Small tablets
    if (screenWidth < 992) return 450; // Tablets
    return 500; // Desktop
}

function getResponsiveMaxHeight() {
    const screenHeight = window.innerHeight;
    if (screenHeight < 600) return '50vh';
    if (screenHeight < 800) return '60vh';
    return '70vh';
}

// =============================================================================
// HIDE DURATION MANAGEMENT
// =============================================================================

function isWidgetHidden() {
    const hiddenUntil = localStorage.getItem(amb.batch_widget.config.storageKey);
    if (!hiddenUntil) return false;
    
    const hiddenTime = parseInt(hiddenUntil, 10);
    if (Date.now() < hiddenTime) {
        return true;
    }
    // Expired, clear storage
    localStorage.removeItem(amb.batch_widget.config.storageKey);
    return false;
}

function hideWidgetFor(hours) {
    const hideUntil = Date.now() + (hours * 60 * 60 * 1000);
    localStorage.setItem(amb.batch_widget.config.storageKey, hideUntil.toString());
    console.log(`🔕 Widget hidden for ${hours} hour(s)`);
}

function showHideDurationDialog(widget) {
    const dialog = new frappe.ui.Dialog({
        title: '🔕 Hide Production Monitor',
        fields: [
            {
                fieldtype: 'Select',
                fieldname: 'duration',
                label: 'Hide for',
                options: [
                    { label: '1 Hour', value: '1' },
                    { label: '2 Hours', value: '2' },
                    { label: '4 Hours', value: '4' },
                    { label: '8 Hours', value: '8' },
                    { label: '24 Hours (1 Day)', value: '24' }
                ],
                default: '1'
            },
            {
                fieldtype: 'HTML',
                options: '<p style="color: #666; font-size: 12px; margin-top: 10px;">The widget will automatically reappear after the selected time.</p>'
            }
        ],
        primary_action_label: 'Hide',
        primary_action: function(values) {
            const hours = parseInt(values.duration, 10);
            hideWidgetFor(hours);
            widget.fadeOut(300, function() {
                $(this).remove();
            });
            dialog.hide();
            frappe.show_alert({
                message: `Production Monitor hidden for ${hours} hour(s)`,
                indicator: 'blue'
            });
        },
        secondary_action_label: 'Cancel',
        secondary_action: function() {
            dialog.hide();
        }
    });
    dialog.show();
}

// =============================================================================
// DRAG FUNCTIONALITY
// =============================================================================

function getSavedPosition() {
    const saved = localStorage.getItem(amb.batch_widget.config.positionKey);
    if (saved) {
        try {
            return JSON.parse(saved);
        } catch (e) {
            return null;
        }
    }
    return null;
}

function savePosition(bottom, left) {
    localStorage.setItem(amb.batch_widget.config.positionKey, JSON.stringify({ bottom, left }));
}

function makeDraggable(widget) {
    const header = widget.find('.widget-drag-handle');
    let startX, startY, startBottom, startLeft;
    
    header.css('cursor', 'move');
    
    header.on('mousedown touchstart', function(e) {
        if ($(e.target).is('button')) return; // Don't drag when clicking buttons
        
        e.preventDefault();
        amb.batch_widget.state.isDragging = true;
        
        const touch = e.type === 'touchstart' ? e.originalEvent.touches[0] : e;
        startX = touch.clientX;
        startY = touch.clientY;
        
        const rect = widget[0].getBoundingClientRect();
        startBottom = window.innerHeight - rect.bottom;
        startLeft = rect.left;
        
        widget.css('transition', 'none');
        
        $(document).on('mousemove.widgetdrag touchmove.widgetdrag', function(e) {
            const touch = e.type === 'touchmove' ? e.originalEvent.touches[0] : e;
            const deltaX = touch.clientX - startX;
            const deltaY = touch.clientY - startY;
            
            let newBottom = startBottom - deltaY;
            let newLeft = startLeft + deltaX;
            
            // Bounds checking
            const widgetWidth = widget.outerWidth();
            const widgetHeight = widget.outerHeight();
            
            newBottom = Math.max(10, Math.min(window.innerHeight - widgetHeight - 10, newBottom));
            newLeft = Math.max(10, Math.min(window.innerWidth - widgetWidth - 10, newLeft));
            
            widget.css({
                'bottom': newBottom + 'px',
                'left': newLeft + 'px',
                'top': 'auto',
                'right': 'auto'
            });
        });
        
        $(document).on('mouseup.widgetdrag touchend.widgetdrag', function() {
            amb.batch_widget.state.isDragging = false;
            $(document).off('.widgetdrag');
            widget.css('transition', '');
            
            // Save position
            const rect = widget[0].getBoundingClientRect();
            savePosition(window.innerHeight - rect.bottom, rect.left);
        });
    });
}

// =============================================================================
// INITIALIZATION
// =============================================================================

function initializeBatchWidget() {
    if (frappe.session && frappe.session.user !== 'Guest') {
        // Check if widget should be hidden
        if (isWidgetHidden()) {
            console.log('🔕 Widget is hidden (user preference)');
            return;
        }
        
        console.log('🚀 Initializing Enhanced Batch Navbar Widget v2.0...');
		        // Show starter pill immediately
        createStarterPill();
        
        setTimeout(function() {
            setupSmartRefresh();
            setTimeout(update_batch_announcements, 2000);
            addGlobalRefreshButton();
            setupConnectivityMonitoring();
            setupResizeHandler();
        }, 3000);
    }
}

function setupResizeHandler() {
    let resizeTimeout;
    $(window).on('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function() {
            const widget = $('.batch-announcement-widget');
            if (widget.length) {
                widget.css({
                    'width': getResponsiveWidth() + 'px',
                    'max-height': getResponsiveMaxHeight()
                });
            }
        }, 250);
    });
}

// =============================================================================
// ENHANCED API CALL MANAGEMENT
// =============================================================================

function setupSmartRefresh() {
    if (amb.batch_widget.state.refreshTimer) {
        clearInterval(amb.batch_widget.state.refreshTimer);
    }
    
    amb.batch_widget.state.refreshTimer = setInterval(function() {
        if (!document.hidden && amb.batch_widget.state.isOnline && !isWidgetHidden()) {
            update_batch_announcements();
        }
    }, amb.batch_widget.config.refreshInterval);
    
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden && !amb.batch_widget.state.isFetching && !isWidgetHidden()) {
            const cacheAge = Date.now() - (amb.batch_widget.state.cacheTimestamp || 0);
            if (!amb.batch_widget.state.cache || cacheAge > amb.batch_widget.config.cacheDuration) {
                update_batch_announcements();
            } else {
                display_cached_data();
            }
        }
    });
}

function update_batch_announcements() {
    if (isWidgetHidden()) {
        console.log('🔕 Widget hidden, skipping update');
        return;
    }
    
    if (amb.batch_widget.state.isFetching) {
        console.log('⏳ API call already in progress, skipping...');
        return;
    }
    
    const cacheAge = Date.now() - (amb.batch_widget.state.cacheTimestamp || 0);
    if (amb.batch_widget.state.cache && cacheAge < 30000) {
        console.log('♻️ Using cached data (fresh)');
        display_cached_data();
        return;
    }
    
    console.log('🔄 Fetching Batch AMB data...');
    amb.batch_widget.state.isFetching = true;
    amb.batch_widget.state.lastFetchTime = Date.now();
    
    frappe.call({
        method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.get_running_batch_announcements',
        args: {
            include_companies: true,
            include_plants: true,
            include_quality: true
        },
        callback: function(r) {
            amb.batch_widget.state.isFetching = false;
            amb.batch_widget.state.retryCount = 0;
            
            if (r.message && r.message.success) {
                console.log('✅ API call successful');
                amb.batch_widget.state.cache = r.message;
                process_api_response(r.message);
            } else {
                console.warn('⚠️ API returned unsuccessful response:', r.message);
                handle_api_error(r.message || {error: 'Unknown API error'});
            }
        },
        error: function(r) {
            amb.batch_widget.state.isFetching = false;
            console.error('❌ API call failed:', r);
            handle_api_error(r);
        },
        freeze: false
    });
}

function process_api_response(response) {
    if (!response) {
        show_error_message('No data received from server');
        return;
    }
    
    try {
        if (response.grouped_announcements && Object.keys(response.grouped_announcements).length > 0) {
            display_grouped_batch_announcements(response.grouped_announcements, response.stats);
        } else if (response.announcements && response.announcements.length > 0) {
            display_batch_announcements(response.announcements, response.stats);
        } else {
            show_no_batches_message(response.message);
        }
        update_last_refresh_time();

		            // Update starter pill status if it exists
            updateStarterPillStatus(response);
    } catch (error) {
        console.error('Error processing API response:', error);
        show_error_message('Error displaying batch data');
    }
}

function handle_api_error(error) {
    const errorMsg = error.error || error.message || 'Connection failed';
    console.error('API Error:', errorMsg);
    
    amb.batch_widget.state.retryCount++;
    
    if (amb.batch_widget.state.retryCount <= amb.batch_widget.config.maxRetries) {
        console.log(`🔄 Retrying in ${amb.batch_widget.config.retryDelay/1000} seconds... (Attempt ${amb.batch_widget.state.retryCount}/${amb.batch_widget.config.maxRetries})`);
        const backoffDelay = amb.batch_widget.config.retryDelay * Math.pow(1.5, amb.batch_widget.state.retryCount - 1);
        
        setTimeout(function() {
            if (amb.batch_widget.state.isOnline) {
                update_batch_announcements();
            }
        }, backoffDelay);
        
        show_retry_message(errorMsg, amb.batch_widget.state.retryCount);
    } else {
        console.error('❌ Max retries reached, giving up');
        show_error_message(`Failed to load batches: ${errorMsg}`);
        amb.batch_widget.state.retryCount = 0;
    }
}

function display_cached_data() {
    if (amb.batch_widget.state.cache) {
        console.log('📦 Displaying cached data');
        process_api_response(amb.batch_widget.state.cache);
    }
}

// =============================================================================
// ENHANCED DISPLAY FUNCTIONS
// =============================================================================

function display_grouped_batch_announcements(groupedData, stats = {}) {
    if (!groupedData || Object.keys(groupedData).length === 0) {
        show_no_batches_message();
        return;
    }
    
    let announcement_html = '';
    let totalBatches = stats.total || 0;
    
    try {
        for (const [companyName, companyData] of Object.entries(groupedData)) {
            const companyColor = amb.batch_widget.config.companyColors[companyName] || '#7f8c8d';
            let companyBatches = 0;
            
            announcement_html += `
                <div class="company-group" style="margin-bottom: 15px;">
                    <div class="company-header" style="
                        display: flex; 
                        align-items: center; 
                        padding: 8px 12px;
                        background: ${companyColor};
                        color: white;
                        border-radius: 5px;
                        margin-bottom: 10px;
                        font-weight: bold;
                        font-size: 14px;
                    ">
                        <span style="margin-right: 8px;">🏢</span>
                        ${companyName}
                    </div>
            `;
            
            for (const [plantCode, plantBatches] of Object.entries(companyData)) {
                const plantColor = amb.batch_widget.config.plantColors[plantCode] || '#95a5a6';
                const plantName = getPlantName(plantCode);
                
                announcement_html += `
                    <div class="plant-group" style="margin-left: 10px; margin-bottom: 12px;">
                        <div class="plant-header" style="
                            display: flex; 
                            align-items: center; 
                            padding: 6px 10px;
                            background: ${plantColor}22;
                            border-left: 4px solid ${plantColor};
                            border-radius: 3px;
                            margin-bottom: 8px;
                            font-size: 12px;
                        ">
                            <span style="margin-right: 6px;">${getPlantIcon(plantCode)}</span>
                            ${plantName} (Plant ${plantCode})
                        </div>
                        <div class="batch-list">
                `;
                
                if (Array.isArray(plantBatches)) {
                    plantBatches.forEach(function(batch) {
                        companyBatches++;
                        const priorityColor = getPriorityColor(batch.priority);
                        const statusIcon = getStatusIcon(batch.quality_status);
                        announcement_html += create_batch_item_html(batch, priorityColor, statusIcon);
                    });
                }
                
                announcement_html += `</div></div>`;
            }
            
            announcement_html = announcement_html.replace(`${companyName}`, `${companyName} <span style="font-size: 0.8em; opacity: 0.9;">(${companyBatches})</span>`);
            announcement_html += `</div>`;
        }
        
        if (announcement_html) {
            show_navbar_widget(announcement_html, totalBatches, stats);
        }
    } catch (error) {
        console.error('Error displaying grouped batches:', error);
        show_error_message('Error displaying batch data');
    }
}

function create_batch_item_html(batch, priorityColor, statusIcon) {
    return `
        <div class="batch-announcement-item" style="
            margin-bottom: 10px; 
            padding: 10px; 
            background: #f8f9fa; 
            border-radius: 5px;
            border-left: 4px solid ${priorityColor};
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            position: relative;
            cursor: pointer;
            transition: background 0.2s;
        " onclick="openBatchRecord('${batch.name}')" onmouseover="this.style.background='#e9ecef'" onmouseout="this.style.background='#f8f9fa'">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: bold; margin-bottom: 5px; font-size: 12px; color: #2c3e50; word-wrap: break-word;">
                        ${statusIcon} ${batch.title || 'Batch'} - ${batch.batch_code || ''}
                    </div>
                    <div style="font-size: 11px; color: #34495e; margin-bottom: 5px;">
                        Item: ${batch.item_code || 'N/A'} | Level: ${batch.level || 'N/A'}
                    </div>
                    <div style="
                        margin: 0; 
                        font-size: 11px; 
                        line-height: 1.3;
                        color: #7f8c8d;
                        word-wrap: break-word;
                    ">${batch.content || batch.message || 'No details available'}</div>
                </div>
            </div>
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 8px;
                font-size: 10px;
            ">
                <span style="background: ${priorityColor}22; color: ${priorityColor}; padding: 2px 6px; border-radius: 3px;">
                    ${batch.quality_status || 'Pending'}
                </span>
                <span style="color: #999;">
                    ${formatTime(batch.modified || batch.creation)}
                </span>
            </div>
        </div>
    `;
}

// =============================================================================
// ENHANCED WIDGET MANAGEMENT
// =============================================================================

function show_navbar_widget(html_content, count, stats = {}) {
    $('.batch-announcement-widget').remove();
    
    const widgetWidth = getResponsiveWidth();
    const maxHeight = getResponsiveMaxHeight();
    const savedPosition = getSavedPosition();
    
    const statsHtml = stats.total ? `
        <div class="widget-stats" style="display: flex; justify-content: space-around; margin: 10px 0; padding: 8px; background: #f8f9fa; border-radius: 5px; flex-wrap: wrap;">
            <div style="text-align: center; min-width: 60px;">
                <div style="font-weight: bold; color: #e74c3c;">${stats.high_priority || 0}</div>
                <div style="font-size: 9px;">High</div>
            </div>
            <div style="text-align: center; min-width: 60px;">
                <div style="font-weight: bold; color: #f39c12;">${stats.quality_check || 0}</div>
                <div style="font-size: 9px;">QC</div>
            </div>
            <div style="text-align: center; min-width: 60px;">
                <div style="font-weight: bold; color: #3498db;">${stats.container_level || 0}</div>
                <div style="font-size: 9px;">Container</div>
            </div>
        </div>
    ` : '';
    
    // Default position: bottom-left, above the user avatar (approximately 60px from bottom)
    let positionStyles = savedPosition 
        ? `bottom: ${savedPosition.bottom}px; left: ${savedPosition.left}px;`
        : 'bottom: 60px; left: 10px;';
    
    let widget = $(`
        <div class="batch-announcement-widget" style="
            position: fixed;
            ${positionStyles}
            width: ${widgetWidth}px;
            max-height: ${maxHeight};
            overflow-y: auto;
            z-index: 1050;
            background: white;
            border: 2px solid #28a745;
            border-radius: 8px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.25);
            animation: slideInUp 0.3s ease-out;
        ">
            <div class="widget-drag-handle" style="
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                padding: 12px 15px;
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                color: white;
                border-radius: 6px 6px 0 0;
                position: sticky;
                top: 0;
                z-index: 10;
            ">
                <div style="flex: 1;">
                    <h4 style="margin: 0; font-size: 15px; display: flex; align-items: center;">
                        <span style="margin-right: 8px;">🏭</span>
                        Production Monitor
                    </h4>
                    <small style="opacity: 0.9; font-size: 11px;">
                        ${count} active batch${count !== 1 ? 'es' : ''} • Drag to move
                    </small>
                </div>
                <div style="display: flex; gap: 5px; flex-shrink: 0;">
                    <button class="btn btn-xs refresh-announcements" style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 8px; border-radius: 4px;" title="Refresh">
                        🔄
                    </button>
                    <button class="btn btn-xs toggle-stats" style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 8px; border-radius: 4px;" title="Toggle Stats">
                        📊
                    </button>
                    <button class="btn btn-xs minimize-announcement" style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 8px; border-radius: 4px;" title="Minimize">
                        ➖
                    </button>
                    <button class="btn btn-xs close-announcement" style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 8px; border-radius: 4px;" title="Close">
                        ✕
                    </button>
                </div>
            </div>
            <div class="widget-body" style="padding: 15px;">
                ${statsHtml}
                <div class="announcement-content">
                    ${html_content}
                </div>
            </div>
            <div style="
                text-align: center; 
                padding: 10px 15px;
                border-top: 1px solid #eee;
                font-size: 10px; 
                color: #666;
                background: #fafafa;
                border-radius: 0 0 6px 6px;
            ">
                🔄 Auto-update 5 min • 
                <span id="last-update-time">${new Date().toLocaleTimeString()}</span>
            </div>
        </div>
    `);
    
    // Add CSS animation
    if (!$('#batch-widget-styles').length) {
        $('head').append(`
            <style id="batch-widget-styles">
                @keyframes slideInUp {
                    from { transform: translateY(100%); opacity: 0; }
                    to { transform: translateY(0); opacity: 1; }
                }
                .batch-announcement-widget::-webkit-scrollbar {
                    width: 6px;
                }
                .batch-announcement-widget::-webkit-scrollbar-thumb {
                    background: #ccc;
                    border-radius: 3px;
                }
                .batch-announcement-widget::-webkit-scrollbar-thumb:hover {
                    background: #999;
                }
            </style>
        `);
    }
    
    $('body').append(widget);
    makeDraggable(widget);
    setup_widget_events(widget);
    
    // Auto-minimize after delay
    setTimeout(function() {
        if (widget.is(':visible') && !widget.is(':hover') && !amb.batch_widget.state.isDragging) {
            minimizeWidget(widget);
        }
    }, amb.batch_widget.config.autoMinimizeDelay);
}

// =============================================================================
// CONNECTIVITY & ERROR HANDLING
// =============================================================================

function setupConnectivityMonitoring() {
    window.addEventListener('online', function() {
        amb.batch_widget.state.isOnline = true;
        console.log('🌐 Connection restored');
        if (!isWidgetHidden()) {
            update_batch_announcements();
        }
    });
    
    window.addEventListener('offline', function() {
        amb.batch_widget.state.isOnline = false;
        console.warn('🔴 Connection lost');
        show_offline_message();
    });
}

function show_retry_message(errorMsg, retryCount) {
    const widget = $('.batch-announcement-widget');
    if (widget.length) {
        widget.find('.retry-notice').remove();
        const retryHtml = `
            <div class="retry-notice" style="
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 5px;
                padding: 8px;
                margin-bottom: 10px;
                font-size: 11px;
                color: #856404;
            ">
                ⚠️ ${errorMsg}<br>
                Retrying... (${retryCount}/${amb.batch_widget.config.maxRetries})
            </div>
        `;
        widget.find('.announcement-content').prepend(retryHtml);
    }
}

function show_error_message(message) {
    const errorHtml = `
        <div style="
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            padding: 10px;
            font-size: 12px;
            color: #721c24;
        ">
            ❌ ${message}
        </div>
    `;
    
    const widget = $('.batch-announcement-widget');
    if (widget.length) {
        widget.find('.announcement-content').html(errorHtml);
    } else {
        show_navbar_widget(errorHtml, 0);
    }
}

function show_offline_message() {
    const offlineHtml = `
        <div style="
            background: #f8f9fa;
            border: 1px solid #6c757d;
            border-radius: 5px;
            padding: 15px;
            text-align: center;
            color: #6c757d;
        ">
            🔴 Offline<br>
            <small>Batch data will refresh when connection is restored</small>
        </div>
    `;
    
    const widget = $('.batch-announcement-widget');
    if (widget.length) {
        widget.find('.announcement-content').html(offlineHtml);
    }
}

function show_no_batches_message(message = 'No active batches found') {
    const noBatchesHtml = `
        <div style="
            background: #e9ecef;
            border-radius: 5px;
            padding: 20px;
            text-align: center;
            color: #6c757d;
        ">
            📭 ${message}
        </div>
    `;
    
    show_navbar_widget(noBatchesHtml, 0);
}

function update_last_refresh_time() {
    $('#last-update-time').text(new Date().toLocaleTimeString());
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function getPriorityColor(priority) {
    const colors = { 'high': '#e74c3c', 'medium': '#f39c12', 'low': '#3498db' };
    return colors[priority] || '#95a5a6';
}

function getPlantName(plantCode) {
    const plantNames = {
        '1': 'Main Production', '2': 'Secondary Plant', '3': 'Processing Unit',
        '4': 'Quality Lab', '5': 'Packaging Unit'
    };
    return plantNames[plantCode] || 'Plant ' + plantCode;
}

function getPlantIcon(plantCode) {
    const icons = { '1': '🏭', '2': '🏢', '3': '⚙️', '4': '🔬', '5': '📦' };
    return icons[plantCode] || '🏭';
}

function getStatusIcon(quality_status) {
    const icons = {
        'Pending': '📝', 'In Progress': '⏳', 'Running': '▶️', 'Completed': '✅',
        'On Hold': '⏸️', 'Cancelled': '❌', 'Quality Check': '🔬', 'Passed': '✅', 'Failed': '❌'
    };
    return icons[quality_status] || '📋';
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}

function openBatchRecord(batchName) {
    if (batchName) {
        frappe.set_route('Form', 'Batch AMB', batchName);
    }
}

function setup_widget_events(widget) {
    widget.find('.refresh-announcements').on('click', function(e) {
        e.stopPropagation();
        update_batch_announcements();
    });
    
    widget.find('.close-announcement').on('click', function(e) {
        e.stopPropagation();
        showHideDurationDialog(widget);
    });
    
    widget.find('.minimize-announcement').on('click', function(e) {
        e.stopPropagation();
        minimizeWidget(widget);
    });
    
    widget.find('.toggle-stats').on('click', function(e) {
        e.stopPropagation();
        widget.find('.widget-stats').toggle();
    });
}

function minimizeWidget(widget) {
    widget.find('.widget-body').slideUp(200);
    widget.find('.minimize-announcement').hide();
    
    if (!widget.find('.maximize-btn').length) {
        widget.find('.toggle-stats').after(
            '<button class="btn btn-xs maximize-btn" style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 8px; border-radius: 4px;" title="Maximize">➕</button>'
        );
        
        widget.find('.maximize-btn').on('click', function(e) {
            e.stopPropagation();
            widget.find('.widget-body').slideDown(200);
            widget.find('.minimize-announcement').show();
            $(this).remove();
        });
    }
}

function addGlobalRefreshButton() {
    if ($('.navbar-batch-refresh').length === 0) {
        $('.navbar-right').prepend(`
            <li class="navbar-batch-refresh">
                <a href="#" onclick="window.refresh_batch_announcements(); return false;" title="Refresh Batches">
                    🔄
                </a>
            </li>
        `);
    }
}

function display_batch_announcements(announcements, stats) {
    let html = '';
    announcements.forEach(function(batch) {
        const priorityColor = getPriorityColor(batch.priority);
        const statusIcon = getStatusIcon(batch.quality_status);
        html += create_batch_item_html(batch, priorityColor, statusIcon);
    });
    if (html) {
        show_navbar_widget(html, announcements.length, stats);
    }
}

// =============================================================================
// GLOBAL EXPORTS
// =============================================================================

window.refresh_batch_announcements = function() {
    console.log('🔄 Manual refresh triggered');
    localStorage.removeItem(amb.batch_widget.config.storageKey); // Clear hide preference
    update_batch_announcements();
};

window.hide_batch_widget = function(hours = 1) {
    hideWidgetFor(hours);
    $('.batch-announcement-widget').fadeOut(300, function() {
        $(this).remove();
    });
};

window.show_batch_widget = function() {
    localStorage.removeItem(amb.batch_widget.config.storageKey);
    if ($('.batch-announcement-widget').length === 0) {
        update_batch_announcements();
    } else {
        $('.batch-announcement-widget').fadeIn();
    }
};

window.reset_batch_widget_position = function() {
    localStorage.removeItem(amb.batch_widget.config.positionKey);
    const widget = $('.batch-announcement-widget');
    if (widget.length) {
        widget.css({ 'bottom': '60px', 'left': '10px', 'top': 'auto', 'right': 'auto' });
    }
};

$(window).on('beforeunload', function() {
    if (amb.batch_widget.state.refreshTimer) {
        clearInterval(amb.batch_widget.state.refreshTimer);
    }
});

console.log('✅ Enhanced Batch Widget v2.0 loaded (Responsive + Draggable + Hide Duration)');

// =============================================================================
// SMALL STARTER PILL WIDGET - Always visible, click to open Production Monitor
// =============================================================================
function createStarterPill() {
    // Remove existing pill if any
    $('.batch-starter-pill').remove();

    var pill = $(`
        <div class="batch-starter-pill" style="
            position: fixed;
            bottom: 60px;
            left: 10px;
            z-index: 1050;
            background: linear-gradient(135deg, #1abc9c, #16a085);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            transition: all 0.3s ease;
            animation: pillSlideIn 0.5s ease-out;
            user-select: none;
        ">
            <span style="font-size: 16px;">&#127981;</span>
            <span class="widget-title" style="font-weight: 600;">Batch AMB</span>
            <span class="widget-status" id="batch-amb-status" style="
                background: rgba(255,255,255,0.2);
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 11px;
            ">Click to run</span>
        </div>
    `);

    // Add hover effect
    pill.on('mouseenter', function() {
        $(this).css({
            'transform': 'translateY(-2px)',
            'box-shadow': '0 4px 15px rgba(0,0,0,0.3)'
        });
    }).on('mouseleave', function() {
        $(this).css({
            'transform': 'translateY(0)',
            'box-shadow': '0 2px 10px rgba(0,0,0,0.2)'
        });
    });

    // Click to load Production Monitor
    pill.on('click', function() {
        var statusEl = $(this).find('#batch-amb-status');
        statusEl.text('Loading...');
        $(this).css('background', 'linear-gradient(135deg, #f39c12, #e67e22)');

        // Clear any hide preference and load the full widget
        localStorage.removeItem(amb.batch_widget.config.storageKey);
        update_batch_announcements();
        setupSmartRefresh();
        addGlobalRefreshButton();
        setupConnectivityMonitoring();
        setupResizeHandler();

        // Update pill status after loading
        setTimeout(function() {
            if ($('.batch-announcement-widget').length > 0) {
                statusEl.text('Running');
                pill.css('background', 'linear-gradient(135deg, #27ae60, #2ecc71)');
            } else {
                statusEl.text('No data');
                pill.css('background', 'linear-gradient(135deg, #95a5a6, #7f8c8d)');
            }
        }, 5000);
    });

    // Add animation CSS
    if (!$('#batch-pill-styles').length) {
        $('head').append(`
            <style id="batch-pill-styles">
                @keyframes pillSlideIn {
                    from { transform: translateX(-100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                .batch-starter-pill:active {
                    transform: scale(0.95) !important;
                }
            </style>
        `);
    }

    $('body').append(pill);
    console.log('[BatchWidget] Starter pill created');

	    // Auto-fetch status on pill creation (don't wait for click)
    setTimeout(function() {
        var autoStatusEl = $('#batch-amb-status');
        if (autoStatusEl.length && autoStatusEl.text() === 'Click to run') {
            autoStatusEl.text('Loading...');
            frappe.call({
                method: 'amb_w_spc.sfc_manufacturing.doctype.batch_amb.batch_amb.get_running_batch_announcements',
                args: { include_companies: true, include_plants: true, include_quality: true },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        var count = r.message.stats ? r.message.stats.total : 0;
                        if (count > 0) {
                            autoStatusEl.text(count + ' active').css('color', '#27ae60');
                            pill.css('background', 'linear-gradient(135deg, #27ae60, #2ecc71)');
                        } else {
                            autoStatusEl.text('No batches').css('color', '#95a5a6');
                            pill.css('background', 'linear-gradient(135deg, #95a5a6, #7f8c8d)');
                        }
                    } else {
                        autoStatusEl.text('Click to run').css('color', '#2c3e50');
                    }
                },
                error: function() {
                    autoStatusEl.text('Offline').css('color', '#e74c3c');
                },
                freeze: false
            });
        }
    }, 2000);
}

// =============================================================================
// STARTER PILL STATUS UPDATER - Called by process_api_response()
// =============================================================================
function updateStarterPillStatus(response) {
    var pillStatus = $('#batch-amb-status');
    var pill = $('.batch-starter-pill');
    if (!pillStatus.length || !pill.length) return;

    var total = 0;
    if (response && response.stats && response.stats.total) {
        total = response.stats.total;
    } else if (response && response.announcements) {
        total = response.announcements.length;
    }

    if (total > 0) {
        pillStatus.text(total + ' active').css('color', '#27ae60');
        pill.css('background', 'linear-gradient(135deg, #27ae60, #2ecc71)');
    } else {
        pillStatus.text('No batches').css('color', '#95a5a6');
        pill.css('background', 'linear-gradient(135deg, #95a5a6, #7f8c8d)');
    }
    console.log('[BatchWidget] Pill status updated: ' + (total > 0 ? total + ' active' : 'No batches'));
}

// Export starter pill function
window.create_batch_starter_pill = createStarterPill;
