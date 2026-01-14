#!/usr/bin/env python3
"""
Vocard Startup Script
Ensures Lavalink is running before starting the Discord bot.
"""

import os
import sys
import time
import subprocess
import socket
import requests
from typing import Optional, Tuple


# Configuration
LAVALINK_HOST = "localhost"
LAVALINK_PORT = 2333
LAVALINK_PASSWORD = "youshallnotpass"
LAVALINK_URL = f"http://{LAVALINK_HOST}:{LAVALINK_PORT}"
MAX_WAIT_TIME = 120  # Maximum time to wait for Lavalink (seconds)
CHECK_INTERVAL = 2  # Time between health checks (seconds)

# Virtual environment paths to check
VENV_PATHS = ["venv", ".venv", "env", ".env"]


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_colored(message: str, color: str = Colors.OKBLUE):
    """Print colored message to console"""
    print(f"{color}{message}{Colors.ENDC}")


def find_venv() -> Tuple[Optional[str], Optional[str]]:
    """
    Find virtual environment in the project directory.
    Returns tuple of (venv_path, python_executable)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    for venv_name in VENV_PATHS:
        venv_path = os.path.join(script_dir, venv_name)
        
        if os.path.isdir(venv_path):
            # Check for Python executable in venv
            if sys.platform == "win32":
                python_exe = os.path.join(venv_path, "Scripts", "python.exe")
            else:
                python_exe = os.path.join(venv_path, "bin", "python")
            
            if os.path.isfile(python_exe):
                return venv_path, python_exe
    
    return None, None


def get_python_executable() -> str:
    """
    Get the appropriate Python executable.
    Returns venv python if available, otherwise system python.
    """
    # Check if already running in a venv
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print_colored("✓ Already running in virtual environment", Colors.OKGREEN)
        return sys.executable
    
    # Try to find a venv
    venv_path, python_exe = find_venv()
    
    if python_exe:
        print_colored(f"✓ Found virtual environment: {os.path.basename(venv_path)}", Colors.OKGREEN)
        return python_exe
    
    # Fallback to system python
    print_colored("⚠ No virtual environment found, using system Python", Colors.WARNING)
    return sys.executable


def is_port_in_use(port: int, host: str = "localhost") -> bool:
    """Check if a port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result == 0
        except socket.error:
            return False


