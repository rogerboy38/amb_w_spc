# Contributing to AMB W SPC

Thank you for your interest in contributing to AMB W SPC! This document provides guidelines and information for contributors.

## 🎯 Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful and professional in all interactions.

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js 16+
- Frappe Framework 15.0+
- Git knowledge
- Basic understanding of ERPNext/Frappe development

### Development Setup

1. **Fork the Repository**
   ```bash
   # Fork the repo on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/amb_w_spc.git
   cd amb_w_spc
   ```

2. **Setup Development Environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   
   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   
   # Install pre-commit hooks
   pre-commit install
   ```

3. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 📝 Development Guidelines

### Code Style

#### Python
- Follow [PEP 8](https://pep8.org/) style guide
- Use [Black](https://black.readthedocs.io/) for code formatting
- Maximum line length: 88 characters
- Use type hints where appropriate

```python
# Good
def calculate_process_capability(data: List[float], target: float) -> Dict[str, float]:
    """Calculate Cp and Cpk values for process capability analysis."""
    return {"cp": cp_value, "cpk": cpk_value}

# Bad
def calc_pc(data,target):
    return {"cp":cp_value,"cpk":cpk_value}
```

#### JavaScript
- Follow [Frappe JavaScript style guide](https://frappeframework.com/docs/v14/user/en/guides/development/javascript-style-guide)
- Use ES6+ features
- Use meaningful variable names

```javascript
// Good
frappe.ui.form.on("SPC Data Point", {
    refresh: function(frm) {
        if (frm.doc.value > frm.doc.upper_limit) {
            frm.set_indicator(__("Out of Control"), "red");
        }
    }
});

// Bad
frappe.ui.form.on("SPC Data Point",{
refresh:function(frm){
if(frm.doc.value>frm.doc.upper_limit)frm.set_indicator(__("Out of Control"),"red");
}});
```

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (no functional changes)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(spc): add real-time control chart updates
fix(scheduler): resolve memory leak in sensor data collection
docs(api): add examples for SPC data endpoints
test(quality): add unit tests for CAPA workflow
```

### Testing

#### Writing Tests

1. **Unit Tests**: Test individual functions and methods
2. **Integration Tests**: Test module interactions
3. **End-to-End Tests**: Test complete workflows

```python
# Example unit test
def test_calculate_control_limits():
    """Test SPC control limit calculations."""
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    limits = calculate_control_limits(data)
    
    assert limits["ucl"] > limits["lcl"]
    assert limits["center_line"] == 3.0
```

#### Running Tests

```bash
# Run all tests
bench --site test_site run-tests --app amb_w_spc

# Run specific module tests
bench --site test_site run-tests --app amb_w_spc --module amb_w_spc.core_spc

# Run with coverage
bench --site test_site run-tests --app amb_w_spc --coverage
```

### Documentation

- Update relevant documentation for any changes
- Add docstrings to all Python functions and classes
- Include examples in API documentation
- Update README.md if needed

```python
def process_sensor_data(sensor_id: str, value: float, timestamp: datetime) -> bool:
    """
    Process incoming sensor data and trigger alerts if necessary.
    
    Args:
        sensor_id: Unique identifier for the sensor
        value: Measured value from the sensor
        timestamp: When the measurement was taken
        
    Returns:
        bool: True if processing successful, False otherwise
        
    Raises:
        ValueError: If sensor_id is not found
        
    Example:
        >>> process_sensor_data("TEMP_001", 72.5, datetime.now())
        True
    """
```

## 🐛 Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Environment Information**
   - Frappe version
   - ERPNext version
   - Python version
   - Browser (if applicable)

2. **Steps to Reproduce**
   - Clear, numbered steps
   - Expected behavior
   - Actual behavior

3. **Additional Information**
   - Error messages
   - Screenshots (if applicable)
   - Console logs

### Feature Requests

For feature requests, please include:

1. **Problem Statement**: What problem does this solve?
2. **Proposed Solution**: How should it work?
3. **Alternatives**: Other solutions considered
4. **Use Cases**: Who would benefit?

## 🔄 Pull Request Process

### Before Submitting

1. **Test Your Changes**
   - Run all tests
   - Test manually in different scenarios
   - Check for performance impacts

2. **Code Quality**
   - Run linters and formatters
   - Ensure no new warnings
   - Update documentation

3. **Review Checklist**
   - [ ] Tests pass
   - [ ] Code follows style guidelines
   - [ ] Documentation updated
   - [ ] No breaking changes (or properly documented)
   - [ ] Commit messages follow convention

### Submitting Pull Request

1. **Create Pull Request**
   - Use descriptive title
   - Reference related issues
   - Provide clear description

2. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] Unit tests added/updated
   - [ ] Manual testing completed
   - [ ] Performance impact assessed
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] Tests pass
   ```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs tests
2. **Code Review**: Maintainers review changes
3. **Feedback**: Address any comments or suggestions
4. **Approval**: Once approved, changes will be merged

## 🏗️ Development Areas

We welcome contributions in these areas:

### Priority Areas

1. **Performance Optimization**
   - Database query optimization
   - Caching improvements
   - Background job efficiency

2. **Testing Coverage**
   - Unit test coverage
   - Integration tests
   - End-to-end tests

3. **Documentation**
   - API documentation
   - User guides
   - Development tutorials

4. **Internationalization**
   - Translation support
   - Locale-specific features

### Feature Areas

1. **Analytics & Reporting**
   - Advanced SPC analytics
   - Custom report builders
   - Data visualization

2. **Integration**
   - Third-party system connectors
   - IoT device drivers
   - API extensions

3. **User Experience**
   - Dashboard improvements
   - Mobile responsiveness
   - Accessibility features

## 📚 Resources

### Documentation
- [Frappe Framework Docs](https://frappeframework.com/docs)
- [ERPNext Developer Guide](https://frappeframework.com/docs/v14/user/en/guides/development)
- [Project Wiki](https://github.com/your-username/amb_w_spc/wiki)

### Community
- [GitHub Discussions](https://github.com/your-username/amb_w_spc/discussions)
- [Frappe Community Forum](https://discuss.frappe.io/)

### Tools
- [Pre-commit Hooks](https://pre-commit.com/)
- [Black Code Formatter](https://black.readthedocs.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)

## 🎉 Recognition

Contributors are recognized in:
- [CONTRIBUTORS.md](CONTRIBUTORS.md) file
- Release notes
- Project documentation

## 📞 Getting Help

If you need help:

1. Check existing [documentation](https://github.com/your-username/amb_w_spc/wiki)
2. Search [existing issues](https://github.com/your-username/amb_w_spc/issues)
3. Ask in [discussions](https://github.com/your-username/amb_w_spc/discussions)
4. Contact maintainers: support@ambsystems.com

Thank you for contributing to AMB W SPC! 🚀