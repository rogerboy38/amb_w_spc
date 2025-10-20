# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, flt

class WorkOrderRouting(Document):
    def validate(self):
        """Validate the work order routing"""
        self.validate_operation_sequence()
        self.validate_time_estimates()
        self.calculate_total_time()
    
    def validate_operation_sequence(self):
        """Ensure operation sequence is unique and sequential"""
        sequences = []
        for operation in self.operations:
            if operation.sequence in sequences:
                frappe.throw(f"Duplicate sequence number {operation.sequence} found")
            sequences.append(operation.sequence)
        
        # Check for gaps in sequence
        sequences.sort()
        for i, seq in enumerate(sequences):
            if i > 0 and seq != sequences[i-1] + 1:
                frappe.msgprint(f"Gap in sequence detected between {sequences[i-1]} and {seq}")
    
    def validate_time_estimates(self):
        """Validate operation time estimates"""
        for operation in self.operations:
            if flt(operation.setup_time) < 0:
                frappe.throw(f"Setup time cannot be negative for operation {operation.operation}")
            if flt(operation.operation_time) <= 0:
                frappe.throw(f"Operation time must be positive for operation {operation.operation}")
    
    def calculate_total_time(self):
        """Calculate total estimated time for all operations"""
        total_setup = sum([flt(op.setup_time) for op in self.operations])
        total_operation = sum([flt(op.operation_time) for op in self.operations])
        self.total_setup_time = total_setup
        self.total_operation_time = total_operation
        self.total_estimated_time = total_setup + total_operation
    
    def get_next_operation(self, current_sequence):
        """Get the next operation in sequence"""
        next_seq = current_sequence + 1
        for operation in self.operations:
            if operation.sequence == next_seq:
                return operation
        return None
    
    def get_operation_by_sequence(self, sequence):
        """Get operation by sequence number"""
        for operation in self.operations:
            if operation.sequence == sequence:
                return operation
        return None
    
    def start_operation(self, sequence, workstation, operator):
        """Start an operation in the routing"""
        operation = self.get_operation_by_sequence(sequence)
        if not operation:
            frappe.throw(f"Operation with sequence {sequence} not found")
        
        # Create SFC transaction
        sfc_doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': operation.operation,
            'operation_sequence': sequence,
            'workstation': workstation,
            'operator': operator,
            'transaction_type': 'Start',
            'timestamp': now_datetime(),
            'status': 'In Progress'
        })
        sfc_doc.insert()
        
        return sfc_doc.name
    
    def complete_operation(self, sequence, actual_time=None, quality_data=None):
        """Complete an operation in the routing"""
        operation = self.get_operation_by_sequence(sequence)
        if not operation:
            frappe.throw(f"Operation with sequence {sequence} not found")
        
        # Find the start transaction
        start_transaction = frappe.get_value('SFC Transaction', {
            'work_order': self.work_order,
            'operation_sequence': sequence,
            'transaction_type': 'Start',
            'status': 'In Progress'
        }, 'name')
        
        if not start_transaction:
            frappe.throw(f"No active start transaction found for operation {sequence}")
        
        # Create completion transaction
        complete_doc = frappe.get_doc({
            'doctype': 'SFC Transaction',
            'work_order': self.work_order,
            'operation': operation.operation,
            'operation_sequence': sequence,
            'transaction_type': 'Complete',
            'timestamp': now_datetime(),
            'status': 'Completed',
            'actual_time': actual_time,
            'quality_data': quality_data
        })
        complete_doc.insert()
        
        # Update start transaction status
        frappe.db.set_value('SFC Transaction', start_transaction, 'status', 'Completed')
        
        return complete_doc.name