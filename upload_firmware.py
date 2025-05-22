import os
import json
import binascii
import time

# Configuration
FIRMWARE_DIR = "/firmware"
METADATA_FILE = "/firmware/metadata.json"

# Calculate CRC32 checksum of a file
def calculate_checksum(filename):
    with open(filename, 'rb') as f:
        checksum = 0
        while True:
            chunk = f.read(1024)
            if not chunk:
                break
            checksum = binascii.crc32(chunk, checksum)
    return '%08x' % (checksum & 0xFFFFFFFF)

# Compare semantic version strings
def compare_versions(version1, version2):
    v1 = [int(x) for x in version1.split(".")]
    v2 = [int(x) for x in version2.split(".")]
    while len(v1) < len(v2): v1.append(0)
    while len(v2) < len(v1): v2.append(0)
    return (v1 > v2) - (v1 < v2)

# Upload a new firmware file and update metadata
def upload_firmware(firmware_file, version, device_type, description=""):
    print(f"Uploading firmware: {firmware_file} for {device_type} v{version}...")

    # Ensure firmware directory exists
    try:
        os.mkdir(FIRMWARE_DIR)
        print(f"✓ Created firmware directory: {FIRMWARE_DIR}")
    except OSError:
        pass  # Already exists

    # Ensure metadata file exists
    try:
        os.stat(METADATA_FILE)
    except OSError:
        print("⚠️ Metadata file not found. Creating new one...")
        with open(METADATA_FILE, 'w') as f:
            json.dump({"firmware_entries": [], "latest_version": "0.0.0"}, f)

    # Define destination path
    extension = firmware_file.split('.')[-1]
    base_filename = f"{device_type}-v{version}.{extension}"
    dest_path = f"{FIRMWARE_DIR}/{base_filename}"

    # Copy firmware in chunks
    try:
        with open(firmware_file, 'rb') as src, open(dest_path, 'wb') as dst:
            while True:
                chunk = src.read(1024)
                if not chunk:
                    break
                dst.write(chunk)
    except Exception as e:
        print(f"❌ Error copying firmware: {e}")
        return False

    # Gather file info
    file_size = os.stat(dest_path)[6]
    checksum = calculate_checksum(dest_path)

    # Load existing metadata
    try:
        with open(METADATA_FILE, 'r') as f:
            metadata = json.load(f)
    except Exception:
        metadata = {"firmware_entries": [], "latest_version": "0.0.0"}

    # Create or update entry
    entry = {
        "version": version,
        "device_type": device_type,
        "filename": base_filename,
        "size": file_size,
        "checksum": checksum,
        "description": description,
        "upload_date": time.time()
    }

    updated = False
    for i, e in enumerate(metadata["firmware_entries"]):
        if e["device_type"] == device_type and e["version"] == version:
            metadata["firmware_entries"][i] = entry
            updated = True
            print("🔄 Updated existing entry.")
            break

    if not updated:
        metadata["firmware_entries"].append(entry)
        print("➕ Added new entry to metadata.")

    # Update latest version
    if compare_versions(version, metadata.get("latest_version", "0.0.0")) > 0:
        metadata["latest_version"] = version
        print(f"⬆️ Updated latest_version to {version}")

    # Write back metadata
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f)

    print("✅ Firmware upload and metadata update complete.")
    return True

# Example usage
if __name__ == "__main__":
    upload_firmware("RHEA_V3.bin", "3.1.0", "V3_001", "Second release device no:1")
