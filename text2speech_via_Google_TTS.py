import subprocess
import sys
import os

def install_package(package):
    """Silently install a package if not already installed"""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])

# Check and install required packages
required_packages = {
    'gtts': 'gTTS'
}

for import_name, package_name in required_packages.items():
    try:
        __import__(import_name)
    except ImportError:
        print(f"Installing {package_name}...")
        install_package(package_name)

from gtts import gTTS

# Check if file path is provided as command-line argument
if len(sys.argv) < 2:
    print("Usage: python text2speech_via_Google_TTS.py <path_to_txt_file>")
    sys.exit(1)

# Get file path from command-line argument
file_path = sys.argv[1]

# Check if file exists
if not os.path.exists(file_path):
    print(f"Error: File '{file_path}' not found.")
    sys.exit(1)

# Check if file is a .txt file
if not file_path.lower().endswith('.txt'):
    print("Error: File must be a .txt file.")
    sys.exit(1)

# Read text from file
print(f"Reading text from '{file_path}'...")
try:
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
except Exception as e:
    print(f"Error reading text file: {e}")
    sys.exit(1)

# Print text length to verify reading
print(f"Text length: {len(text)} characters")

# Generate output filename based on input filename
output_file = os.path.splitext(os.path.basename(file_path))[0] + ".mp3"

# Convert text to .mp3
print(f"Converting text to speech...")
try:
    tts = gTTS(text, lang='en')
    tts.save(output_file)
    print(f"Audio file saved as '{output_file}'")
except Exception as e:
    print(f"Error converting to speech: {e}")
    sys.exit(1)
