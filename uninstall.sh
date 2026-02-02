#!/bin/bash
#
# Claude-Discord Bridge Uninstaller
# This script removes the Claude-Discord Bridge from your system
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TOOLKIT_ROOT="$SCRIPT_DIR"
BIN_DIR="$TOOLKIT_ROOT/bin"

echo -e "${BLUE}🗑️  Claude-Discord Bridge Uninstaller${NC}"
echo "===================================="
echo ""

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Stop running services
stop_services() {
    print_info "Checking for running services..."

    # Try to stop services using vexit if available
    if [[ -x "$BIN_DIR/vexit" ]]; then
        "$BIN_DIR/vexit" 2>/dev/null || true
    else
        # Manual cleanup
        # Kill tmux sessions
        tmux kill-session -t claude-discord-bridge 2>/dev/null || true
        tmux kill-session -t claude-cli 2>/dev/null || true  # Legacy support

        # Kill any Python processes related to the toolkit
        pkill -f "discord_bot.py" 2>/dev/null || true
        pkill -f "flask_app.py" 2>/dev/null || true
    fi

    print_success "Services stopped"
}

# Remove from PATH
remove_from_path() {
    print_info "Removing from PATH..."

    # Detect shell
    SHELL_NAME=$(basename "$SHELL")
    RC_FILE=""

    case "$SHELL_NAME" in
        zsh)
            RC_FILE="$HOME/.zshrc"
            ;;
        bash)
            RC_FILE="$HOME/.bashrc"
            ;;
        *)
            print_warning "Unknown shell: $SHELL_NAME"
            echo "Please remove the following from your shell configuration manually:"
            echo "  export PATH=\"$BIN_DIR:\$PATH\""
            return
            ;;
    esac

    if [[ ! -f "$RC_FILE" ]]; then
        print_warning "RC file not found: $RC_FILE"
        return
    fi

    # Create backup
    cp "$RC_FILE" "$RC_FILE.claude-cli-backup"
    print_info "Created backup: $RC_FILE.claude-cli-backup"

    # Use Python for safer and more reliable text processing
    python3 << 'EOF' "$RC_FILE" "$BIN_DIR"
import sys
import re

rc_file = sys.argv[1]
bin_dir = sys.argv[2]

try:
    with open(rc_file, 'r') as f:
        lines = f.readlines()

    # Remove Claude-Discord Bridge related lines
    filtered_lines = []
    skip_next = False

    for line in lines:
        # Skip Claude-Discord Bridge comment and the following export line
        if '# Claude-Discord Bridge' in line:
            skip_next = True
            continue
        elif skip_next and f'export PATH="{bin_dir}:' in line:
            skip_next = False
            continue
        # Also handle old Claude CLI Toolkit entries
        elif '# Claude CLI Toolkit' in line:
            skip_next = True
            continue
        elif skip_next and (f'export PATH="{bin_dir}:' in line or '/claude-cli-toolkit/' in line):
            skip_next = False
            continue
        else:
            skip_next = False
            filtered_lines.append(line)

    # Remove trailing empty lines
    while filtered_lines and filtered_lines[-1].strip() == '':
        filtered_lines.pop()

    # Write back to file
    with open(rc_file, 'w') as f:
        f.writelines(filtered_lines)

    print("Successfully removed Claude-Discord Bridge entries")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF

    print_success "Removed from PATH"
}

# Remove configuration
remove_config() {
    # Check both old and new config directory names
    OLD_CONFIG_DIR="$HOME/.claude-cli-toolkit"
    NEW_CONFIG_DIR="$HOME/.claude-discord-bridge"

    # Determine which config directory exists
    if [[ -d "$NEW_CONFIG_DIR" ]]; then
        CONFIG_DIR="$NEW_CONFIG_DIR"
    elif [[ -d "$OLD_CONFIG_DIR" ]]; then
        CONFIG_DIR="$OLD_CONFIG_DIR"
    else
        CONFIG_DIR=""
    fi

    if [[ -d "$CONFIG_DIR" ]]; then
        echo ""
        print_warning "Configuration directory found: $CONFIG_DIR"
        echo "This contains your Discord bot token and session configuration."
        read -p "Remove configuration? (y/N): " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$CONFIG_DIR"
            print_success "Configuration removed"
        else
            print_info "Configuration kept at: $CONFIG_DIR"
        fi
    fi
}

# Main uninstall flow
main() {
    echo "This uninstaller will:"
    echo "  1. Stop any running Claude CLI services"
    echo "  2. Remove commands from your PATH"
    echo "  3. Optionally remove configuration files"
    echo ""
    echo -e "${YELLOW}Note: The toolkit files at $TOOLKIT_ROOT will NOT be deleted.${NC}"
    echo -e "${YELLOW}      You can manually delete them if needed.${NC}"
    echo ""

    read -p "Continue with uninstall? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Uninstall cancelled."
        exit 0
    fi

    echo ""
    stop_services
    remove_from_path
    remove_config

    echo ""
    echo "===================================="
    print_success "Uninstall complete!"
    echo ""
    echo "To complete the removal:"
    echo "  1. Open a new terminal or run: source ~/.${SHELL_NAME}rc"
    echo "  2. Optionally delete the toolkit directory:"
    echo "     rm -rf $TOOLKIT_ROOT"
    echo ""
    print_info "Thanks for using Claude-Discord Bridge! 👋"
}

# Run main function
main
