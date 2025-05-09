import os
import json
import time
import network
import socket
import binascii
import hashlib
from machine import Pin

# Configuration
WIFI_SSID = "GEARBOX EUROPLACER"
WIFI_PASS = "Euro@2023"
SERVER_PORT = 80
API_USERNAME = "admin"
API_PASSWORD = "admin"
LED = Pin("LED", Pin.OUT)  # Onboard LED for status indication

# Directory structure
FIRMWARE_DIR = "/firmware"
METADATA_FILE = "/firmware/metadata.json"

# Ensure firmware directory exists
def setup_storage():
    try:
        os.mkdir(FIRMWARE_DIR)
        print(f"Created firmware directory at {FIRMWARE_DIR}")
    except OSError:
        pass

    try:
        os.stat(METADATA_FILE)
    except OSError:
        print(f"Creating new metadata file at {METADATA_FILE}")
        with open(METADATA_FILE, 'w') as f:
            json.dump({"firmware_entries": [], "latest_version": "0.0.0"}, f)

# Connect to WiFi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(f"Connecting to WiFi network: {WIFI_SSID}")
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASS)
        max_wait = 20
        while max_wait > 0 and not wlan.isconnected():
            time.sleep(1)
            max_wait -= 1
            print("Waiting for connection...")
            LED.toggle()

    if wlan.isconnected():
        LED.value(1)
        ip = wlan.ifconfig()[0]
        print(f"Connected! IP address: {ip}")
        return ip
    else:
        LED.value(0)
        print("Connection failed!")
        return None

# Parse request
def parse_request(request):
    lines = request.split(b'\r\n')
    if not lines:
        return None, None, None, None

    request_line = lines[0].decode()
    parts = request_line.split()
    if len(parts) < 3:
        return None, None, None, None

    method, path, _ = parts
    headers = {}
    for line in lines[1:]:
        if b":" in line:
            key, value = line.decode().split(":", 1)
            headers[key.strip().lower()] = value.strip()
        if line == b"":
            break

    query_params = {}
    if '?' in path:
        path, query_string = path.split('?', 1)
        for param in query_string.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                query_params[key] = value

    return method, path, headers, query_params

# Basic Auth check
def check_auth(headers):
    if 'authorization' in headers:
        auth = headers['authorization']
        if auth.startswith('Basic '):
            import ubinascii
            try:
                decoded = ubinascii.a2b_base64(auth[6:]).decode()
                username, password = decoded.split(':', 1)
                return username == API_USERNAME and password == API_PASSWORD
            except:
                pass
    return False

# HTTP Status
HTTP_200 = b"HTTP/1.1 200 OK\r\n"
HTTP_401 = b"HTTP/1.1 401 Unauthorized\r\n"
HTTP_404 = b"HTTP/1.1 404 Not Found\r\n"
HTTP_500 = b"HTTP/1.1 500 Internal Server Error\r\n"

# Handle requests
def handle_request(client_socket):
    try:
        request = client_socket.recv(1024)
        method, path, headers, query_params = parse_request(request)
        if not method:
            client_socket.send(HTTP_404)
            client_socket.close()
            return

        print(f"Request: {method} {path}")

        if not (path.startswith('/download/') or path == '/firmware/metadata.json') and not check_auth(headers):
            client_socket.send(HTTP_401)
            client_socket.send(b"WWW-Authenticate: Basic realm=\"FOTA Server\"\r\n")
            client_socket.send(b"Content-Type: text/plain\r\n\r\nAuthentication required")
            client_socket.close()
            return

        if path == '/':
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            response = HTTP_200
            response += b"Content-Type: text/html\r\n\r\n"
            response += b"<html><body><h1>FOTA Server</h1>"
            response += f"<p>Latest version: {metadata['latest_version']}</p>".encode()
            response += f"<p>Available firmware: {len(metadata['firmware_entries'])}</p>".encode()
            response += b"</body></html>"
            #client_socket.send(response)
            response += b"<h2>Available Firmware Files:</h2><ul>"
            
            for entry in metadata['firmware_entries']:
                response += f"<li>{entry['device_type']} v{entry['version']} - {entry['description']} ({entry['size']} bytes)</li>".encode()
            
            response += b"</ul></body></html>"
            client_socket.send(response)

        elif path == '/api/firmware/list':
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            response = HTTP_200
            response += b"Content-Type: application/json\r\n\r\n"
            response += json.dumps(metadata).encode()
            client_socket.send(response)

        elif path == '/firmware/metadata.json':
            try:
                with open(METADATA_FILE, 'r') as f:
                    data = f.read()
                response = HTTP_200
                response += b"Content-Type: application/json\r\n\r\n"
                response += data.encode() if isinstance(data, str) else data
                client_socket.send(response)
            except Exception as e:
                print(f"Error serving metadata: {e}")
                response = HTTP_500
                response += b"Content-Type: text/plain\r\n\r\nInternal Server Error"
                client_socket.send(response)

        elif path.startswith('/download/'):
            filename = path[10:]
            filepath = f"{FIRMWARE_DIR}/{filename}"
            try:
                size = os.stat(filepath)[6]
                response = HTTP_200
                response += f"Content-Length: {size}\r\n".encode()
                response += b"Content-Type: application/octet-stream\r\n\r\n"
                client_socket.send(response)
                with open(filepath, 'rb') as f:
                    chunk = f.read(1024)
                    while chunk:
                        client_socket.send(chunk)
                        chunk = f.read(1024)
            except:
                response = HTTP_404
                response += b"Content-Type: text/plain\r\n\r\nFile not found"
                client_socket.send(response)

        else:
            response = HTTP_404
            response += b"Content-Type: text/plain\r\n\r\nEndpoint not found"
            client_socket.send(response)

    except Exception as e:
        print(f"Error: {e}")
        response = HTTP_500
        response += b"Content-Type: text/plain\r\n\r\nInternal error"
        client_socket.send(response)
    finally:
        client_socket.close()

# Main server loop
def run_server(ip):
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', SERVER_PORT))
    sock.listen(5)
    print(f"FOTA server running on http://{ip}:{SERVER_PORT}")
    while True:
        client, addr = sock.accept()
        print(f"Client connected: {addr}")
        LED.toggle()
        handle_request(client)
        LED.value(1)

# Start app
def main():
    setup_storage()
    ip = connect_wifi()
    if ip:
        run_server(ip)
    else:
        print("Failed to connect to WiFi")

if __name__ == "__main__":
    main()
