"""Unified file download utilities for USPTO resources"""

import socket
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional


def _create_ssl_context() -> ssl.SSLContext:
    """Build an SSL context with an explicit CA bundle.

    The python.org macOS installer ships OpenSSL without a system CA bundle, so
    ``urllib`` downloads from HTTPS hosts (e.g. the USPTO MPEP zip) fail with
    ``CERTIFICATE_VERIFY_FAILED``. ``certifi`` is available transitively via
    ``requests``; pointing the context at ``certifi.where()`` fixes verification
    on those interpreters while remaining correct everywhere else. If ``certifi``
    is somehow unavailable we fall back to the platform default context.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class FileDownloader:
    """Handles file downloads with progress tracking and error handling"""

    @staticmethod
    def download_with_progress(
        url: str,
        dest_path: Path,
        file_description: str,
        timeout_seconds: int = 120,
        use_mb: bool = False,
        manual_instructions: Optional[str] = None,
    ) -> bool:
        """Download file with progress bar and comprehensive error handling.

        Args:
            url: URL to download from
            dest_path: Local path to save file
            file_description: Human-readable description (e.g., "35 USC Consolidated Patent Laws")
            timeout_seconds: Download timeout in seconds (default: 120)
            use_mb: Display progress in MB instead of KB (default: False)
            manual_instructions: Optional instructions if download fails

        Returns:
            True if download succeeded, False otherwise
        """
        # Validate URL scheme for security
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in ("http", "https"):
            print(
                f"Error: Invalid URL scheme '{parsed_url.scheme}'. Only HTTP and HTTPS are allowed.",
                file=sys.stderr,
            )
            return False

        print(f"\nDownloading {file_description} from {url}", file=sys.stderr)
        if timeout_seconds > 120:
            print("This may take several minutes depending on your connection...", file=sys.stderr)

        old_timeout = socket.getdefaulttimeout()

        try:
            socket.setdefaulttimeout(timeout_seconds)

            # Create progress callback
            divisor = (1024 * 1024) if use_mb else 1024
            unit = "MB" if use_mb else "KB"

            _last_percent = [-1]  # mutable container for closure

            def progress_hook(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = min(100, (downloaded * 100) // total_size)
                    if percent == _last_percent[0]:
                        return  # Only print when percentage changes
                    _last_percent[0] = percent
                    downloaded_size = downloaded / divisor
                    total_size_converted = total_size / divisor
                    print(
                        f"\rProgress: {percent}% ({downloaded_size:.1f}{unit} / {total_size_converted:.1f}{unit})",
                        end="",
                        file=sys.stderr,
                    )

            try:
                # Stream the download manually (rather than urlretrieve) so we can
                # pass an explicit SSL context with a certifi CA bundle — required
                # on python.org's macOS Python, which ships no system CA bundle.
                ssl_context = _create_ssl_context()
                request = urllib.request.Request(url)
                block_size = 8192
                with urllib.request.urlopen(
                    request, timeout=timeout_seconds, context=ssl_context
                ) as response:
                    total_size = int(response.headers.get("Content-Length", 0) or 0)
                    block_num = 0
                    downloaded = 0
                    progress_hook(block_num, block_size, total_size)
                    with dest_path.open("wb") as out_file:
                        while True:
                            chunk = response.read(block_size)
                            if not chunk:
                                break
                            out_file.write(chunk)
                            downloaded += len(chunk)
                            block_num += 1
                            progress_hook(block_num, block_size, total_size)
                    # Mirror urlretrieve's ContentTooShortError: a stream that ends
                    # before the advertised Content-Length is a truncated download,
                    # not a success. Raising routes to the cleanup path below.
                    if total_size and downloaded < total_size:
                        raise OSError(f"Download truncated: got {downloaded} of {total_size} bytes")
                print(f"\n[OK] {file_description} download complete", file=sys.stderr)
                return True
            finally:
                socket.setdefaulttimeout(old_timeout)

        except socket.timeout:
            timeout_minutes = timeout_seconds // 60
            print(
                f"\n[X] Download timed out after {timeout_minutes} minute{'s' if timeout_minutes != 1 else ''}",
                file=sys.stderr,
            )
            print(
                "Your connection may be too slow or the server is not responding", file=sys.stderr
            )
            if dest_path.exists():
                dest_path.unlink()
            return False

        except Exception as e:
            print(f"\n[X] Download failed: {e}", file=sys.stderr)
            if dest_path.exists():
                dest_path.unlink()
            if manual_instructions:
                print("\nManual download instructions:", file=sys.stderr)
                print(manual_instructions, file=sys.stderr)
            else:
                print(f"\nManual download: Visit {url}", file=sys.stderr)
            print(f"Save as: {dest_path.absolute()}", file=sys.stderr)
            return False
