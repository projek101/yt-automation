#!/bin/bash
# install-deps.sh - Install system dependencies for CLIPPER

set -e

echo "Installing CLIPPER system dependencies..."

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

echo "Detected OS: $OS"

# Install common dependencies
echo "Installing common packages..."

if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ] || [ "$OS" = "linuxmint" ]; then
    sudo apt update
    sudo apt install -y \
        ffmpeg \
        git \
        curl \
        build-essential \
        cmake \
        pkg-config \
        libsndfile1 \
        python3-pip \
        python3-venv

elif [ "$OS" = "fedora" ]; then
    sudo dnf install -y \
        ffmpeg \
        git \
        curl \
        cmake \
        pkgconfig \
        libsndfile \
        python3-pip

elif [ "$OS" = "arch" ]; then
    sudo pacman -S --noconfirm \
        ffmpeg \
        git \
        curl \
        cmake \
        pkgconf \
        libsndfile \
        python-pip

else
    echo "Unsupported OS: $OS"
    echo "Please install dependencies manually:"
    echo "  - ffmpeg"
    echo "  - git"
    echo "  - curl"
    echo "  - build-essential/cmake"
    echo "  - libsndfile"
fi

# Install yt-dlp
echo "Installing yt-dlp..."
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp

# Verify installations
echo "Verifying installations..."
command -v ffmpeg >/dev/null 2>&1 || { echo "ERROR: ffmpeg not found"; exit 1; }
command -v yt-dlp >/dev/null 2>&1 || { echo "ERROR: yt-dlp not found"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "ERROR: git not found"; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "ERROR: curl not found"; exit 1; }

echo ""
echo "======================================"
echo "System dependencies installed!"
echo ""
echo "Next steps:"
echo "1. Create virtualenv:"
echo "   python3 -m venv ~/yt-env"
echo "   source ~/yt-env/bin/activate"
echo ""
echo "2. Install Python packages:"
echo "   pip install -r backend/requirements.txt"
echo ""
echo "3. (Optional) Install whisper.cpp for transcription:"
echo "   cd ~"
echo "   git clone https://github.com/ggerganov/whisper.cpp.git"
echo "   cd whisper.cpp && make -j4"
echo "   ./models/download-ggml-model.sh base.en"
echo ""
echo "4. (Optional) Install Ollama for script generation:"
echo "   curl -fsSL https://ollama.com/install.sh | sh"
echo "   ollama pull llama2"
echo ""
echo "5. Configure .env file:"
echo "   cp .env.example .env"
echo "   # Edit .env with your settings"
echo ""
echo "6. Run CLIPPER:"
echo "   uvicorn backend.app:app --host 0.0.0.0 --port 8000"
echo "======================================"
