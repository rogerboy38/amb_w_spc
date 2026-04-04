# -*- coding: utf-8 -*-
# Copyright (c) 2026, AMB Solutions and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document


class SensorSkill(Document):
    """Sensor Skill configuration for IoT device runtime.

    This defines how to communicate with and read from a specific type of sensor.
    The RPi client loads this config and uses it to drive the physical device.
    """

    def validate(self):
        """Validate skill configuration."""
        self.validate_python_config()
        self.validate_ranges()

    def validate_python_config(self):
        """Ensure python_config is valid JSON if provided."""
        if self.python_config:
            try:
                json.loads(self.python_config)
            except json.JSONDecodeError:
                frappe.throw(
                    "Python Configuration must be valid JSON",
                    frappe.ValidationError
                )

    def validate_ranges(self):
        """Validate min/max value range."""
        if self.min_value and self.max_value:
            if self.min_value >= self.max_value:
                frappe.throw(
                    "Min Value must be less than Max Value",
                    frappe.ValidationError
                )


@frappe.whitelist()
def get_skill_config(skill_id):
    """Get skill configuration for RPi runtime.

    Args:
        skill_id (str): The skill identifier

    Returns:
        dict: Skill configuration with serial settings
    """
    skill = frappe.get_doc("Sensor Skill", skill_id)
    return {
        "skill_id": skill.skill_id,
        "skill_name": skill.skill_name,
        "sensor_type": skill.sensor_type,
        "version": skill.version,
        "min_value": skill.min_value,
        "max_value": skill.max_value,
        "unit_of_measure": skill.unit_of_measure,
        "port": skill.port,
        "baud_rate": skill.baud_rate,
        "python_config": skill.python_config
    }


@frappe.whitelist()
def list_enabled_skills():
    """List all enabled sensor skills.

    Returns:
        list: Enabled skill configs
    """
    skills = frappe.get_all(
        "Sensor Skill",
        filters={"enabled": 1},
        fields=["skill_id", "skill_name", "sensor_type", "version"]
    )
    return skills
