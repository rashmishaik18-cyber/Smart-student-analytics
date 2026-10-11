"""
run.py  -  one command to regenerate data, rebuild the unified student view
and open the dashboard.

    python run.py            # generate data + run pipeline + open dashboard
    python run.py --serve    # same, but serve over http://localhost:8000
    python run.py --skip-generate   # reuse existing data/raw/*.csv (e.g. your own files)
"""
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent


def step(title, script):
    print(f"\n=== {title} ===")
    subprocess.run([sys.executable, str(ROOT / script)], check=True)


if __name__ == "__main__":
    if "--skip-generate" not in sys.argv:
        step("1/2  Generating synthetic raw data", "generate_data.py")
    step("2/2  Integrating, scoring and exporting", "pipeline.py")
    page = ROOT / "dashboard" / "index.html"
    if "--serve" in sys.argv:
        import functools, http.server, socketserver
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "dashboard"))
        with socketserver.TCPServer(("", 8000), handler) as httpd:
            print("\nDashboard: http://localhost:8000   (Ctrl+C to stop)")
            webbrowser.open("http://localhost:8000")
            httpd.serve_forever()
    else:
        print(f"\nOpening {page}")
        webbrowser.open(page.as_uri())
