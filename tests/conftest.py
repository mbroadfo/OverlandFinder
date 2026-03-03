"""
Pytest configuration — stubs MongoDB so tests run without a live Atlas connection.
"""
import os
import pytest

# Ensure a dummy URI is set before any src module imports try to connect
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("SMS_RECIPIENT", "test@vtext.com")
os.environ.setdefault("SMTP_USERNAME", "test@gmail.com")
os.environ.setdefault("SMTP_PASSWORD", "test-password")
