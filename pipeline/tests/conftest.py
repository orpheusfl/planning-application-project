"""
Pytest configuration for the pipeline tests.

Ensures the pipeline directory is in the Python path so that utilities module
can be imported correctly.
"""

import sys
from pathlib import Path

# Add the pipeline directory to sys.path
pipeline_dir = Path(__file__).parent
sys.path.insert(0, str(pipeline_dir))
