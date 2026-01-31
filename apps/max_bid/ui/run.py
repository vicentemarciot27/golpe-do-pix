"""
Script to run the Max Bid Calculator Streamlit application
"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    # Get the path to the main file
    main_file = Path(__file__).parent / "__main__.py"

    # Run streamlit with the home page as entry point
    # Streamlit will automatically discover pages in the pages/ folder
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(main_file),
            "--server.port=8501",
            "--server.address=localhost",
        ]
    )
