#!/usr/bin/env python3
"""
+===========================================================================+
|                                                                           |
|                    CLAUDE PATENT CREATOR INSTALLER                        |
|                     One-Command Setup and Configuration                   |
|                                                                           |
+===========================================================================+

DESCRIPTION:
    Simplified setup script that automatically configures the Claude Patent
    Creator MCP server with optimal settings for your system. Handles all
    dependencies, data downloads, and Claude Code integration.

REQUIREMENTS:
    - Python 3.9+ must be installed
    - Virtual environment must be created and activated BEFORE running
    - ~1GB free disk space (minimum)
    - ~30GB for full patent corpus (optional, not recommended)

VIRTUAL ENVIRONMENT NOTES:
    After installation, Claude Code automatically manages the virtual environment.
    Manual activation is ONLY needed for:
    - Running this install.py script initially
    - Manually updating dependencies with pip
    - Running CLI commands outside Claude Code
    - Troubleshooting or advanced operations

FEATURES:
    [OK] Auto-detects OS (Windows/Linux/macOS) and hardware (GPU)
    [OK] Installs PyTorch with correct CUDA version for NVIDIA GPUs
    [OK] Downloads USPTO examination rules (MPEP, 35 USC, 37 CFR)
    [OK] Configures BigQuery patent search (100M+ patents, FREE)
    [OK] Registers MCP server with Claude Code automatically
    [OK] Installs Pydantic for input validation
    [OK] Sets up structured logging and performance monitoring
    [OK] Configures optional Graphviz for diagram generation
    [OK] Optional: 9.2M patent corpus for offline search (NOT RECOMMENDED)

INSTALLATION STEPS:

    # Windows (PowerShell):
    python -m venv venv
    venv\\Scripts\\activate
    python install.py

    # Linux/macOS:
    python3 -m venv venv
    source venv/bin/activate
    python install.py

    # After installation, restart Claude Code!

WHAT GETS INSTALLED:
    Core Dependencies:
    - PyTorch (CPU or CUDA-optimized for GPU)
    - Sentence Transformers (embedding models)
    - FAISS (vector search)
    - NumPy, BeautifulSoup, lxml
    - Pydantic & pydantic-settings (NEW - validation and config)
    - MCP server framework
    - Google Cloud BigQuery client (optional)
    - Graphviz (optional, for diagrams)

    Data Downloads (Optional):
    - MPEP Manual + 35 USC + 37 CFR (~500MB)
    - Patent corpus (~13GB, indexing takes 24+ hours)

    Integration:
    - Registers with Claude Code MCP system
    - Sets up project commands and skills
    - Configures environment variables

NEW IN THIS VERSION:
    [OK] Structured logging with JSON support
    [OK] Performance monitoring and metrics tracking
    [OK] Pydantic input validation for all tools
    [OK] Type-safe configuration management
    [OK] Enhanced error handling with detailed context
    [OK] Backward compatible graceful fallbacks
    See IMPROVEMENTS_SUMMARY.md for full details

RECENT CHANGES:
    2025-11-11: Added Pydantic validation and structured logging
    2025-11-11: Implemented performance monitoring and metrics
    2025-11-11: Enhanced error handling with MCP best practices
    2025-11-09: Add timeout handling to prevent indefinite hangs
    2025-11-09: Auto-remove existing MCP registration before re-registering
    2025-11-08: Fixed installation order (PyTorch before other deps)
    2025-11-08: Added package verification before MPEP download
    2025-11-08: Auto-installs correct PyTorch for RTX 5090/5080 (CUDA 12.8)
    2025-11-08: Fixed GPU detection using nvidia-smi with compute capability
    2025-11-08: Auto-selects CUDA version based on GPU (12.4 or 12.8)
    2025-11-08: PDFs now stored in pdfs/ directory (not project root)
    2025-11-08: Added PDF cleanup prompt after successful indexing

DOCUMENTATION:
    - README.md - Quick start guide
    - ADVANCED-README.md - Technical documentation
    - GPU_SETUP.md - GPU configuration details
    - IMPROVEMENTS_SUMMARY.md - Latest enhancements
    - BIGQUERY_SETUP.md - BigQuery configuration
    - Issues: https://github.com/RobThePCGuy/Claude-Patent-Creator/issues

"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


class Colors:
    """Terminal colors for output"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(message):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")


def print_success(message):
    """Print success message"""
    print(f"{Colors.OKGREEN}[OK] {message}{Colors.ENDC}")


