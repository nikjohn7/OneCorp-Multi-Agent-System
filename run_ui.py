#!/usr/bin/env python3
"""Run the OneCorp MAS visual dashboard.

Usage:
    python run_ui.py          # Start on default port 5000
    python run_ui.py --port 8080  # Start on custom port
"""

import argparse
import webbrowser
import threading
import time


def main():
    parser = argparse.ArgumentParser(description="OneCorp MAS Visual Dashboard")
    parser.add_argument("--port", type=int, default=5000, help="Port to run on (default: 5000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    from src.ui.app import run_server

    # Open browser after a short delay
    if not args.no_browser:
        def open_browser():
            time.sleep(1.5)
            url = f"http://localhost:{args.port}"
            print(f"\nOpening browser at {url}")
            webbrowser.open(url)

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           OneCorp Multi-Agent System - Visual Dashboard              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Dashboard URL: http://localhost:{args.port:<5}                            ║
║                                                                      ║
║  Instructions:                                                       ║
║  1. Click "Start Demo" to begin the workflow                         ║
║  2. Watch agents process the contract in real-time                   ║
║  3. After completion, click "Test SLA" for overdue scenario          ║
║                                                                      ║
║  Press Ctrl+C to stop the server                                     ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    run_server(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
