#!/bin/bash
# RAG SDS Matrix launcher with Qt platform selection

export QT_STYLE_OVERRIDE=kvantum-dark
export QT_QPA_PLATFORMTHEME=Kvantum

# Preload XCB cursor library to avoid missing symbol errors
export LD_PRELOAD="/usr/lib/libxcb-cursor.so.0:${LD_PRELOAD}"
export LD_LIBRARY_PATH="/usr/lib:/usr/lib/qt6:${LD_LIBRARY_PATH}"

# Detect best platform
if command -v wayland &>/dev/null && [ -n "$WAYLAND_DISPLAY" ]; then
    echo "Using Wayland platform"
    export QT_QPA_PLATFORM=wayland
elif [ -n "$DISPLAY" ]; then
    echo "Using XCB (X11) platform on $DISPLAY"
    export QT_QPA_PLATFORM=xcb
else
    echo "No display server detected. Using offscreen platform."
    echo "Note: The GUI will not be visible, but the app will run."
    export QT_QPA_PLATFORM=offscreen
fi

# Run the app
/home/rdmdelboni/Work/Gits/RAG_SDS_MATRIX/.venv/bin/python /home/rdmdelboni/Work/Gits/RAG_SDS_MATRIX/main.py "$@"
