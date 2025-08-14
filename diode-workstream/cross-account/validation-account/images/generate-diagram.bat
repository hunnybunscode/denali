@echo off
echo Installing required packages...
pip install -r requirements.txt

echo Generating architecture diagram...
python validation-account-architecture.py

echo Done! Check validation-account-architecture.png
pause