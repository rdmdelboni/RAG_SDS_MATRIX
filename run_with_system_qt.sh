#!/bin/bash
# Run RAG SDS Matrix - XCB (X11) with Kvantum dark theme

export DISPLAY=:1
export QT_QPA_PLATFORM=xcb
export QT_STYLE_OVERRIDE=kvantum-dark
export QT_QPA_PLATFORMTHEME=Kvantum

# Use system Qt6 libraries
export QT_PLUGIN_PATH="/usr/lib/qt6/plugins"
export LD_LIBRARY_PATH="/usr/lib/qt6:/usr/lib:${LD_LIBRARY_PATH}"

# Launch the app
/home/rdmdelboni/Work/Gits/RAG_SDS_MATRIX/.venv/bin/python /home/rdmdelboni/Work/Gits/RAG_SDS_MATRIX/main.py "$@"
