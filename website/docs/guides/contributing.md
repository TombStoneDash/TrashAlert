---
sidebar_position: 4
title: Contributing Guide
slug: /guides/contributing
---

# Contributing to TrashAlert

We welcome contributions from the community! This guide explains how to contribute to TrashAlert.

## Code of Conduct

TrashAlert is committed to providing a welcoming and inclusive environment. Please be respectful and constructive in all interactions.

## Getting Started

### 1. Fork the Repository

Visit [TrashAlert on GitHub](https://github.com/TombStoneDash/TrashAlert) and click "Fork".

### 2. Clone Your Fork

```bash
git clone https://github.com/YOUR_USERNAME/TrashAlert.git
cd TrashAlert
```

### 3. Add Upstream Remote

```bash
git remote add upstream https://github.com/TombStoneDash/TrashAlert.git
```

### 4. Create a Branch

```bash
# Update from upstream
git fetch upstream
git checkout upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

## Development Workflow

### 1. Set Up Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 2. Make Changes

- Write code following the [style guide](#code-style)
- Add or update tests for your changes
- Update documentation if needed

### 3. Run Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov=api

# Run specific tests
pytest tests/unit/test_utils.py -v
```

### 4. Format Code

```bash
# Format with Black
black app tests

# Lint with Flake8
flake8 app tests

# Type check with mypy
mypy app
```

### 5. Commit Changes

```bash
# Stage changes
git add .

# Commit with clear message
git commit -m "feat: Add feature description"
# or
git commit -m "fix: Fix description"
# or
git commit -m "docs: Update documentation"
```

**Commit message types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style (formatting, missing semicolons, etc.)
- `refactor:` - Code refactor (no feature or bug fix)
- `test:` - Test changes
- `chore:` - Build process, dependencies, etc.

### 6. Push and Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Visit GitHub and create Pull Request
```

## Code Style

### Python Code Style

Follow [PEP 8](https://pep8.org/) and [Black](https://github.com/psf/black) formatting.

```python
# Good
def lookup_address(address: str, city_id: Optional[str] = None) -> Dict[str, Any]:
    """Look up an address.

    Args:
        address: The address string to look up
        city_id: Optional city identifier

    Returns:
        Dictionary with lookup results
    """
    pass

# Bad
def lookup_address(addr, city=None):
    pass
```

### Type Hints

Use type hints for all function parameters and return values:

```python
from typing import Optional, Dict, Any, List

def get_cities(state: Optional[str] = None) -> List[Dict[str, str]]:
    """Get list of cities."""
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def submit_report(
    address: str,
    trash_day: str,
    user_hash: Optional[str] = None
) -> ReportResponse:
    """Submit a crowdsourced report.

    Args:
        address: The address string
        trash_day: The day trash is picked up
        user_hash: Optional user identifier

    Returns:
        ReportResponse with submission status and consensus

    Raises:
        HTTPException: If validation fails
    """
    pass
```

### Variable and Function Naming

```python
# Good
normalized_address = normalize_address(raw_address)
is_verified = check_verification_status(consensus)
get_consensus_for_address(address_id)

# Bad
norm_addr = norm_add(raw_add)
verified = chk_ver(cons)
cons = getConsensus(aid)
```

## Testing Requirements

- **Minimum Coverage**: 80%
- **All new features** must have tests
- **All bug fixes** should have a test that catches the bug

### Writing Tests

```python
# tests/unit/test_feature.py
import pytest

def test_feature_basic_case():
    """Test basic functionality."""
    result = your_function("input")
    assert result == "expected"

def test_feature_edge_case():
    """Test edge cases."""
    result = your_function("")
    assert result is None

def test_feature_error_case():
    """Test error handling."""
    with pytest.raises(ValueError):
        your_function(None)
```

## Documentation Requirements

### API Documentation

If adding/modifying API endpoints:

1. Update docstrings in `app/main.py`
2. Update or create endpoint documentation in `/website/docs/api/`
3. Add examples to `/website/docs/api/examples.md`

### Code Comments

Add comments for:
- Complex algorithms
- Unintuitive logic
- Important business rules

```python
# Calculate consensus day using weighted scoring
# More recent reports receive higher weight (exponential decay)
consensus_day = calculate_consensus(reports)
```

## Pull Request Process

### 1. Describe Your Changes

- Clear title: "Add feature X" or "Fix issue #123"
- Description of what changed and why
- Link to related issues: "Closes #123"

### 2. Example PR Description

```markdown
## Description
Added new endpoint to interpret freeform address text using AI.

## Type of Change
- [x] New feature
- [ ] Bug fix
- [ ] Breaking change

## Related Issues
Closes #456

## Testing
- [x] Added unit tests
- [x] Added integration tests
- [x] Manual testing completed

## Checklist
- [x] Code follows style guidelines
- [x] Tests added/updated
- [x] Documentation updated
- [x] No breaking changes
```

### 3. Review Process

- Maintainers will review your PR
- Request changes if needed
- Approve and merge when ready

### 4. After Merge

Your contribution will be included in the next release. Thank you!

## Types of Contributions

### Code Contributions

- **Bug Fixes**: Address issues marked with `bug`
- **Features**: Implement issues marked with `enhancement`
- **Performance**: Optimize slow operations
- **Refactoring**: Improve code quality

### Documentation Contributions

- **API Docs**: Document endpoints and models
- **Guides**: Write how-to guides
- **Examples**: Add code examples
- **Fixes**: Correct typos and clarify unclear sections

### Community Contributions

- **Issues**: Report bugs and request features
- **Discussions**: Share ideas and feedback
- **Reviews**: Review open PRs
- **Support**: Help other users

## Useful Commands

```bash
# Update fork from upstream
git fetch upstream
git rebase upstream/main

# Clean up local branches
git branch -d feature/old-feature

# View commit history
git log --oneline -10

# Stash uncommitted changes
git stash
git stash pop
```

## Troubleshooting

### Merge Conflicts

```bash
# Update your branch
git fetch upstream
git rebase upstream/main

# Resolve conflicts in your editor
# Then continue
git rebase --continue
```

### Test Failures

```bash
# Run tests locally before pushing
pytest

# Run specific failing test
pytest tests/unit/test_file.py::test_name -v

# Check coverage
pytest --cov=app --cov-report=term-missing
```

### Linting Errors

```bash
# Format code
black app tests

# Fix import sorting
isort app tests

# Check linting
flake8 app tests
```

## Project Structure

```
TrashAlert/
├── app/                    # Main application
│   ├── main.py            # FastAPI app and endpoints
│   ├── models.py          # Database models
│   ├── schemas.py         # Pydantic schemas
│   ├── database.py        # Database configuration
│   ├── utils.py           # Utility functions
│   └── ...
├── tests/                 # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/                  # Project documentation
├── website/              # Docusaurus site
│   └── docs/
│       ├── api/
│       ├── guides/
│       ├── architecture/
│       └── pipeline/
├── scripts/              # Utility scripts
└── README.md
```

## Getting Help

- **Documentation**: Read the [docs](/docs/)
- **Issues**: Check [existing issues](https://github.com/TombStoneDash/TrashAlert/issues)
- **Discussions**: Join [GitHub Discussions](https://github.com/TombStoneDash/TrashAlert/discussions)
- **Email**: Email support@trashalert.com

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md
- Release notes
- Project website

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to TrashAlert! 🎉

