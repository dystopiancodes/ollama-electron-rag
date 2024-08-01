#!/bin/bash

# Navigate to the directory containing the Python files (if necessary)
cd app

# Combine all Python files into a single file
for file in *.py; do
    echo -e "\n# File: $file\n" >> combined_script.py
    cat "$file" >> combined_script.py
done

echo "All Python files have been combined into combined_script.py"