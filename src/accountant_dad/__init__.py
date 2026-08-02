"""accountant-dad.

CI scaffolding only.

This package deliberately contains no engine, no accounting logic, no AI and no
Tally integration. It exists so the `build` gate has a real artifact to build,
install into a clean environment and import — proving the packaging path works
before any product code depends on it.

Adding domain logic here requires an amendment to the build freeze
(`CLAUDE.md` §P). See Amendment 1 for the scope of what is currently permitted.
"""

__all__ = ["__version__"]

__version__ = "0.0.0"