def check_lavalink_health() -> bool:
    """Check if Lavalink is healthy and responding"""
    try:
        headers = {"Authorization": LAVALINK_PASSWORD}
        response = requests.get(
            f"{LAVALINK_URL}/version",
            headers=headers,
            timeout=5
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def wait_for_lavalink() -> bool:
    """Wait for Lavalink to become ready"""
    print_colored("⏳ Waiting for Lavalink to be ready...", Colors.OKCYAN)
    
    elapsed = 0
    while elapsed < MAX_WAIT_TIME:
        if check_lavalink_health():
            print_colored("✓ Lavalink is ready!", Colors.OKGREEN)
            return True
        
        time.sleep(CHECK_INTERVAL)
        elapsed += CHECK_INTERVAL
        
        # Print progress every 10 seconds
        if elapsed % 10 == 0:
            print_colored(f"  Still waiting... ({elapsed}s / {MAX_WAIT_TIME}s)", Colors.WARNING)
    
    return False


def start_lavalink_docker() -> Optional[subprocess.Popen]:
    """Start Lavalink using Docker Compose"""
    print_colored("🐳 Starting Lavalink with Docker Compose...", Colors.OKCYAN)
    
    try:
        # Check if docker-compose is available
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True
        )
        
        # Start only the lavalink service
        process = subprocess.Popen(
            ["docker", "compose", "up", "lavalink"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        print_colored("✓ Docker Compose command executed", Colors.OKGREEN)
        return process
        
    except subprocess.CalledProcessError:
        print_colored("✗ Docker Compose not found or failed to start", Colors.FAIL)
        return None
    except FileNotFoundError:
        print_colored("✗ Docker not found on system", Colors.FAIL)
        return None


def start_bot(python_exe: str):
    """Start the Discord bot"""
    print_colored("\n🤖 Starting Vocard Discord Bot...", Colors.OKCYAN)
    print_colored("=" * 50, Colors.HEADER)
    
    try:
        # Run main.py with the appropriate Python interpreter
        subprocess.run([python_exe, "main.py"], check=True)
    except KeyboardInterrupt:
        print_colored("\n\n✓ Bot stopped by user", Colors.WARNING)
    except subprocess.CalledProcessError as e:
        print_colored(f"\n✗ Bot exited with error code {e.returncode}", Colors.FAIL)
        sys.exit(e.returncode)


def check_requirements(python_exe: str):
    """Check if requirements are installed"""
    print_colored("📦 Checking requirements...", Colors.OKCYAN)
    
    if not os.path.exists("requirements.txt"):
        print_colored("✗ requirements.txt not found!", Colors.FAIL)
        return False
    
    # Check if modules are importable with the selected Python
    check_imports = subprocess.run(
        [python_exe, "-c", "import discord; import voicelink"],
        capture_output=True
    )
    
    if check_imports.returncode == 0:
        print_colored("✓ Core dependencies found", Colors.OKGREEN)
        return True
    else:
        print_colored("⚠ Some dependencies might be missing", Colors.WARNING)
        venv_path, _ = find_venv()
        if venv_path:
            print_colored(f"  Run: source {venv_path}/bin/activate && pip install -r requirements.txt", Colors.WARNING)
        else:
            print_colored("  Run: python3 -m pip install -r requirements.txt", Colors.WARNING)
        
        response = input("\nWould you like to install dependencies now? (y/n): ").lower()
        if response == 'y':
            try:
                subprocess.run(
                    [python_exe, "-m", "pip", "install", "-r", "requirements.txt"],
                    check=True
                )
                print_colored("✓ Dependencies installed", Colors.OKGREEN)
                return True
            except subprocess.CalledProcessError:
                print_colored("✗ Failed to install dependencies", Colors.FAIL)
                return False
        return False


def main():
    """Main startup sequence"""
    print_colored("""
╔═══════════════════════════════════════╗
║        Vocard Startup Script          ║
╚═══════════════════════════════════════╝
    """, Colors.HEADER)
    
    # Get the appropriate Python executable
    python_exe = get_python_executable()
    print_colored(f"Using Python: {python_exe}", Colors.OKBLUE)
    print()
    
    # Check if requirements are installed
    if not check_requirements(python_exe):
        print_colored("\n✗ Please install requirements before continuing", Colors.FAIL)
        sys.exit(1)
    
    print()
    
    # Check if Lavalink is already running
    if is_port_in_use(LAVALINK_PORT, LAVALINK_HOST):
        print_colored(f"✓ Lavalink is already running on port {LAVALINK_PORT}", Colors.OKGREEN)
        
        # Verify it's actually Lavalink and healthy
        if check_lavalink_health():
            print_colored("✓ Lavalink health check passed", Colors.OKGREEN)
        else:
            print_colored("⚠ Port is in use but Lavalink health check failed", Colors.WARNING)
            print_colored("  Continuing anyway...", Colors.WARNING)
    else:
        print_colored(f"⚠ Lavalink not detected on port {LAVALINK_PORT}", Colors.WARNING)
        
        # Try to start Lavalink with Docker
        lavalink_process = start_lavalink_docker()
        
        if lavalink_process is None:
            print_colored("\n✗ Could not start Lavalink automatically", Colors.FAIL)
            print_colored("Please start Lavalink manually with one of these methods:", Colors.WARNING)
            print_colored("  1. Docker: docker compose up lavalink", Colors.WARNING)
            print_colored("  2. Java: java -jar Lavalink.jar", Colors.WARNING)
            sys.exit(1)
        
        # Wait for Lavalink to be ready
        if not wait_for_lavalink():
            print_colored(f"\n✗ Lavalink did not become ready within {MAX_WAIT_TIME} seconds", Colors.FAIL)
            print_colored("Please check Lavalink logs for errors", Colors.WARNING)
            
            # Clean up the process
            if lavalink_process:
                lavalink_process.terminate()
            
            sys.exit(1)
    
    # Start the bot
    print_colored("\n" + "=" * 50, Colors.HEADER)
    start_bot(python_exe)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n✓ Startup cancelled by user", Colors.WARNING)
        sys.exit(0)
    except Exception as e:
        print_colored(f"\n✗ Unexpected error: {e}", Colors.FAIL)
        sys.exit(1)