def print_error(message):
    """Print error message"""
    print(f"{Colors.FAIL}[X] {message}{Colors.ENDC}")


def print_info(message):
    """Print info message"""
    print(f"{Colors.OKCYAN}[INFO] {message}{Colors.ENDC}")


def print_warning(message):
    """Print warning message"""
    print(f"{Colors.WARNING}[WARNING] {message}{Colors.ENDC}")


def run_command(cmd, description, check=True, show_output=False):
    """Run shell command with pretty output"""
    try:
        print_info(f"{description}...")
        if show_output:
            # For commands that need to show real-time output (like pip installs)
            result = subprocess.run(cmd, shell=True, check=check)
            if result.returncode == 0:
                print_success(f"{description} complete")
                return True
            else:
                if check:
                    print_error(f"{description} failed")
                return False
        else:
            # For commands where we want to capture output
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
            if result.returncode == 0:
                print_success(f"{description} complete")
                return True
            else:
                if check:
                    print_error(f"{description} failed")
                    if result.stderr:
                        print(f"   {result.stderr[:200]}")
                return False
    except Exception as e:
        print_error(f"{description} failed: {e}")
        return False


def detect_environment():
    """Detect user's OS and hardware"""
    print_header("DETECTING YOUR ENVIRONMENT")

    env_info = {
        "os": platform.system(),
        "arch": platform.machine(),
        "python_version": sys.version.split()[0],
        "has_gpu": False,
        "gpu_type": None,
    }

    # Detect GPU using system tools (before PyTorch is installed)
    if env_info["os"] == "Windows":
        # Check for NVIDIA GPU using nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,compute_cap", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                env_info["has_gpu"] = True
                env_info["gpu_type"] = "NVIDIA"
                # Parse compute capability (e.g., "8.9" for RTX 4090, "12.0" for RTX 5090)
                output = result.stdout.strip()
                if "," in output:
                    compute_cap = output.split(",")[1].strip()
                    env_info["compute_capability"] = float(compute_cap)
        except subprocess.TimeoutExpired:
            print_warning("nvidia-smi timed out - GPU detection skipped")
        except Exception:
            pass
    elif env_info["os"] == "Linux":
        # Try nvidia-smi first
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,compute_cap", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                env_info["has_gpu"] = True
                env_info["gpu_type"] = "NVIDIA"
                # Parse compute capability
                output = result.stdout.strip()
                if "," in output:
                    compute_cap = output.split(",")[1].strip()
                    env_info["compute_capability"] = float(compute_cap)
        except subprocess.TimeoutExpired:
            print_warning("nvidia-smi timed out - GPU detection skipped")
        except Exception:
            pass

        # Try detecting AMD GPU
        if not env_info["has_gpu"]:
            try:
                result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
                if "AMD" in result.stdout and "VGA" in result.stdout:
                    env_info["has_gpu"] = True
                    env_info["gpu_type"] = "AMD"
            except subprocess.TimeoutExpired:
                print_warning("lspci timed out - AMD GPU detection skipped")
            except Exception:
                pass

    print_success(f"OS: {env_info['os']}")
    print_success(f"Architecture: {env_info['arch']}")
    print_success(f"Python: {env_info['python_version']}")

    if env_info["has_gpu"]:
        gpu_msg = f"GPU: {env_info['gpu_type']} detected"
        if env_info.get("compute_capability"):
            gpu_msg += f" (Compute {env_info['compute_capability']})"
        print_success(gpu_msg)

        # RTX 5090/5080 need CUDA 12.8, older GPUs use CUDA 12.4
        if env_info.get("compute_capability", 0) >= 10.0:
            print_info("RTX 5090/5080 detected - will install PyTorch with CUDA 12.8")
            env_info["cuda_version"] = "cu128"
        else:
            env_info["cuda_version"] = "cu124"
    else:
        print_info("No GPU detected - will use CPU")

    return env_info


def check_virtual_environment():
    """Check if running inside a virtual environment"""
    print_header("CHECKING VIRTUAL ENVIRONMENT")

    # Check if we're in a virtual environment
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    if in_venv:
        print_success("Virtual environment is active")
        return True
    else:
        print_error("Virtual environment is NOT active")
        print_info("")
        print_info("Please create and activate a virtual environment first:")
        print_info("(This is only required for running install.py)")
        print_info("")

        if platform.system() == "Windows":
            print_info("Windows (PowerShell):")
            print_info("  python -m venv venv")
            print_info("  venv\\Scripts\\activate")
        else:
            print_info("Linux/macOS:")
            print_info("  python3 -m venv venv")
            print_info("  source venv/bin/activate")

        print_info("")
        print_info("Then run this installer again:")
        print_info("  python install.py")
        print_info("")
        print_info("After installation, Claude Code will manage the venv automatically!")
        return False


