#!/bin/bash
echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing wheel and setuptools..."
pip install wheel setuptools

echo "Installing each requirement separately with verbose output..."
while read requirement; do
    # Skip comments and empty lines
    [[ $requirement =~ ^#.*$ ]] && continue
    [[ -z $requirement ]] && continue
    
    echo "Installing $requirement..."
    pip install -v $requirement
    if [ $? -ne 0 ]; then
        echo "Failed to install $requirement"
        exit 1
    fi
done < requirements.txt

echo "All requirements installed successfully"
