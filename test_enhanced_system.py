#!/usr/bin/env python3
"""
Test script for the enhanced AgenticSystem
"""

import tempfile
import os
import subprocess
from coding_agent import AgenticSystem

def create_test_repo():
    """Create a simple test repository with a bug to fix"""
    temp_dir = tempfile.mkdtemp()
    
    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=temp_dir, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_dir, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_dir, check=True)
    
    # Create a simple Python file with a bug
    main_py = """def add_numbers(a, b):
    # Bug: should return a + b, but returns a - b
    return a - b

def main():
    result = add_numbers(5, 3)
    print(f"5 + 3 = {result}")

if __name__ == "__main__":
    main()
"""
    
    with open(os.path.join(temp_dir, 'main.py'), 'w') as f:
        f.write(main_py)
    
    # Create a test file
    test_py = """import pytest
from main import add_numbers

def test_add_numbers():
    assert add_numbers(5, 3) == 8
    assert add_numbers(0, 0) == 0
    assert add_numbers(-1, 1) == 0
"""
    
    with open(os.path.join(temp_dir, 'test_main.py'), 'w') as f:
        f.write(test_py)
    
    # Commit the initial state
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit with bug'], cwd=temp_dir, check=True)
    
    # Get the commit hash
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=temp_dir, capture_output=True, text=True, check=True)
    commit_hash = result.stdout.strip()
    
    return temp_dir, commit_hash

def test_enhanced_system():
    """Test the enhanced AgenticSystem with patch validation and multi-attempt logic"""
    print("Creating test repository...")
    temp_dir, base_commit = create_test_repo()
    
    try:
        print(f"Test repo created at: {temp_dir}")
        print(f"Base commit: {base_commit}")
        
        # Create AgenticSystem with enhanced features
        problem_statement = """
        The add_numbers function in main.py has a bug. It should add two numbers but currently subtracts them.
        Fix the function so that it correctly adds the two input numbers.
        """
        
        test_description = """
        Run the tests in test_main.py using pytest to verify the fix works correctly.
        The tests should pass after fixing the add_numbers function.
        """
        
        chat_history_file = os.path.join(temp_dir, 'chat_history.md')
        
        system = AgenticSystem(
            problem_statement=problem_statement,
            git_tempdir=temp_dir,
            base_commit=base_commit,
            chat_history_file=chat_history_file,
            test_description=test_description,
            max_attempts=2,  # Use fewer attempts for testing
            max_patch_retries=1,
            instance_id='test'
        )
        
        print("Testing patch validation...")
        
        # Test empty patch validation
        empty_patch = ""
        is_valid, summary, files = system.validate_patch(empty_patch)
        print(f"Empty patch validation: valid={is_valid}, summary='{summary}'")
        assert not is_valid, "Empty patch should be invalid"
        
        # Test test-only patch validation
        test_patch = """diff --git a/test_main.py b/test_main.py
index 1234567..abcdefg 100644
--- a/test_main.py
+++ b/test_main.py
@@ -1,3 +1,4 @@
 import pytest
+# Added comment
 from main import add_numbers
"""
        is_valid, summary, files = system.validate_patch(test_patch)
        print(f"Test-only patch validation: valid={is_valid}, summary='{summary}'")
        assert not is_valid, "Test-only patch should be invalid"
        
        # Test valid source patch validation
        source_patch = """diff --git a/main.py b/main.py
index 1234567..abcdefg 100644
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
 def add_numbers(a, b):
+    # Fixed the bug
     return a + b
"""
        is_valid, summary, files = system.validate_patch(source_patch)
        print(f"Source patch validation: valid={is_valid}, summary='{summary}'")
        assert is_valid, "Source patch should be valid"
        
        print("✓ Patch validation tests passed!")
        
        print("Testing attempt context building...")
        
        # Add some fake attempt history
        system.attempt_history = [
            {
                'attempt_num': 1,
                'patch': source_patch,
                'patch_summary': 'Test patch',
                'test_report': {'test_add_numbers': 'PASSED'},
                'score': 1.0,
                'msg_history': []
            }
        ]
        
        context = system.build_attempt_context(2)
        print(f"Attempt context length: {len(context)}")
        assert "PREVIOUS ATTEMPTS CONTEXT" in context, "Context should contain previous attempts"
        
        print("✓ Attempt context building tests passed!")
        
        print("All enhanced system tests passed!")
        
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test repo: {temp_dir}")

if __name__ == "__main__":
    test_enhanced_system()