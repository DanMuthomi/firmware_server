import os
import json
import time
import gc
import struct

# Configuration
FIRMWARE_DIR = "/firmware"
METADATA_FILE = "/firmware/metadata.json"

# ================================
# STM32-Compatible CRC32 Function
# ================================
def calculate_stm32_crc32(filename):
    """
    Compute CRC32 exactly matching STM32 hardware implementation:
    - Polynomial: 0x04C11DB7
    - Initial: 0xFFFFFFFF
    - Processes 32-bit words in little-endian format
    - No final inversion (unlike standard CRC32)
    """
    crc = 0xFFFFFFFF
    chunk_size = 256  # Memory efficient for MicroPython
    
    try:
        with open(filename, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                # Process chunk in 32-bit words (like STM32 HAL_CRC_Calculate)
                i = 0
                while i + 3 < len(chunk):
                    # Extract 4 bytes and convert to little-endian 32-bit word
                    word = struct.unpack('<I', chunk[i:i+4])[0]
                    crc ^= word
                    
                    # Process 32 bits
                    for _ in range(32):
                        if crc & 0x80000000:
                            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
                        else:
                            crc = (crc << 1) & 0xFFFFFFFF
                    i += 4
                
                # Handle remaining bytes (like STM32 HAL_CRC_Accumulate for partial words)
                if i < len(chunk):
                    remaining = chunk[i:]
                    # Pad to 4 bytes with zeros (like STM32 does)
                    padded = remaining + b'\x00' * (4 - len(remaining))
                    word = struct.unpack('<I', padded)[0]
                    crc ^= word
                    
                    # Process 32 bits
                    for _ in range(32):
                        if crc & 0x80000000:
                            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
                        else:
                            crc = (crc << 1) & 0xFFFFFFFF
                
                gc.collect()  # Important for MicroPython memory management
        
        return '%08x' % crc
        
    except Exception as e:
        print(f"❌ CRC32 calculation error: {e}")
        return None

# ============================
# Semantic Version Comparison
# ============================
def compare_versions(version1, version2):
    v1 = [int(x) for x in version1.split(".")]
    v2 = [int(x) for x in version2.split(".")]
    while len(v1) < len(v2): v1.append(0)
    while len(v2) < len(v1): v2.append(0)
    return (v1 > v2) - (v1 < v2)

# ============================
# Main Upload Firmware Script
# ============================
def upload_firmware(firmware_file, version, device_type, description=""):
    print(f"📦 Uploading firmware: {firmware_file} for {device_type} v{version}...")

    # Ensure firmware directory exists
    try:
        os.mkdir(FIRMWARE_DIR)
        print(f"📁 Created firmware directory: {FIRMWARE_DIR}")
    except OSError:
        pass  # Already exists

    # Ensure metadata file exists or create default
    try:
        os.stat(METADATA_FILE)
    except OSError:
        print("📄 Metadata not found. Creating default metadata.json...")
        with open(METADATA_FILE, 'w') as f:
            json.dump({"firmware_entries": [], "latest_version": "0.0.0"}, f)

    # Prepare filename and paths
    extension = firmware_file.split('.')[-1]
    base_filename = f"{device_type}-v{version}.{extension}"
    dest_path = f"{FIRMWARE_DIR}/{base_filename}"

    # Copy firmware in chunks (memory safe)
    print("📤 Copying firmware...")
    try:
        total_bytes = 0
        with open(firmware_file, 'rb') as src, open(dest_path, 'wb') as dst:
            while True:
                chunk = src.read(1024)
                if not chunk:
                    break
                dst.write(chunk)
                total_bytes += len(chunk)
        print(f"✅ Copied {total_bytes} bytes")
    except Exception as e:
        print(f"❌ Error copying firmware: {e}")
        return False

    # Get file size and CRC
    try:
        file_size = os.stat(dest_path)[6]
        checksum = calculate_stm32_crc32(dest_path)
        if checksum is None:
            print("❌ Failed to calculate CRC")
            return False
        print(f"🧮 STM32-Compatible CRC32: {checksum}")
    except Exception as e:
        print(f"❌ Error gathering info: {e}")
        return False

    # Load metadata
    try:
        with open(METADATA_FILE, 'r') as f:
            metadata = json.load(f)
    except:
        metadata = {"firmware_entries": [], "latest_version": "0.0.0"}

    # Create or update firmware entry
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
            print("🔄 Updated existing entry")
            break

    if not updated:
        metadata["firmware_entries"].append(entry)
        print("➕ Added new entry")

    # Update latest version if needed
    if compare_versions(version, metadata.get("latest_version", "0.0.0")) > 0:
        metadata["latest_version"] = version
        print(f"⬆️ Updated latest_version to {version}")

    # Save metadata
    try:
        with open(METADATA_FILE, 'w') as f:
            json.dump(metadata, f)
        print("✅ Metadata updated successfully")
    except Exception as e:
        print(f"❌ Failed to save metadata: {e}")
        return False

    print("🎉 Firmware upload complete!")
    return True

# ============================
# Test function to verify CRC calculation
# ============================
def test_crc_calculation():
    """Test function to verify our CRC matches STM32 output"""
    # Create a small test file for verification
    test_data = b"Hello STM32 CRC test!"
    with open("test.bin", "wb") as f:
        f.write(test_data)
    
    crc = calculate_stm32_crc32("test.bin")
    print(f"Test CRC for '{test_data.decode()}': {crc}")
    
    # Clean up
    try:
        os.remove("test.bin")
    except:
        pass

# ============================
# Run if main
# ============================
if __name__ == "__main__":
    # Uncomment to test CRC calculation first
    # test_crc_calculation()
    
    upload_firmware("RHEA_V3.bin", "3.1.0", "V3_001", "Second release device no:1")
