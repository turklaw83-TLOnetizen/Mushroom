"""
Desktop Launcher for AllRise Beta Legal Intelligence Suite
Opens the Streamlit app in a native Windows window via PyWebView.
No browser chrome -- looks like a real desktop application.

Usage:  python launcher.py
"""
import subprocess
import sys
import os
import time
import socket
import webview

APP_TITLE = "AllRise Beta — Legal Intelligence Suite"
STREAMLIT_PORT = 8501
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"


def is_port_open(port, host="localhost", timeout=1.0):
    """Check if the Streamlit server is up."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


def start_streamlit():
    """Launch Streamlit in a background process."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(script_dir, "app.py")

    cmd = [
        sys.executable, "-m", "streamlit", "run", app_path,
        "--server.port", str(STREAMLIT_PORT),
        "--server.headless", "true",
        "--server.address", "localhost",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]

    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    process = subprocess.Popen(
        cmd,
        cwd=script_dir,
        startupinfo=startupinfo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process


def wait_for_server(timeout=45):
    """Wait until Streamlit is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(STREAMLIT_PORT):
            return True
        time.sleep(0.3)
    return False


def kill_process_tree(process):
    """Kill the Streamlit subprocess and all its children on Windows."""
    if sys.platform == "win32":
        subprocess.call(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main():
    already_running = is_port_open(STREAMLIT_PORT)

    process = None
    if not already_running:
        process = start_streamlit()
        print("Starting AllRise Beta server...")
        if not wait_for_server():
            print("ERROR: Server did not start within 45 seconds.")
            if process:
                kill_process_tree(process)
            sys.exit(1)
        print("Server ready.")

    window = webview.create_window(
        APP_TITLE,
        STREAMLIT_URL,
        width=1440,
        height=900,
        min_size=(1024, 680),
        confirm_close=True,
        text_select=True,
    )

    webview.start(debug=False)

    if process:
        print("Shutting down server...")
        kill_process_tree(process)
        print("Done.")


if __name__ == "__main__":
    main()
