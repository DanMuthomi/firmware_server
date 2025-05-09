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
    except OSError:
        # Directory already exists
        pass
    
    # Create metadata file if it doesn't exist
    if METADATA_FILE not in os.listdir(FIRMWARE_DIR):
        with open(METADATA_FILE, 'w') as f:
            json.dump({
                "firmware_entries": [],
                "latest_version": "0.0.0"
            }, f)

# Connect to WiFi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    print(f"Connecting to WiFi network: {WIFI_SSID}")
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASS)
        # Wait for connection with timeout
        max_wait = 20
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print("Waiting for connection...")
            time.sleep(1)
            LED.toggle()  # Blink LED while connecting

    if wlan.isconnected():
        LED.value(1)  # LED on when connected
        ip = wlan.ifconfig()[0]
        print(f"Connected! IP address: {ip}")
        return ip
    else:
        LED.value(0)  # LED off if connection failed
        print("Connection failed!")
        return None

# Calculate MD5 hash of a file
def calculate_md5(filename):
    with open(filename, 'rb') as f:
        file_hash = hashlib.md5()
        chunk = f.read(1024)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(1024)
    return binascii.hexlify(file_hash.digest()).decode()

# Add new firmware to the repository
def add_firmware(filename, version, device_type, description=""):
    # Copy file to firmware directory with version in filename
    base_name = os.path.basename(filename)
    extension = base_name.split('.')[-1]
    new_filename = f"{FIRMWARE_DIR}/{device_type}-v{version}.{extension}"
    
    # Read source file
    with open(filename, 'rb') as src:
        data = src.read()
    
    # Write to destination
    with open(new_filename, 'wb') as dst:
        dst.write(data)
    
    # Calculate MD5 hash
    md5_hash = calculate_md5(new_filename)
    file_size = os.stat(new_filename)[6]  # Get file size
    
    # Update metadata
    with open(METADATA_FILE, 'r') as f:
        metadata = json.load(f)
    
    # Add new firmware entry
    firmware_entry = {
        "version": version,
        "device_type": device_type,
        "filename": os.path.basename(new_filename),
        "size": file_size,
        "md5": md5_hash,
        "description": description,
        "upload_date": time.time()
    }
    
    # Check if this version already exists
    for i, entry in enumerate(metadata["firmware_entries"]):
        if entry["version"] == version and entry["device_type"] == device_type:
            # Replace existing entry
            metadata["firmware_entries"][i] = firmware_entry
            break
    else:
        # Add new entry
        metadata["firmware_entries"].append(firmware_entry)
    
    # Update latest version if newer
    from pkg_resources import parse_version
    if parse_version(version) > parse_version(metadata["latest_version"]):
        metadata["latest_version"] = version
    
    # Write updated metadata
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f)
    
    return True

# Parse HTTP request
def parse_request(request):
    # Split request into lines
    lines = request.split(b'\r\n')
    if not lines:
        return None, None, None, None
    
    # Parse request line
    request_line = lines[0].decode()
    parts = request_line.split()
    if len(parts) < 3:
        return None, None, None, None
    
    method, path, _ = parts
    
    # Parse headers
    headers = {}
    for i in range(1, len(lines)):
        line = lines[i].decode()
        if not line:
            break
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip().lower()] = value.strip()
    
    # Parse query parameters
    query_params = {}
    if '?' in path:
        path, query_string = path.split('?', 1)
        for param in query_string.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                query_params[key] = value
    
    return method, path, headers, query_params

# Check authentication
def check_auth(headers):
    # Extremely basic auth - for production, use a more secure method
    if 'authorization' in headers:
        auth = headers['authorization']
        if auth.startswith('Basic '):
            import ubinascii
            try:
                decoded = ubinascii.a2b_base64(auth[6:]).decode()
                username, password = decoded.split(':', 1)
                if username == API_USERNAME and password == API_PASSWORD:
                    return True
            except:
                pass
    return False

# HTTP status codes
HTTP_200 = b"HTTP/1.1 200 OK\r\n"
HTTP_401 = b"HTTP/1.1 401 Unauthorized\r\n"
HTTP_404 = b"HTTP/1.1 404 Not Found\r\n"
HTTP_500 = b"HTTP/1.1 500 Internal Server Error\r\n"

