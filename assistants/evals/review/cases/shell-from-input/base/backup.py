"""Archive a directory named on the command line."""

import subprocess
import sys


def archive(directory):
    """Create <directory>.tar.gz next to the directory."""
    subprocess.run(["tar", "-czf", directory + ".tar.gz", directory], check=True)


if __name__ == "__main__":
    archive(sys.argv[1])