def get_venv_python():
    """Get path to Python executable in virtual environment"""
    # Since we're running inside the venv, just use the current Python
    return sys.executable


def install_dependencies(env_info):
    """Install required Python packages with optimal configuration

    Order matters:
    1. Install PyTorch with correct CUDA version FIRST
    2. Then install package dependencies (won't reinstall torch)
    3. Verify all imports work before proceeding

    NEW: Includes Pydantic for validation and structured logging modules
    """
    print_header("INSTALLING DEPENDENCIES")
    print_info("")
    print_info("This includes:")
    print_info("  * PyTorch (with GPU support if available)")
    print_info("  * Sentence Transformers and FAISS")
    print_info("  * Pydantic for validation (NEW)")
    print_info("  * BigQuery client (optional)")
    print_info("  * All other project dependencies")
    print_info("")

    venv_python = get_venv_python()

    # Upgrade pip first
    print_info("Installing core dependencies...")
    if not run_command(
        f'"{venv_python}" -m pip install --upgrade pip',
        "Upgrading pip",
        show_output=True,
    ):
        return False

    # Install PyTorch FIRST with correct CUDA version to avoid CPU version being installed by dependencies
    if env_info["has_gpu"] and env_info["gpu_type"] == "NVIDIA":
        cuda_ver = env_info.get("cuda_version", "cu124")
        # Extract CUDA version from cu124 -> 12.4 or cu128 -> 12.8
        cuda_display = f"{cuda_ver[2:4]}.{cuda_ver[4:]}" if len(cuda_ver) == 5 else cuda_ver[2:]
        print_info(f"Installing PyTorch with CUDA {cuda_display}...")
        if not run_command(
            f'"{venv_python}" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/{cuda_ver}',
            f"Installing PyTorch with CUDA {cuda_display}",
            show_output=True,
        ):
            print_error("Failed to install PyTorch with CUDA")
            return False
    else:
        print_info("Installing PyTorch (CPU)...")
        if not run_command(
            f'"{venv_python}" -m pip install torch torchvision torchaudio',
            "Installing PyTorch (CPU)",
            show_output=True,
        ):
            print_error("Failed to install PyTorch")
            return False

    # Now install the rest of the package (won't reinstall torch since it's already there)
    print_info("Installing remaining dependencies...")
    if not run_command(
        f'"{venv_python}" -m pip install -e .',
        "Installing package dependencies",
        show_output=True,
    ):
        return False

    # No need to force reinstall - compatible versions are specified in pyproject.toml

    # Verify critical imports work
    print_info("Verifying installations...")

    # Test each import separately for better error reporting
    test_imports = [
        ("torch", "PyTorch"),
        ("sentence_transformers", "Sentence Transformers"),
        ("faiss", "FAISS"),
        ("numpy", "NumPy"),
    ]

    all_ok = True
    for module, name in test_imports:
        verify_cmd = f'"{venv_python}" -c "import {module}; print(\'OK\')"'
        result = subprocess.run(verify_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print_error(f"{name} import failed")
            if result.stderr:
                # Show full error for debugging
                error_lines = result.stderr.strip().split("\n")
                for line in error_lines[-10:]:  # Last 10 lines
                    print(f"   {line}")
            all_ok = False
        else:
            print_success(f"{name} verified")

    if not all_ok:
        print_error("Some packages failed verification")
        print_info("")
        print_info("This usually means conflicting package versions.")
        print_info("To fix:")
        print_info("  1. Delete the venv directory: rmdir /s venv")
        print_info("  2. Create fresh venv: python -m venv venv")
        print_info("  3. Activate: venv\\Scripts\\activate")
        print_info("  4. Run installer again: python install.py")
        return False

    print_success("All dependencies installed and verified")
    return True


def download_mpep_data():
    """Download and index MPEP data"""
    print_header("DOWNLOADING USPTO EXAMINATION RULES")
    print_info("This will download MPEP, 35 USC, and 37 CFR (~500MB)")
    print_info("Takes about 5-10 minutes depending on your internet speed")

    venv_python = get_venv_python()

    response = input("\nDownload now? (y/n): ").lower()
    if response == "y":
        if run_command(
            f'"{venv_python}" -m mcp_server.cli setup',
            "Downloading MPEP data",
            show_output=True,
        ):
            print_success("USPTO examination rules downloaded and indexed")
            return True
    else:
        print_warning("Skipped MPEP download - you can run 'patent-creator setup' later")
    return False


def setup_bigquery():
    """Interactive BigQuery setup with gcloud authentication"""
    print_header("BIGQUERY PATENT SEARCH SETUP (FREE)")
    print_info("")
    print_success("[OK] No credit card needed")
    print_success("[OK] No billing setup required")
    print_success("[OK] 1 TB free queries per month")
    print_info("")

    # Check if gcloud is installed
    gcloud_path = shutil.which("gcloud")

    if not gcloud_path:
        print_warning("gcloud CLI not found")
        print_info("")
        print_info("Step 1: Install gcloud CLI")
        print_info("  Download from: https://cloud.google.com/sdk/docs/install")
        print_info("")

        if platform.system() == "Windows":
            print_info("  Windows: Download the installer and run it")
            print_info(
                "  https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe"
            )
        elif platform.system() == "Darwin":
            print_info("  macOS: Run in terminal:")
            print_info("  curl https://sdk.cloud.google.com | bash")
        else:
            print_info("  Linux: Run in terminal:")
            print_info("  curl https://sdk.cloud.google.com | bash")

        print_info("")
        response = input("Press Enter after installing gcloud (or 's' to skip): ").lower()
        if response == "s":
            print_warning("Skipped - BigQuery will not work without authentication")
            return False

        # Check again after install
        gcloud_path = shutil.which("gcloud")
        if not gcloud_path:
            print_error("gcloud still not found - may need to restart terminal")
            print_info("After restarting, run: gcloud auth application-default login")
            return False

    print_success(f"gcloud CLI found at: {gcloud_path}")
    print_info("")
    print_info("Step 2: Authenticate with Google")
    print_info("  This will open a browser for you to sign in")
    print_info("")

    response = input("Authenticate now? (y/n): ").lower()
    if response != "y":
        print_warning("Skipped authentication")
        print_info("Run later: gcloud auth application-default login")
        return False

    print_info("")
    print_info("Opening browser for authentication...")
    print_info("(If browser doesn't open, copy the URL from the terminal)")
    print_info("")

    if run_command(
        "gcloud auth application-default login",
        "Authenticating with Google",
        check=False,
        show_output=True,
    ):
        print_success("Authentication complete!")
        print_info("")
        print_info("BigQuery is now ready to use")
        print_info("Your credentials are saved and will work automatically")
        return True
    else:
        print_error("Authentication failed")
        print_info("Try again: gcloud auth application-default login")
        return False


def install_graphviz():
    """Install Graphviz for diagram generation"""
    print_header("INSTALLING DIAGRAM TOOLS (OPTIONAL)")
    print_info("Graphviz enables generation of patent-style technical diagrams")

    response = input("\nInstall Graphviz? (y/n): ").lower()
    if response == "y":
        print_info("Attempting automatic installation...")
        # Quote sys.executable (may contain spaces) and resolve the script path
        # relative to this file so it works regardless of the current directory.
        # run_command uses shell=True, so paths are quoted rather than passed as a list.
        graphviz_script = Path(__file__).parent / "scripts" / "install_graphviz.py"
        run_command(
            f'"{sys.executable}" "{graphviz_script}"',
            "Installing Graphviz",
            check=False,
            show_output=True,
        )
    else:
        print_info("Skipped Graphviz - diagrams will not be available")
        print_info("You can install later by running: python scripts/install_graphviz.py")


def register_with_claude():
    """Register MCP server with Claude Code"""
    print_header("CONNECTING TO CLAUDE CODE")

    # Get absolute paths - use Path.resolve() to ensure clean absolute paths
    project_root = Path(__file__).parent.resolve()
    python_path = Path(get_venv_python()).resolve()  # sys.executable is already absolute
    server_path = (project_root / "mcp_server" / "server.py").resolve()

    # Verify paths exist
    if not python_path.exists():
        print_error(f"Python executable not found: {python_path}")
        return False

    if not server_path.exists():
        print_error(f"Server file not found: {server_path}")
        return False

    # Check if Claude Code CLI is available
    claude_cli = shutil.which("claude")
    if not claude_cli:
        print_error("Claude Code CLI not found")
        print_info("Please install Claude Code first: https://claude.com/code")
        return False

    # On Windows, Claude CLI requires git-bash
    if platform.system() == "Windows":
        bash_path = shutil.which("bash")
        if bash_path:
            # Set environment variable for Claude CLI to find git-bash
            os.environ["CLAUDE_CODE_GIT_BASH_PATH"] = bash_path
            print_info(f"Set CLAUDE_CODE_GIT_BASH_PATH to: {bash_path}")

    print_info("Registering MCP server...")
    print_info(f"Python: {python_path}")
    print_info(f"Server: {server_path}")

    # Convert to string with forward slashes for cross-platform compatibility
    # Claude CLI expects consistent path format
    python_str = str(python_path).replace("\\", "/")
    server_str = str(server_path).replace("\\", "/")

    # Remove existing registration if present to avoid "already exists" error
    try:
        subprocess.run(
            ["claude", "mcp", "remove", "claude-patent-creator"],
            capture_output=True,
            timeout=10,
        )
        print_info("Removed existing MCP server registration")
    except Exception:
        pass

    cmd = f'claude mcp add --transport stdio claude-patent-creator --scope user -- "{python_str}" "{server_str}"'

    if run_command(cmd, "Registering with Claude Code", check=False):
        print_success("Successfully registered with Claude Code")
        print_info("")
        print_info("Verify with: claude mcp list")
        print_info("")
        print_info("Expected configuration in ~/.claude.json:")
        print_info(f'  "command": "{python_str}"')
        print_info(f'  "args": ["{server_str}"]')
        print_info("")
        print_warning("IMPORTANT: If the server fails to start, check ~/.claude.json")
        print_warning(f"  Python path should be: {python_str}")
        print_warning(f"  Server path should be: {server_str}")
        return True
    else:
        print_error("Auto-registration failed")
        print_info("")
        print_info("Manual registration command:")
        print(f"\n{cmd}\n")
        print_info("")
        print_info("Or manually edit ~/.claude.json with:")
        print_info(f'  "command": "{python_str}"')
        print_info(f'  "args": ["{server_str}"]')
        return False


def main():
    """Main setup workflow"""
    print(
        f"""
{Colors.HEADER}{Colors.BOLD}
+============================================================+
|                                                            |
|           CLAUDE PATENT CREATOR SETUP                      |
|           One-Command Installation                         |
|                                                            |
+============================================================+
{Colors.ENDC}
    """
    )

    # Step 1: Check virtual environment
    if not check_virtual_environment():
        return 1

    # Step 2: Detect environment
    env_info = detect_environment()

    # Step 3: Install dependencies
    if not install_dependencies(env_info):
        print_error("Failed to install dependencies")
        return 1

    # Step 4: Download MPEP data
    download_mpep_data()

    # Step 5: Setup BigQuery
    setup_bigquery()

    # Step 6: Optional Graphviz
    install_graphviz()

    # Step 7: Register with Claude Code
    register_with_claude()

    # Done
    venv_activate_cmd = (
        "venv\\Scripts\\activate" if platform.system() == "Windows" else "source venv/bin/activate"
    )

    print(
        f"""
{Colors.OKGREEN}{Colors.BOLD}
+============================================================================+
|                                                                            |
|                          SETUP COMPLETE! [OK]                                 |
|                   Patent Creator Ready to Use                              |
|                                                                            |
+============================================================================+
{Colors.ENDC}

{Colors.HEADER}{Colors.BOLD}NEW FEATURES INSTALLED:{Colors.ENDC}
  [OK] Structured logging with JSON support
  [OK] Performance monitoring and metrics
  [OK] Pydantic input validation
  [OK] Enhanced error handling
  See IMPROVEMENTS_SUMMARY.md for full details

{Colors.OKCYAN}{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}

{Colors.OKCYAN}NEXT STEPS:{Colors.ENDC}

{Colors.BOLD}1. Restart Claude Code{Colors.ENDC} (if currently running)
   * Close and reopen Claude Code to load the MCP server

{Colors.BOLD}2. Setup Commands in Your Project{Colors.ENDC}
   * Open your project in Claude Code
   * Ask Claude: {Colors.OKGREEN}"Please setup the patent creator commands for this project"{Colors.ENDC}
   * Claude will copy the .claude folder to your project directory
   * Available commands will appear in autocomplete

{Colors.BOLD}3. Try It Out - Example Queries{Colors.ENDC}
   {Colors.OKBLUE}MPEP Search:{Colors.ENDC}
   * "Search MPEP for claim indefiniteness requirements"
   * "What are the 35 USC 112 enablement requirements?"

   {Colors.OKBLUE}Patent Creation:{Colors.ENDC}
   * "Review my patent claims for compliance"
   * "Check this specification for 112(a) compliance"
   * "Verify formalities in this patent application"

   {Colors.OKBLUE}Prior Art Search:{Colors.ENDC}
   * "Search patents for prior art on machine learning image recognition"
   * "Find patents in CPC class G06F related to neural networks"

{Colors.BOLD}4. Patent Search Tools Available{Colors.ENDC}
   {Colors.OKGREEN}[OK] BigQuery (RECOMMENDED){Colors.ENDC} - search_patents_bigquery
     * 100M+ worldwide patents, instant access, FREE (1TB/month)

   {Colors.OKGREEN}[OK] USPTO API{Colors.ENDC} - search_uspto_api
     * Real-time US patent data, official USPTO source

{Colors.BOLD}5. Available Slash Commands{Colors.ENDC} (after setup in project)
   * {Colors.OKGREEN}/full-review{Colors.ENDC}        - Complete patent application review
   * {Colors.OKGREEN}/review-claims{Colors.ENDC}      - Analyze patent claims for 112(b) compliance
   * {Colors.OKGREEN}/review-specification{Colors.ENDC} - Check specification for 112(a) support
   * {Colors.OKGREEN}/review-formalities{Colors.ENDC} - Verify MPEP 608 formalities requirements
   * {Colors.OKGREEN}/create-patent{Colors.ENDC}      - Generate complete patent application

{Colors.OKCYAN}{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}

{Colors.OKCYAN}CONFIGURATION (Optional):{Colors.ENDC}

{Colors.BOLD}Logging Configuration{Colors.ENDC} (Environment Variables)
  PATENT_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
  PATENT_LOG_FORMAT=human        # human (colored) or json (production)
  PATENT_LOG_FILE=logs/app.log   # Optional file output

{Colors.BOLD}Performance Tuning{Colors.ENDC}
  PATENT_ENABLE_METRICS=true     # Enable performance tracking
  PATENT_OPERATION_TIMEOUT=300   # Timeout in seconds (default: 5 min)
  PATENT_ENABLE_CACHE=true       # Enable result caching

{Colors.BOLD}API Configuration{Colors.ENDC}
  USPTO_API_KEY=your_key         # USPTO API key (optional)
  PATENT_BIGQUERY_PROJECT_ID=... # Google Cloud project (if using BigQuery)

{Colors.OKCYAN}{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}

{Colors.OKCYAN}VIRTUAL ENVIRONMENT:{Colors.ENDC}
  * {Colors.BOLD}Claude Code handles this automatically!{Colors.ENDC}
  * Manual activation only needed for:
    - Running install.py
    - Manual pip updates
    - CLI commands outside Claude Code
  * To activate: {Colors.OKBLUE}{venv_activate_cmd}{Colors.ENDC}
  * To deactivate: {Colors.OKBLUE}deactivate{Colors.ENDC}

{Colors.OKCYAN}{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}

{Colors.OKCYAN}DOCUMENTATION:{Colors.ENDC}
  * README.md                  - Quick start guide
  * IMPROVEMENTS_SUMMARY.md    - Latest enhancements (NEW!)
  * ADVANCED-README.md         - Technical documentation
  * BIGQUERY_SETUP.md          - BigQuery configuration guide
  * GPU_SETUP.md               - GPU optimization details

{Colors.OKCYAN}NEED HELP?{Colors.ENDC}
  * Issues: https://github.com/RobThePCGuy/Claude-Patent-Creator/issues
  * Discussions: Ask questions in GitHub Discussions
  * Contact: Please open an issue or use Discussions for support

{Colors.OKCYAN}{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}

{Colors.OKGREEN}{Colors.BOLD} Happy Patenting! {Colors.ENDC}

{Colors.OKCYAN}The Claude Patent Creator is now ready to help you with:
  * USPTO MPEP rule searches
  * Patent application reviews
  * Prior art searches (100M+ patents via BigQuery)
  * Patent diagrams and flowcharts
  * Complete patent application creation{Colors.ENDC}

{Colors.BOLD}Restart Claude Code to activate!{Colors.ENDC}
    """
    )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Setup cancelled by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
