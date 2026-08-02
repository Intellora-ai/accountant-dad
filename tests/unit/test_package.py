"""The build gate ships this package. Prove it imports and stays free of domain logic."""

import accountant_dad


def test_package_imports_and_exposes_a_version() -> None:
    assert accountant_dad.__version__ == "0.0.0"


def test_package_contains_no_domain_logic() -> None:
    # Build-freeze guard. This package is CI scaffolding; it must stay that way
    # until the freeze is amended again. See CLAUDE.md section P, Amendment 1.
    public = [name for name in vars(accountant_dad) if not name.startswith("_")]
    assert public == [], f"unexpected public names: {public}"
