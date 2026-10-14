"""Archive a directory named on the command line."""

import subprocess
import sys


def archive(directory, label):
    """Create <label>.tar.gz from the directory."""
    subprocess.run(f"tar -czf {label}.tar.gz {directory}", shell=True, check=True)


if __name__ == "__main__":
    archive(sys.argv[1], sys.argv[2])
