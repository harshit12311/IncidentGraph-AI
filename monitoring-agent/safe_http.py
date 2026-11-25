import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit


def validate_public_url(url):
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        raise ValueError("Control characters are not allowed in URLs.")

    parsed = urlsplit(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are allowed.")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid website URL.")

    hostname = parsed.hostname.encode("idna").decode("ascii")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if not 1 <= port <= 65535:
        raise ValueError("Invalid port.")

    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            results = socket.getaddrinfo(
                hostname, port, type=socket.SOCK_STREAM
            )
        except socket.gaierror as error:
            raise ValueError("Website DNS lookup failed.") from error

        addresses = sorted(
            {
                ipaddress.ip_address(result[4][0])
                for result in results
            },
            key=lambda address: (address.version != 4, str(address)),
        )

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Website resolves to a non-public IP address.")

    return parsed, hostname, port, addresses


def safe_get(url, timeout=10, max_redirects=3):
    """Perform a GET using validated public IPs and safe redirects."""
    current_url = url

    for redirect_count in range(max_redirects + 1):
        parsed, hostname, port, addresses = validate_public_url(current_url)

        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        host_header = f"[{hostname}]" if ":" in hostname else hostname
        if port not in (80, 443):
            host_header += f":{port}"

        last_error = None
        response_received = False

        for address in addresses:
            raw_socket = None
            connection = None

            try:
                raw_socket = socket.create_connection(
                    (str(address), port), timeout=timeout
                )

                if parsed.scheme == "https":
                    context = ssl.create_default_context()
                    connection = context.wrap_socket(
                        raw_socket, server_hostname=hostname
                    )
                else:
                    connection = raw_socket

                request = (
                    f"GET {path} HTTP/1.1\r\n"
                    f"Host: {host_header}\r\n"
                    "User-Agent: IncidentGraph-AI-Monitor/1.0\r\n"
                    "Accept: */*\r\n"
                    "Connection: close\r\n\r\n"
                )

                connection.sendall(request.encode("ascii"))
                response = http.client.HTTPResponse(connection)
                response.begin()

                status_code = response.status
                location = response.getheader("Location")
                response.close()
                response_received = True
                break

            except (OSError, ssl.SSLError, http.client.HTTPException) as error:
                last_error = error

            finally:
                if connection is not None:
                    connection.close()
                elif raw_socket is not None:
                    raw_socket.close()

        if not response_received:
            raise ConnectionError(
                f"Could not connect to any validated public IP for {hostname}"
            ) from last_error

        if status_code not in (301, 302, 303, 307, 308):
            return status_code

        if not location:
            return status_code

        if redirect_count >= max_redirects:
            raise ValueError("Maximum redirect limit exceeded.")

        current_url = urljoin(current_url, location)

    raise ValueError("Maximum redirect limit exceeded.")