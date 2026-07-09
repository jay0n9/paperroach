"""PaperRoach public package alias.

The implementation currently lives in the historical ``kb`` package. This
module keeps the public project name aligned without breaking existing imports.
"""

from kb import __version__

__all__ = ["__version__"]
