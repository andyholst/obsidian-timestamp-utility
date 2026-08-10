#!/usr/bin/env python3
"""
PTY Runner for nerdctl compose run on macOS.

This script creates a pseudo-terminal so that `nerdctl compose run --interactive --tty`
works correctly when stdout is NOT a tty (CI, piped output, etc.).

Usage: pty_runner.py "command" [timeout_seconds]
"""

import os
import sys
import pty
import select
import signal
import subprocess
import time


def run_with_pty(command, timeout=300):
    """Run a command with a pseudo-terminal."""
    pid, fd = pty.openpty()

    # Set terminal size (needed by some programs)
    import struct
    import fcntl
    import termios

    winsize = struct.pack('HHHH', 24, 80, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    # Start the command with a shell that won't interpret quotes
    proc = subprocess.Popen(
        ['/bin/sh', '-c', command],
        stdout=fd,
        stderr=fd,
        stdin=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )

    # Close the master side in the child process
    os.close(fd)

    # Read output with timeout
    start_time = time.time()
    output = b''

    while True:
        # Check if process is still running
        ret = proc.poll()
        if ret is not None:
            break

        # Check timeout
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"ERROR: Command timed out after {timeout} seconds", file=sys.stderr)
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            sys.exit(124)

        # Wait for output with 0.1s timeout
        if proc.stdout and proc.stderr:
            ready, _, _ = select.select([sys.stdout], [], [], 0.1)
            if ready:
                try:
                    data = os.read(proc.stdout.fileno(), 4096)
                    if data:
                        output += data
                        sys.stdout.write(data.decode('utf-8', errors='replace'))
                        sys.stdout.flush()
                    else:
                        # EOF
                        break
                except OSError:
                    break

    # Wait for process to complete
    proc.wait()
    return proc.returncode


if __name__ == '__main__':
    timeout = 300

    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Usage:")
        print("  pty_runner.py \"command\" [timeout_seconds]")
        sys.exit(0)

    # Command is the first argument
    if len(sys.argv) < 2:
        print("Usage: pty_runner.py \"command\" [timeout_seconds]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    # Optional timeout as second argument
    if len(sys.argv) > 2:
        try:
            timeout = int(sys.argv[2])
        except ValueError:
            pass

    exit_code = run_with_pty(command, timeout)
    sys.exit(exit_code)