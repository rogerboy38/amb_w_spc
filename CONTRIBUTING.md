# Contributing to AMB W SPC ERPNext System

## Table of Contents

1. [Introduction](#introduction)
2. [Development Environment Setup](#development-environment-setup)
3. [Coding Standards](#coding-standards)
4. [Pull Request Guidelines](#pull-request-guidelines)
5. [Testing Requirements](#testing-requirements)
6. [Documentation Standards](#documentation-standards)
7. [Issue Reporting Procedures](#issue-reporting-procedures)
8. [Code Review Process](#code-review-process)
9. [Release Procedures](#release-procedures)
10. [Community Guidelines](#community-guidelines)

## Introduction

Welcome to the AMB W SPC ERPNext System project! This is a comprehensive, FDA-compliant Statistical Process Control (SPC) system designed for seamless integration with ERPNext. The system features 25+ custom DocTypes, advanced workflow automation, role-based security, and comprehensive audit capabilities for manufacturing environments.

This contributing guide will help you understand how to effectively contribute to this enterprise-level quality management solution that supports FDA 21 CFR Part 11 requirements and multi-plant scalability.

## Development Environment Setup

### Prerequisites

Before you begin development, ensure your system meets the following requirements:

#### Software Requirements
- **ERPNext**: Version 14.0.0 or higher
- **Frappe Framework**: Version 14.0.0 or higher
- **Python**: Version 3.8 or higher
- **Database**: MariaDB 10.3+ or PostgreSQL 12+
- **Operating System**: Ubuntu 20.04+ or CentOS 8+
- **Node.js**: Version 16.0.0 or higher
- **Git**: Version 2.25.0 or higher

#### Hardware Requirements
- **RAM**: Minimum 4GB, Recommended 8GB+
- **Storage**: Minimum 10GB free space
- **CPU**: Multi-core processor recommended
- **Network**: Stable internet connection for updates

### Local Development Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/rogerboy38/amb_w_spc.git
   cd amb_w_spc
   ```

2. **Set up ERPNext Development Environment**
   ```bash
   # Install Frappe Bench
   pip3 install frappe-bench
   
   # Initialize bench
   bench init frappe-bench --frappe-branch version-14
   cd frappe-bench
   
   # Create site
   bench new-site your-site.localhost
   bench use your-site.localhost
   
   # Install ERPNext
   bench get-app erpnext --branch version-14
   bench install-app erpnext
   ```

3. **Install AMB W SPC System**
   ```bash
   # Get the app
   bench get-app amb_w_spc path/to/amb_w_spc
   
   # Install the app
   bench install-app amb_w_spc
   ```

4. **Development Mode Setup**
   ```bash
   # Enable developer mode
   bench set-config developer_mode 1
   bench restart
   
   # Start development server
   bench start
   ```

### Database Configuration

Configure your database connection properly in `site_config.json`:

```json
{
 "db_host": "localhost",
 "db_port": 3306,
 "db_name": "your_site_db",
 "db_password": "your_password",
 "encryption_key": "your_encryption_key",
 "developer_mode": 1
}
```

### IDE Configuration

We recommend using Visual Studio Code with the following extensions:
- Python
- Frappe/ERPNext Snippets
- GitLens
- Python Docstring Generator
- JSON Tools

**VS Code Settings for Project:**
```json
{
    "python.defaultInterpreterPath": "./env/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "files.associations": {
        "*.json": "json",
        "*.py": "python",
        "*.js": "javascript"
    }
}
```

## Coding Standards

### Python Code Standards

#### Style Guide
- Follow **PEP 8** Python Style Guide
- Use **Black** formatter with 88-character line length
- Use **flake8** for linting with the following configuration:

```ini
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = .git,__pycache__,migrations
```

#### Naming Conventions
- **Functions**: `snake_case`
- **Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **DocTypes**: Use ERPNext naming convention with spaces (e.g., "SPC Data Point")

#### Code Structure
```python
# Standard library imports
import os
import json
from datetime import datetime

# Third-party imports
import frappe
from frappe import _
from frappe.model.document import Document

# Local application imports
from amb_w_spc.utils.spc_calculations import calculate_control_limits


class SPCDataPoint(Document):
    """
    Document class for SPC Data Point DocType.
    
    This class handles statistical process control data points
    and implements FDA 21 CFR Part 11 compliance requirements.
    """
    
    def validate(self):
        """Validate the document before saving."""
        self.validate_measurement_value()
        self.validate_operator_permissions()
        self.check_specification_limits()
    
    def validate_measurement_value(self):
        """Validate measurement value against parameter specifications."""
        if not self.measurement_value:
            frappe.throw(_("Measurement value is required"))
        
        # Additional validation logic here
```

#### Documentation Requirements
- All public functions must have docstrings following Google style
- Include type hints for function parameters and return values
- Document complex algorithms and FDA compliance requirements

```python
def calculate_process_capability(data_points: list, 
                               usl: float, 
                               lsl: float) -> dict:
    """
    Calculate process capability indices (Cp, Cpk, Pp, Ppk).
    
    Args:
        data_points: List of measurement values
        usl: Upper specification limit
        lsl: Lower specification limit
        
    Returns:
        Dictionary containing capability indices and status
        
    Raises:
        ValueError: If insufficient data points provided
        
    Note:
        Requires minimum 30 data points for reliable calculation
        per FDA guidance.
    """
```

### JavaScript Code Standards

#### Style Guide
- Use **ESLint** with Airbnb configuration
- Use **Prettier** for code formatting
- Prefer `const` and `let` over `var`
- Use arrow functions where appropriate

#### Frappe Framework Patterns
```javascript
// DocType client script example
frappe.ui.form.on('SPC Data Point', {
    refresh: function(frm) {
        // Form refresh logic
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Generate Alert'), function() {
                check_specification_limits(frm);
            }, __('Actions'));
        }
    },
    
    measurement_value: function(frm) {
        // Real-time validation
        validate_measurement_range(frm);
    }
});

function validate_measurement_range(frm) {
    if (frm.doc.measurement_value && frm.doc.parameter) {
        frappe.call({
            method: 'amb_w_spc.api.validate_measurement',
            args: {
                parameter: frm.doc.parameter,
                value: frm.doc.measurement_value
            },
            callback: function(r) {
                if (r.message && r.message.alert_required) {
                    frappe.msgprint(__('Measurement exceeds specification limits'));
                }
            }
        });
    }
}
```

### JSON Configuration Standards

#### DocType Definitions
- Use consistent field naming
- Include proper field descriptions
- Set appropriate permissions and validations

```json
{
    "autoname": "naming_series:",
    "creation": "2024-01-01 00:00:00",
    "doctype": "DocType",
    "engine": "InnoDB",
    "field_order": [
        "naming_series",
        "parameter",
        "workstation",
        "measurement_value"
    ],
    "fields": [
        {
            "fieldname": "naming_series",
            "fieldtype": "Select",
            "label": "Series",
            "options": "SPC-DP-.YYYY.-",
            "reqd": 1
        }
    ]
}
```

## Pull Request Guidelines

### Before Submitting a Pull Request

1. **Fork and Branch**
   ```bash
   # Fork the repository on GitHub
   # Clone your fork
   git clone https://github.com/your-username/amb_w_spc.git
   
   # Create a feature branch
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Follow coding standards
   - Add tests for new functionality
   - Update documentation
   - Ensure FDA compliance requirements are met

3. **Test Your Changes**
   ```bash
   # Run unit tests
   bench run-tests --app amb_w_spc
   
   # Run integration tests
   bench run-tests --app amb_w_spc --module test_integration
   
   # Run FDA compliance tests
   bench run-tests --app amb_w_spc --module test_fda_compliance
   ```

### Pull Request Template

Use this template for all pull requests:

```markdown
## Description
Brief description of the changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] FDA compliance update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] FDA compliance tests pass
- [ ] Manual testing completed

## FDA Compliance Impact
- [ ] No impact on FDA compliance
- [ ] Updates maintain FDA compliance
- [ ] New FDA compliance features added
- [ ] Requires validation protocol update

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```

### Pull Request Review Criteria

- **Code Quality**: Follows project coding standards
- **Functionality**: Feature works as intended
- **Testing**: Adequate test coverage (minimum 80%)
- **Documentation**: Updated documentation for changes
- **FDA Compliance**: Maintains or enhances compliance
- **Performance**: No negative performance impact
- **Security**: No security vulnerabilities introduced

## Testing Requirements

### Test Categories

#### 1. Unit Tests
Location: `amb_w_spc/tests/`

```python
# Example unit test
import unittest
import frappe
from amb_w_spc.utils.spc_calculations import calculate_control_limits

class TestSPCCalculations(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_data = [1.0, 2.0, 3.0, 4.0, 5.0]
    
    def test_control_limits_calculation(self):
        """Test control limits calculation."""
        result = calculate_control_limits(self.test_data)
        
        self.assertIn('ucl', result)
        self.assertIn('lcl', result)
        self.assertIn('center_line', result)
        self.assertIsInstance(result['ucl'], float)
    
    def test_insufficient_data_handling(self):
        """Test handling of insufficient data."""
        with self.assertRaises(ValueError):
            calculate_control_limits([1.0, 2.0])  # Less than minimum required
```

#### 2. Integration Tests
Focus on testing interactions between DocTypes and workflows:

```python
def test_spc_alert_workflow_integration(self):
    """Test SPC alert creation and workflow progression."""
    # Create test data point exceeding limits
    data_point = frappe.get_doc({
        'doctype': 'SPC Data Point',
        'parameter': 'Test Parameter',
        'measurement_value': 100.0,  # Exceeds specification
        'workstation': 'Test Workstation'
    })
    data_point.insert()
    
    # Verify alert creation
    alerts = frappe.get_all('SPC Alert', 
                           filters={'data_point': data_point.name})
    self.assertEqual(len(alerts), 1)
```

#### 3. FDA Compliance Tests
Ensure all regulatory requirements are met:

```python
def test_electronic_signature_compliance(self):
    """Test electronic signature FDA compliance."""
    signature = create_test_signature()
    
    # Verify required signature components
    self.assertIsNotNone(signature.signed_by)
    self.assertIsNotNone(signature.signature_meaning)
    self.assertIsNotNone(signature.timestamp)
    self.assertIsNotNone(signature.ip_address)
```

### Test Coverage Requirements

- **Minimum Coverage**: 80% for all new code
- **Critical Path Coverage**: 95% for FDA compliance features
- **Documentation**: All tests must include docstrings

### Running Tests

```bash
# Run all tests
bench run-tests --app amb_w_spc

# Run specific test module
bench run-tests --app amb_w_spc --module test_spc_calculations

# Run with coverage
bench run-tests --app amb_w_spc --coverage

# Run FDA compliance tests only
bench run-tests --app amb_w_spc --module test_fda_compliance
```

## Documentation Standards

### Documentation Types

#### 1. Code Documentation
- **Docstrings**: Required for all public functions and classes
- **Inline Comments**: For complex logic and FDA compliance requirements
- **Type Hints**: For all function parameters and return values

#### 2. User Documentation
Location: `docs/user_guide/`

```markdown
# Document Template

## Overview
Brief description of the feature/process

## Prerequisites
- List of requirements
- Permissions needed
- System setup requirements

## Step-by-Step Instructions
1. Detailed step descriptions
2. Include screenshots where helpful
3. Note any FDA compliance considerations

## Troubleshooting
Common issues and solutions

## See Also
- Related documentation links
- Reference materials
```

#### 3. API Documentation
Location: `docs/api/`

Use OpenAPI specification for REST APIs:

```yaml
# Example API documentation
paths:
  /api/method/amb_w_spc.api.create_spc_data_point:
    post:
      summary: Create SPC Data Point
      description: Creates a new SPC data point with validation
      parameters:
        - name: parameter
          in: body
          required: true
          schema:
            type: string
      responses:
        200:
          description: Successfully created data point
        400:
          description: Validation error
```

#### 4. Installation Documentation
- Step-by-step installation guides
- Troubleshooting common installation issues
- Environment-specific instructions

### Documentation Review Process

1. **Technical Accuracy**: Verified by subject matter experts
2. **Clarity**: Reviewed for clear, concise language
3. **Completeness**: Covers all necessary information
4. **FDA Compliance**: Includes relevant regulatory considerations

## Issue Reporting Procedures

### Issue Categories

#### 1. Bug Reports
Use this template for bug reports:

```markdown
**Bug Description**
A clear and concise description of what the bug is.

**Steps to Reproduce**
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
A clear description of what you expected to happen.

**Actual Behavior**
A clear description of what actually happened.

**Environment**
- ERPNext Version: [e.g. 14.0.0]
- AMB W SPC Version: [e.g. 1.0.0]
- Browser: [e.g. Chrome 91.0]
- Operating System: [e.g. Ubuntu 20.04]

**FDA Compliance Impact**
- [ ] No impact on FDA compliance
- [ ] Potential compliance issue
- [ ] Critical compliance violation

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Additional Context**
Add any other context about the problem here.
```

#### 2. Feature Requests
```markdown
**Feature Description**
A clear and concise description of the proposed feature.

**Business Justification**
Explain why this feature would be valuable.

**FDA Compliance Considerations**
Any regulatory requirements or implications.

**Proposed Implementation**
If you have ideas about how to implement this feature.

**Alternative Solutions**
Other approaches you've considered.
```

#### 3. Security Issues
**IMPORTANT**: Do not report security issues publicly. Send them to: security@ambwspc.com

### Issue Triage Process

Issues are triaged based on:
- **Critical**: Security vulnerabilities, FDA compliance violations, data loss
- **High**: Major functionality broken, significant performance issues
- **Medium**: Minor functionality issues, enhancement requests
- **Low**: Documentation issues, cosmetic improvements

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Improvements or additions to documentation
- `fda-compliance`: Related to FDA regulatory requirements
- `security`: Security-related issues
- `performance`: Performance-related issues
- `good-first-issue`: Good for newcomers

## Code Review Process

### Review Requirements

All pull requests require:
- **Minimum 2 reviewers** for core functionality changes
- **FDA compliance reviewer** for changes affecting regulated features
- **Security reviewer** for changes affecting authentication or data access
- **Technical lead approval** for architectural changes

### Review Checklist

#### Code Quality
- [ ] Code follows project style guidelines
- [ ] No code smells or anti-patterns
- [ ] Appropriate error handling
- [ ] No security vulnerabilities
- [ ] Performance considerations addressed

#### Functionality
- [ ] Feature works as specified
- [ ] Edge cases handled appropriately
- [ ] Integration points working correctly
- [ ] No breaking changes (or properly documented)

#### FDA Compliance
- [ ] Maintains audit trail requirements
- [ ] Electronic signature compliance maintained
- [ ] Data integrity controls preserved
- [ ] Validation requirements met

#### Testing
- [ ] Adequate test coverage (minimum 80%)
- [ ] All tests passing
- [ ] Integration tests included
- [ ] Manual testing completed

#### Documentation
- [ ] Code documentation updated
- [ ] User documentation updated if needed
- [ ] API documentation updated if applicable
- [ ] FDA compliance documentation updated

### Review Process Timeline

- **Initial Review**: Within 2 business days
- **Follow-up Reviews**: Within 1 business day
- **Final Approval**: Within 24 hours of all requirements met

### Reviewer Guidelines

#### Providing Feedback
- Be constructive and specific
- Reference coding standards where applicable
- Suggest alternatives for improvements
- Consider FDA compliance implications
- Focus on learning opportunities

#### Example Review Comments
```markdown
# Good
Consider using a list comprehension here for better readability:
`result = [item.value for item in data if item.valid]`

# Avoid
This code is bad.
```

## Release Procedures

### Release Types

#### Major Releases (x.0.0)
- Breaking changes
- New major features
- Significant architecture changes
- FDA compliance updates requiring validation

#### Minor Releases (x.y.0)
- New features (backwards compatible)
- Performance improvements
- New DocTypes or workflows

#### Patch Releases (x.y.z)
- Bug fixes
- Security patches
- Documentation updates
- Minor enhancements

### Release Process

#### 1. Pre-Release Testing
```bash
# Run comprehensive test suite
bench run-tests --app amb_w_spc --coverage

# Run FDA compliance validation
bench run-tests --app amb_w_spc --module test_fda_compliance

# Performance testing
bench run-tests --app amb_w_spc --module test_performance

# Security scanning
bandit -r amb_w_spc/

# Documentation validation
make docs-test
```

#### 2. Version Numbering
Follow Semantic Versioning (SemVer):
- Update version in `setup.py`
- Update version in `__init__.py`
- Update CHANGELOG.md

#### 3. Release Notes
Create comprehensive release notes:

```markdown
# Release Notes - v1.2.0

## New Features
- Enhanced SPC control chart visualization
- Automated process capability studies
- Advanced deviation management workflow

## Improvements
- Performance optimization for large datasets
- Improved user interface for mobile devices
- Enhanced FDA compliance reporting

## Bug Fixes
- Fixed calculation error in Cpk values
- Resolved workflow transition issues
- Corrected audit trail timestamps

## FDA Compliance Updates
- Enhanced electronic signature validation
- Improved audit trail completeness
- Updated validation protocols

## Breaking Changes
None

## Upgrade Instructions
1. Backup your site
2. Run: `bench update`
3. Run: `bench migrate`
4. Verify all functionality

## Known Issues
- None
```

#### 4. Deployment Checklist
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Release notes prepared
- [ ] Migration scripts tested
- [ ] Backup procedures verified
- [ ] Rollback plan prepared
- [ ] FDA compliance validation completed

### Hotfix Process

For critical security or FDA compliance issues:

1. **Immediate Assessment**: Evaluate severity and impact
2. **Create Hotfix Branch**: From latest stable release
3. **Develop Fix**: Minimal changes to address issue
4. **Testing**: Focused testing on affected functionality
5. **Emergency Release**: Expedited review and release process
6. **Communication**: Notify all stakeholders immediately

## Community Guidelines

### Code of Conduct

We are committed to providing a welcoming and inspiring community for all. Our Code of Conduct governs how we interact:

#### Our Standards

**Positive Behaviors:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable Behaviors:**
- Use of sexualized language or imagery
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without explicit permission
- Other conduct which could reasonably be considered inappropriate in a professional setting

#### Enforcement

Community leaders are responsible for clarifying and enforcing standards of acceptable behavior and will take appropriate and fair corrective action in response to any instances of unacceptable behavior.

### Communication Channels

#### Primary Channels
- **GitHub Issues**: Bug reports, feature requests, project discussions
- **GitHub Discussions**: General questions, ideas, community discussions
- **Discord**: Real-time chat for development discussions (invite-only)
- **Email**: security@ambwspc.com for security issues

#### Communication Guidelines
- **Be Patient**: Remember that people have different time zones and commitments
- **Be Clear**: Provide context and details in your communications
- **Be Professional**: Maintain professional standards in all interactions
- **Be Inclusive**: Welcome newcomers and help them get started

### Getting Help

#### For Developers
1. **Documentation**: Check the docs folder for detailed guides
2. **GitHub Issues**: Search existing issues before creating new ones
3. **Community Discussions**: Ask questions in GitHub Discussions
4. **Code Examples**: Review existing code for patterns and best practices

#### For Users
1. **User Guide**: Comprehensive documentation in docs/user_guide/
2. **Video Tutorials**: Available on project website
3. **Community Forum**: Connect with other users
4. **Support**: Commercial support available for enterprise users

### Recognition and Attribution

We believe in recognizing contributors:

#### Types of Contributions
- **Code**: New features, bug fixes, performance improvements
- **Documentation**: Writing, reviewing, and improving documentation
- **Testing**: Finding bugs, writing tests, quality assurance
- **Design**: UI/UX improvements, graphics, user experience
- **Community**: Helping other users, organizing events, advocacy

#### Recognition Methods
- **Contributors File**: All contributors listed in CONTRIBUTORS.md
- **Release Notes**: Major contributors acknowledged in each release
- **Hall of Fame**: Outstanding contributors featured on project website
- **Mentorship Program**: Experienced contributors can mentor newcomers

### Diversity and Inclusion

We actively promote diversity and inclusion:

- Welcome contributors from all backgrounds and experience levels
- Provide mentorship for newcomers to open source
- Offer documentation in multiple languages where possible
- Ensure accessibility in all user interfaces
- Create opportunities for underrepresented groups

### Project Governance

#### Decision Making Process
- **Minor Changes**: Can be made by any maintainer
- **Major Changes**: Require consensus among core team
- **Breaking Changes**: Require community discussion and RFC process
- **FDA Compliance**: Requires approval from compliance team

#### Core Team Structure
- **Project Lead**: Overall project direction and strategy
- **Technical Lead**: Technical architecture and code quality
- **FDA Compliance Lead**: Regulatory requirements and validation
- **Community Manager**: Community engagement and support
- **Security Lead**: Security reviews and vulnerability management

---

## Conclusion

Thank you for contributing to the AMB W SPC ERPNext System! Your contributions help make this FDA-compliant quality management system better for manufacturing organizations worldwide.

For questions about this contributing guide, please open an issue or contact the maintainers.

**Remember**: When working with FDA-regulated software, attention to detail and compliance with established procedures is not just good practice—it's essential for patient safety and regulatory compliance.

---

*Last Updated: September 17, 2025*
*Version: 1.0.0*
