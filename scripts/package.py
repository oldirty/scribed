#!/usr/bin/env python3
"""
Local packaging and testing script for Scribed

This script helps developers test packaging locally before pushing tags.
"""

import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path


def run_command(cmd, cwd=None, check=True):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def build_python_packages():
    """Build Python source and wheel distributions."""
    print("=" * 50)
    print("Building Python packages...")
    print("=" * 50)

    # Clean previous builds
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")

    # Install build dependencies
    run_command(f"{sys.executable} -m pip install build twine")

    # Build packages
    run_command(f"{sys.executable} -m build")

    print("✅ Python packages built successfully!")
    print("Files created:")
    for file in os.listdir("dist"):
        print(f"  - dist/{file}")


def test_python_packages():
    """Test the built Python packages."""
    print("=" * 50)
    print("Testing Python packages...")
    print("=" * 50)

    # Check package integrity
    run_command("twine check dist/*")

    # Test installation in a temporary environment
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / "test_venv"

        # Create virtual environment
        run_command(f"{sys.executable} -m venv {venv_path}")

        # Get the right pip executable
        if os.name == "nt":  # Windows
            pip_exe = venv_path / "Scripts" / "pip.exe"
        else:  # Unix-like
            pip_exe = venv_path / "bin" / "pip"

        # Install the wheel
        wheel_file = None
        for file in os.listdir("dist"):
            if file.endswith(".whl"):
                wheel_file = f"dist/{file}"
                break

        if wheel_file:
            run_command(f"{pip_exe} install {wheel_file}")
            print("✅ Package installs successfully!")
        else:
            print("❌ No wheel file found to test!")


def build_windows_executable():
    """Build Windows executable using PyInstaller."""
    if os.name != "nt":
        print("⏭️  Skipping Windows executable (not on Windows)")
        return

    print("=" * 50)
    print("Building Windows executable...")
    print("=" * 50)

    # Install PyInstaller
    run_command(f"{sys.executable} -m pip install pyinstaller")

    # Build executable
    run_command(
        "pyinstaller --onefile --name scribed src/scribed/cli.py --hidden-import=scribed"
    )

    print("✅ Windows executable built successfully!")
    print(f"Executable: dist/scribed.exe")


def create_source_archive():
    """Create a source archive."""
    print("=" * 50)
    print("Creating source archive...")
    print("=" * 50)

    import zipfile

    # Get version from pyproject.toml or git tag
    version = "dev"
    try:
        result = run_command("git describe --tags --abbrev=0", check=False)
        if result.returncode == 0:
            version = result.stdout.strip().lstrip("v")
    except:
        pass

    archive_name = f"scribed-{version}-source.zip"

    with zipfile.ZipFile(archive_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("."):
            # Skip unwanted directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ["__pycache__", "build", "dist", "node_modules"]
            ]

            for file in files:
                if not file.startswith(".") and not file.endswith(".pyc"):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, ".")
                    zipf.write(file_path, arcname)

    print(f"✅ Source archive created: {archive_name}")


def main():
    """Main packaging script."""
    print("🚀 Scribed Local Packaging Script")
    print("=" * 50)

    if len(sys.argv) > 1:
        action = sys.argv[1]
    else:
        action = ""

    if action in ["", "help", "--help", "-h"]:
        print("Available actions:")
        print("  python    - Build Python packages")
        print("  test      - Test Python packages")
        print("  windows   - Build Windows executable")
        print("  source    - Create source archive")
        print("  all       - Do everything")
        print("\nUsage: python scripts/package.py <action>")
        return

    if action == "python":
        build_python_packages()
    elif action == "test":
        test_python_packages()
    elif action == "windows":
        build_windows_executable()
    elif action == "source":
        create_source_archive()
    elif action == "all":
        build_python_packages()
        test_python_packages()
        if os.name == "nt":
            build_windows_executable()
        create_source_archive()
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

    print("\n🎉 Packaging complete!")


if __name__ == "__main__":
    main()