# Handle client request
def handle_request(client_socket):
    try:
        # Receive client request
        request = client_socket.recv(1024)
        
        # Parse request
        method, path, headers, query_params = parse_request(request)
        if not method:
            client_socket.send(HTTP_400)
            client_socket.close()
            return
        
        print(f"Request: {method} {path}")
        
        # Check authentication for all requests except firmware downloads
        if not path.startswith('/download/') and not check_auth(headers):
            client_socket.send(HTTP_401)
            client_socket.send(b"WWW-Authenticate: Basic realm=\"FOTA Server\"\r\n")
            client_socket.send(b"Content-Type: text/plain\r\n\r\n")
            client_socket.send(b"Authentication required")
            client_socket.close()
            return
            
        # API endpoints
        if path == '/':
            # Root endpoint - basic status page
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            
            response = HTTP_200
            response += b"Content-Type: text/html\r\n\r\n"
            response += b"<html><body><h1>FOTA Server</h1>"
            response += f"<p>Latest version: {metadata['latest_version']}</p>".encode()
            response += f"<p>Available firmware: {len(metadata['firmware_entries'])}</p>".encode()
            response += b"<h2>Available Firmware Files:</h2><ul>"
            
            for entry in metadata['firmware_entries']:
                response += f"<li>{entry['device_type']} v{entry['version']} - {entry['description']} ({entry['size']} bytes)</li>".encode()
            
            response += b"</ul></body></html>"
            client_socket.send(response)
            
        elif path == '/api/firmware/list':
            # List all available firmware
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            
            response = HTTP_200
            response += b"Content-Type: application/json\r\n\r\n"
            response += json.dumps(metadata).encode()
            client_socket.send(response)
            
        elif path == '/api/firmware/latest':
            # Get latest firmware for device type
            device_type = query_params.get('device_type', '')
            
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            
            # Find latest version for this device type
            latest_version = "0.0.0"
            latest_entry = None
            
            for entry in metadata['firmware_entries']:
                if entry['device_type'] == device_type:
                    if parse_version(entry['version']) > parse_version(latest_version):
                        latest_version = entry['version']
                        latest_entry = entry
            
            if latest_entry:
                response = HTTP_200
                response += b"Content-Type: application/json\r\n\r\n"
                response += json.dumps(latest_entry).encode()
            else:
                response = HTTP_404
                response += b"Content-Type: application/json\r\n\r\n"
                response += json.dumps({"error": "No firmware found for specified device type"}).encode()
            
            client_socket.send(response)
            
        elif path.startswith('/download/'):
            # Download firmware file
            filename = path[10:]  # Remove '/download/' prefix
            filepath = f"{FIRMWARE_DIR}/{filename}"
            
            try:
                file_size = os.stat(filepath)[6]
                
                response = HTTP_200
                response += f"Content-Type: application/octet-stream\r\n".encode()
                response += f"Content-Length: {file_size}\r\n".encode()
                response += f"Content-Disposition: attachment; filename=\"{filename}\"\r\n\r\n".encode()
                client_socket.send(response)
                
                # Send file in chunks
                with open(filepath, 'rb') as f:
                    chunk = f.read(1024)
                    while chunk:
                        client_socket.send(chunk)
                        chunk = f.read(1024)
            except OSError:
                response = HTTP_404
                response += b"Content-Type: text/plain\r\n\r\n"
                response += b"File not found"
                client_socket.send(response)
        
        else:
            # 404 Not Found
            response = HTTP_404
            response += b"Content-Type: text/plain\r\n\r\n"
            response += b"Endpoint not found"
            client_socket.send(response)
    
    except Exception as e:
        # 500 Internal Server Error
        print(f"Error handling request: {e}")
        try:
            response = HTTP_500
            response += b"Content-Type: text/plain\r\n\r\n"
            response += f"Internal server error: {str(e)}".encode()
            client_socket.send(response)
        except:
            pass
    
    finally:
        client_socket.close()

# Main server loop
def run_server(ip):
    # Create socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind(('0.0.0.0', SERVER_PORT))
        server_socket.listen(5)
        print(f"FOTA server running on http://{ip}:{SERVER_PORT}")
        
        while True:
            try:
                client_socket, addr = server_socket.accept()
                print(f"Client connected from {addr[0]}:{addr[1]}")
                LED.toggle()  # Blink LED on connection
                handle_request(client_socket)
                LED.value(1)  # Turn LED back on
            except Exception as e:
                print(f"Error accepting connection: {e}")
    
    finally:
        server_socket.close()

# Helper function to compare version strings
def parse_version(version_string):
    return tuple(map(int, version_string.split('.')))

# Main application
def main():
    # Initialize storage
    setup_storage()
    
    # Connect to WiFi
    ip = connect_wifi()
    if not ip:
        print("WiFi connection failed. Cannot start server.")
        return
    
    # Start FOTA server
    run_server(ip)

# Run the application
if __name__ == "__main__":
    main()