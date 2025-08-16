#!/usr/bin/env python3
"""Force complete restart by modifying critical initialization code"""

import os
import time
from datetime import datetime

# Add a unique timestamp comment to force complete reload
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Read app.py
with open('app.py', 'r') as f:
    content = f.read()

# Replace the timestamp comment
import re
content = re.sub(
    r'# Deploy timestamp: .*',
    f'# Deploy timestamp: {timestamp} - Force SQLAlchemy metadata clear',
    content
)

# Write back
with open('app.py', 'w') as f:
    f.write(content)

print(f"Updated app.py with timestamp: {timestamp}")

# Also update the __init__.py to force model reload
with open('models/__init__.py', 'r') as f:
    content = f.read()

# Add a comment to force reload
if '# Force reload:' in content:
    content = re.sub(
        r'# Force reload: .*',
        f'# Force reload: {timestamp}',
        content
    )
else:
    # Add before the imports
    content = f'# Force reload: {timestamp}\n' + content

with open('models/__init__.py', 'w') as f:
    f.write(content)

print(f"Updated models/__init__.py with timestamp: {timestamp}")
print("Files updated. Ready to commit and push.")
