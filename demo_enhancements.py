#!/usr/bin/env python3
"""
Demonstration script for the enhanced coding agent features
"""

import tempfile
import os
from tools.edit import tool_function
from utils.git_utils import is_patch_empty_or_test_only, get_patch_summary
from llm_withtools import summarize_history

def demo_enhanced_editor():
    """Demonstrate the enhanced editor tool features"""
    print("=" * 60)
    print("DEMO: Enhanced Editor Tool")
    print("=" * 60)
    
    # Create a temporary file for demonstration
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""def example_function():
    '''This is an example function'''
    x = 1
    y = 2
    z = x + y
    return z

def another_function():
    '''Another function'''
    return "hello world"

# Some comments
# More comments
# Even more comments
""")
        temp_file = f.name
    
    try:
        print(f"Created temporary file: {temp_file}")
        
        # Demo 1: View with range
        print("\n1. Viewing lines 1-8:")
        result = tool_function('view', temp_file, view_range=[1, 8])
        print(result)
        
        print("\n2. Viewing from line 9 to end:")
        result = tool_function('view', temp_file, view_range=[9, -1])
        print(result)
        
        # Demo 2: String replacement
        print("\n3. Replacing function content:")
        result = tool_function('str_replace', temp_file, 
                              old_str='    x = 1\n    y = 2\n    z = x + y\n    return z',
                              new_str='    # Simplified implementation\n    return 1 + 2')
        print(result)
        
        print("\n4. Viewing the modified file:")
        result = tool_function('view', temp_file)
        print(result)
        
    finally:
        os.unlink(temp_file)
        print(f"\nCleaned up temporary file: {temp_file}")

def demo_patch_validation():
    """Demonstrate patch validation features"""
    print("\n" + "=" * 60)
    print("DEMO: Patch Validation")
    print("=" * 60)
    
    # Test different types of patches
    patches = [
        ("Empty patch", ""),
        ("Test-only patch", """diff --git a/test_example.py b/test_example.py
index 1234567..abcdefg 100644
--- a/test_example.py
+++ b/test_example.py
@@ -1,3 +1,4 @@
 def test_something():
+    # Added test comment
     assert True
"""),
        ("Source code patch", """diff --git a/main.py b/main.py
index 1234567..abcdefg 100644
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
 def main():
+    print("Hello, World!")
     pass
"""),
        ("Mixed patch", """diff --git a/main.py b/main.py
index 1234567..abcdefg 100644
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
 def main():
+    print("Hello, World!")
     pass
diff --git a/test_main.py b/test_main.py
index 1234567..abcdefg 100644
--- a/test_main.py
+++ b/test_main.py
@@ -1,3 +1,4 @@
 def test_main():
+    # Test comment
     assert True
""")
    ]
    
    for name, patch in patches:
        print(f"\n{name}:")
        is_empty, is_test_only, modified_files = is_patch_empty_or_test_only(patch)
        summary = get_patch_summary(patch)
        
        print(f"  Empty: {is_empty}")
        print(f"  Test-only: {is_test_only}")
        print(f"  Modified files: {modified_files}")
        print(f"  Summary: {summary}")
        print(f"  Valid for deployment: {not is_empty and not is_test_only}")

def demo_conversation_summarization():
    """Demonstrate conversation history summarization"""
    print("\n" + "=" * 60)
    print("DEMO: Conversation Summarization")
    print("=" * 60)
    
    # Create a sample conversation history
    msg_history = []
    for i in range(10):
        msg_history.extend([
            {
                'role': 'user',
                'content': [{'type': 'text', 'text': f'User message {i+1}: This is a longer message with some content that might take up space in the context window.'}]
            },
            {
                'role': 'assistant', 
                'content': [{'type': 'text', 'text': f'Assistant response {i+1}: Here is a detailed response that also takes up context space.'}]
            }
        ])
    
    print(f"Original conversation length: {len(msg_history)} messages")
    
    # Demonstrate summarization with different settings
    for keep_count in [3, 5, 8]:
        summarized = summarize_history(msg_history, max_messages_to_keep=keep_count, logging=print)
        print(f"Keeping {keep_count} recent messages: {len(summarized)} total messages")
        
        if len(summarized) > 0 and 'CONVERSATION SUMMARY' in summarized[0]['content'][0]['text']:
            summary_preview = summarized[0]['content'][0]['text'][:150] + "..."
            print(f"  Summary preview: {summary_preview}")
        print()

def demo_comprehensive_features():
    """Run all demonstrations"""
    print("Enhanced Coding Agent - Feature Demonstrations")
    print("=" * 60)
    
    try:
        demo_enhanced_editor()
        demo_patch_validation()
        demo_conversation_summarization()
        
        print("\n" + "=" * 60)
        print("All demonstrations completed successfully!")
        print("=" * 60)
        
        print("\nKey Benefits:")
        print("✓ Enhanced editor with precise string replacement and range viewing")
        print("✓ Automatic patch validation to ensure source code modifications")
        print("✓ Intelligent conversation summarization for token limit management")
        print("✓ Multi-attempt solution process with iterative improvement")
        print("✓ Comprehensive logging and transparent retry mechanisms")
        
    except Exception as e:
        print(f"\nError during demonstration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demo_comprehensive_features()