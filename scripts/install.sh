#!/bin/bash
DOWNLOAD_DIR="./tmp"
mkdir -p "$DOWNLOAD_DIR"

if [ ! -f "$DOWNLOAD_DIR/TCIA*" ]; then
    echo "TCIA Data Retriever not exist, start downloading"
    curl -C - --output-dir "$DOWNLOAD_DIR" -OL https://github.com/TCIA/data-retriever/releases/latest/download/TCIA_Data_Retriever_linux_x86_64.zip
fi

echo "Start installing TCIA Data Retriever"

if [ ! -f "$DOWNLOAD_DIR/TCIA_Data_Retriever-x86_64.AppImage"]; then
    unzip "${DOWNLOAD_DIR}/TCIA_Data_Retriever_linux_x86_64.zip"
fi

