import os
import subprocess

# Standard Ubuntu/Debian paths for SmokePing CGI
CGI_PATHS = [
    "/usr/lib/cgi-bin/smokeping.cgi",
    "/usr/share/smokeping/smokeping.cgi",
]


def find_cgi():
    """Find the SmokePing CGI script on disk."""
    custom = os.environ.get("SPM_CGI_PATH")
    if custom and os.path.isfile(custom):
        return custom
    for path in CGI_PATHS:
        if os.path.isfile(path):
            return path
    return None


def call_cgi(query_string="", script_name="/smokeping/smokeping.cgi"):
    """Execute the SmokePing CGI and return (content_type, body).

    CGI scripts communicate via environment variables and stdout.
    We set up the required CGI env vars, run the script, and parse
    the response headers from its output.
    """
    cgi_path = find_cgi()
    if not cgi_path:
        return "text/plain", b"SmokePing CGI not found. Set SPM_CGI_PATH in your env file."

    env = os.environ.copy()
    env.update({
        "REQUEST_METHOD": "GET",
        "QUERY_STRING": query_string,
        "SCRIPT_NAME": script_name,
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "5000",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "HTTP_HOST": "localhost",
        "GATEWAY_INTERFACE": "CGI/1.1",
    })

    try:
        result = subprocess.run(
            [cgi_path],
            env=env,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "text/plain", b"SmokePing CGI not executable or missing interpreter."
    except subprocess.TimeoutExpired:
        return "text/plain", b"SmokePing CGI timed out."

    output = result.stdout
    if not output:
        stderr = result.stderr.decode("utf-8", errors="replace")
        return "text/plain", f"CGI returned no output. stderr: {stderr}".encode()

    # CGI output: headers\r\n\r\nbody (or headers\n\nbody)
    # Split headers from body
    for sep in [b"\r\n\r\n", b"\n\n"]:
        if sep in output:
            header_block, body = output.split(sep, 1)
            break
    else:
        # No headers found, treat entire output as body
        return "text/html", output

    # Parse content-type from CGI headers
    content_type = "text/html"
    for line in header_block.split(b"\n"):
        line = line.strip()
        if line.lower().startswith(b"content-type:"):
            content_type = line.split(b":", 1)[1].strip().decode("utf-8", errors="replace")
            break

    return content_type, body
