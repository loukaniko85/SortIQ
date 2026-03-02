#!/bin/bash
# Simplified AppImage build script using python-appimage

set -e

APP_NAME="SortIQ"
APP_VERSION="1.3"

echo "Building $APP_NAME AppImage (simplified method)..."

# Check if python-appimage is installed
if ! command -v python-appimage &> /dev/null; then
    echo "Installing python-appimage..."
    pip3 install --user python-appimage
fi

# Create a simple wrapper script
cat > run_app.sh <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 main.py "$@"
EOF
chmod +x run_app.sh

# Build AppImage
python-appimage build app \
    --name "$APP_NAME" \
    --version "$APP_VERSION" \
    --entrypoint run_app.sh \
    --python-version 3.11 \
    --requirements requirements.txt

echo "Done! AppImage should be created in the current directory."
