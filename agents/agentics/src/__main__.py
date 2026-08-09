"""Entry point for running the agentics pipeline as `python -m src.agentics`."""
import sys
import os

# Add the src directory to the path so relative imports work
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Now import and run the main module
from agentics import main

if __name__ == "__main__":
    main()
