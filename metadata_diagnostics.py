# metadata_diagnostics.py - Run this to check metadata status and fix issues

import os
import json

FIRMWARE_DIR = "/firmware"
METADATA_FILE = "/firmware/metadata.json"

def check_metadata():
    # First check if the firmware directory exists
    try:
        dirs = os.listdir("/")
        print(f"Root directory contents: {dirs}")
        
        if "firmware" in dirs:
            print("✓ Firmware directory exists")
            
            # Check contents of firmware directory
            firmware_contents = os.listdir(FIRMWARE_DIR)
            print(f"Firmware directory contents: {firmware_contents}")
            
            # Check if metadata file exists
            if "metadata.json" in firmware_contents:
                print("✓ Metadata file exists")
                
                # Try to read and display metadata
                try:
                    with open(METADATA_FILE, 'r') as f:
                        metadata = json.load(f)
                        print(f"Current metadata content: {metadata}")
                    
                    # Check if we can write to the metadata file
                    print("Testing metadata file write access...")
                    try:
                        with open(METADATA_FILE, 'w') as f:
                            metadata["test_flag"] = True
                            json.dump(metadata, f)
                        
                        # Read it back to confirm changes
                        with open(METADATA_FILE, 'r') as f:
                            updated_metadata = json.load(f)
                        
                        if "test_flag" in updated_metadata and updated_metadata["test_flag"] == True:
                            print("✓ Successfully wrote to metadata file")
                            
                            # Remove test flag
                            with open(METADATA_FILE, 'w') as f:
                                metadata.pop("test_flag", None)
                                json.dump(metadata, f)
                        else:
                            print("✗ Failed to update metadata file")
                    except Exception as e:
                        print(f"✗ Error writing to metadata file: {e}")
                except Exception as e:
                    print(f"✗ Error reading metadata file: {e}")
            else:
                print("✗ Metadata file does not exist")
                print("Creating metadata file...")
                try:
                    with open(METADATA_FILE, 'w') as f:
                        json.dump({
                            "firmware_entries": [],
                            "latest_version": "0.0.0"
                        }, f)
                    print("✓ Created metadata file")
                except Exception as e:
                    print(f"✗ Error creating metadata file: {e}")
        else:
            print("✗ Firmware directory does not exist")
            print("Creating firmware directory...")
            try:
                os.mkdir(FIRMWARE_DIR)
                print("✓ Created firmware directory")
                
                # Create metadata file
                with open(METADATA_FILE, 'w') as f:
                    json.dump({
                        "firmware_entries": [],
                        "latest_version": "0.0.0"
                    }, f)
                print("✓ Created metadata file")
            except Exception as e:
                print(f"✗ Error creating firmware directory: {e}")
    except Exception as e:
        print(f"✗ Error checking root directory: {e}")

# Run the diagnostic check
check_metadata()