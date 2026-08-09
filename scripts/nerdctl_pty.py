#!/usr/bin/env python3
"""
Run a command with a pseudo-terminal for nerdctl compose run.

Usage: nerdctl_pty.py "command" [timeout_seconds]
       nerdctl_pty.py --file <path> [timeout_seconds]
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
    # Create PTY pair
    master_fd, slave_fd = pty.openpty()

    # Set terminal size
    import struct
    import fcntl
    import termios
    winsize = struct.pack('HHHH', 24, 80, 0, 0)
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

    # Fork and exec the command in a new session
    pid = os.fork()
    if pid == 0:
        # Child process
        os.setsid()
        os.dup2(slave_fd, 0)  # stdin
        os.dup2(slave_fd, 1)  # stdout
        os.dup2(slave_fd, 2)  # stderr
        os.close(master_fd)
        os.close(slave_fd)

        # Execute the command
        os.execvp('/bin/sh', ['/bin/sh', '-c', command])
    else:
        # Parent process - read from master
        os.close(slave_fd)  # Close slave in parent

        start_time = time.time()
        output = b''

        while True:
            ret = os.waitpid(pid, os.WNOHANG)
            if ret != (0, 0):
                break

            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(f"ERROR: Command timed out after {timeout} seconds", file=sys.stderr)
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
                sys.exit(124)

            # Wait for data with 0.1s timeout
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if ready:
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        output += data
                        sys.stdout.write(data.decode('utf-8', errors='replace'))
                        sys.stdout.flush()
                    else:
                        # EOF - close master and wait for process
                        os.close(master_fd)
                        break
                except OSError:
                    # File descriptor closed or error
                    break

        # Wait for process to complete if not already done
        try:
            pid, status = os.waitpid(pid, 0)
            exit_code = os.WEXITSTATUS(status)
        except ChildProcessError:
            exit_code = 1

        return exit_code


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  nerdctl_pty.py \"command\" [timeout_seconds]", file=sys.stderr)
        print("  nerdctl_pty.py --file <path> [timeout_seconds]", file=sys.stderr)
        sys.exit(1)

    # Check if we're reading from a file
    if sys.argv[1] == '--file':
        if len(sys.argv) < 3:
            print("Error: --file requires a path argument", file=sys.stderr)
            sys.exit(1)
        filepath = sys.argv[2]
        with open(filepath, 'r') as f:
            command = f.read().strip()
        timeout = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.environ.get('NERDCTL_PTY_TIMEOUT', '300'))
    else:
        # Command is the first argument
        command = sys.argv[1]
        timeout = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get('NERDCTL_PTY_TIMEOUT', '300'))

    exit_code = run_with_pty(command, timeout)
    sys.exit(exit_code)