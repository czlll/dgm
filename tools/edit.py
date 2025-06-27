from pathlib import Path
import subprocess

def tool_info():
    return {
        "name": "editor",
        "description": """Custom editing tool for viewing, creating and editing files in plain-text format\n
* State is persistent across command calls and discussions with the user\n
* If `path` is a text file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep\n
* The `create` command cannot be used if the specified `path` already exists as a file\n
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`\n
* The `str_replace` command will revert the last edit made to the file at `path`\n
* This tool can be used for creating and editing files in plain-text format.\n\n
Before using this tool:\n
1. Use the view tool to understand the file's contents and context\n
2. Verify the directory path is correct (only applicable when creating new files):\n
   - Use the view tool to verify the parent directory exists and is the correct location\n\n
When making edits:\n
   - Ensure the edit results in idiomatic, correct code\n
   - Do not leave the code in a broken state\n
   - Always use absolute file paths (starting with /)\n\n
CRITICAL REQUIREMENTS FOR USING THIS TOOL:\n\n
1. EXACT MATCHING: The `old_str` parameter must match EXACTLY one or more consecutive lines from the file, including all whitespace and indentation. The tool will fail if `old_str` matches multiple locations or doesn't match exactly with the file content.\n\n
2. UNIQUENESS: The `old_str` must uniquely identify a single instance in the file:\n
   - Include sufficient context before and after the change point (3-5 lines recommended)\n
   - If not unique, the replacement will not be performed\n\n
3. REPLACEMENT: The `new_str` parameter should contain the edited lines that replace the `old_str`. Both strings must be different.\n\n
Remember: when making multiple file edits in a row to the same file, you should prefer to send all edits in a single message with multiple calls to this tool, rather than multiple messages with a single call each.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["view", "create", "str_replace"],
                    "description": "The commands to run. Allowed options are: `view`, `create`, `str_replace`."
                },
                "path": {
                    "description": "Absolute path to file or directory, e.g. `/workspace/file.py` or `/workspace`.",
                    "type": "string"
                },
                "file_text": {
                    "description": "Required parameter of `create` command, with the content of the file to be created.",
                    "type": "string"
                },
                "view_range": {
                    "description": "Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.",
                    "type": "array",
                    "items": {"type": "integer"}
                },
                "old_str": {
                    "description": "Required parameter of `str_replace` command containing the string in `path` to replace.",
                    "type": "string"
                },
                "new_str": {
                    "description": "Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.",
                    "type": "string"
                }
            },
            "required": ["command", "path"]
        }
    }

def maybe_truncate(content: str, max_length: int = 10000) -> str:
    """Truncate long content and add marker."""
    if len(content) > max_length:
        return content[:max_length] + "\n<response clipped>"
    return content

def validate_path(path: str, command: str) -> Path:
    """
    Validate the file path for each command:
      - 'view': path may be a file or directory; must exist.
      - 'create': path must not exist (for new file creation).
      - 'str_replace': path must exist and must be a file.
    """
    path_obj = Path(path)

    # Check if it's an absolute path
    if not path_obj.is_absolute():
        raise ValueError(
            f"The path {path} is not an absolute path (must start with '/')."
        )

    if command == "view":
        # Path must exist
        if not path_obj.exists():
            raise ValueError(f"The path {path} does not exist.")
    elif command == "create":
        # Path must not exist
        if path_obj.exists():
            raise ValueError(f"Cannot create new file; {path} already exists.")
    elif command == "str_replace":
        # Path must exist and must be a file
        if not path_obj.exists():
            raise ValueError(f"The file {path} does not exist.")
        if path_obj.is_dir():
            raise ValueError(f"{path} is a directory and cannot be edited as a file.")
    else:
        raise ValueError(f"Unknown or unsupported command: {command}")

    return path_obj

def format_output(content: str, path: str, init_line: int = 1) -> str:
    """Format output with line numbers (for file content)."""
    content = maybe_truncate(content)
    content = content.expandtabs()
    numbered_lines = [
        f"{i + init_line:6}\t{line}"
        for i, line in enumerate(content.split("\n"))
    ]
    return f"Here's the result of running `cat -n` on {path}:\n" + "\n".join(numbered_lines) + "\n"

def read_file(path: Path) -> str:
    """Read and return the entire file contents."""
    try:
        return path.read_text()
    except Exception as e:
        raise ValueError(f"Failed to read file: {e}")

def write_file(path: Path, content: str):
    """Write (overwrite) entire file contents."""
    try:
        path.write_text(content)
    except Exception as e:
        raise ValueError(f"Failed to write file: {e}")

def view_path(path_obj: Path, view_range=None) -> str:
    """View the file contents or directory listing, optionally with line range."""
    if path_obj.is_dir():
        # For directories: list non-hidden files up to 2 levels deep
        try:
            result = subprocess.run(
                ['find', str(path_obj), '-maxdepth', '2', '-not', '-path', '*/\\.*'],
                capture_output=True,
                text=True
            )
            if result.stderr:
                return f"Error listing directory: {result.stderr}"
            
            # Count hidden files/directories
            hidden_count = 0
            try:
                hidden_result = subprocess.run(
                    ['find', str(path_obj), '-maxdepth', '1', '-name', '.*'],
                    capture_output=True,
                    text=True
                )
                if hidden_result.returncode == 0:
                    hidden_count = len([line for line in hidden_result.stdout.strip().split('\n') if line and line != str(path_obj)])
            except:
                pass
            
            output = (
                f"Here's the files and directories up to 2 levels deep in {path_obj}, excluding hidden items:\n"
                + result.stdout
            )
            if hidden_count > 0:
                output += f"\n{hidden_count} hidden files/directories in this directory are excluded. You can use 'ls -la {path_obj}' to see them."
            return output
        except Exception as e:
            raise ValueError(f"Failed to list directory: {e}")

    # If it's a file, show the file with line numbers (optionally with range)
    content = read_file(path_obj)
    
    if view_range is not None:
        lines = content.split('\n')
        start_line, end_line = view_range
        
        # Convert to 0-based indexing
        start_idx = max(0, start_line - 1)
        
        if end_line == -1:
            end_idx = len(lines)
        else:
            end_idx = min(len(lines), end_line)
        
        if start_idx >= len(lines):
            return f"Error: Start line {start_line} is beyond the file length ({len(lines)} lines)."
        
        selected_lines = lines[start_idx:end_idx]
        selected_content = '\n'.join(selected_lines)
        return format_output(selected_content, str(path_obj), init_line=start_line)
    
    return format_output(content, str(path_obj))

def str_replace_in_file(path_obj: Path, old_str: str, new_str: str = "") -> str:
    """Replace old_str with new_str in the file, ensuring old_str appears exactly once."""
    content = read_file(path_obj)
    
    # Count occurrences of old_str
    count = content.count(old_str)
    
    if count == 0:
        return f"Error: The string to replace was not found in {path_obj}."
    elif count > 1:
        return f"Error: The string to replace appears {count} times in {path_obj}. It must appear exactly once."
    
    # Perform the replacement
    new_content = content.replace(old_str, new_str, 1)
    
    # Check if the replacement actually changed the content
    if new_content == content:
        return f"Error: The old_str and new_str are identical, no changes made to {path_obj}."
    
    # Write the new content
    write_file(path_obj, new_content)
    
    return f"File at {path_obj} has been edited. Here's the result of running `cat -n` on a snippet of {path_obj}:\n" + \
           format_output(new_str, str(path_obj))

def tool_function(command: str, path: str, file_text: str = None, view_range=None, old_str: str = None, new_str: str = None) -> str:
    """
    Main tool function that handles:
      - 'view'       : View the file or directory listing, optionally with line range
      - 'create'     : Create a new file with the given file_text
      - 'str_replace': Replace old_str with new_str in the file
    """
    try:
        path_obj = validate_path(path, command)

        if command == "view":
            return view_path(path_obj, view_range)

        elif command == "create":
            if file_text is None:
                raise ValueError("Missing required `file_text` for 'create' command.")
            write_file(path_obj, file_text)
            return f"File created successfully at: {path}"

        elif command == "str_replace":
            if old_str is None:
                raise ValueError("Missing required `old_str` for 'str_replace' command.")
            if new_str is None:
                new_str = ""
            return str_replace_in_file(path_obj, old_str, new_str)

        else:
            raise ValueError(f"Unknown command: {command}")

    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Test replacement
    result = tool_function("view", "./coding_agent.py", view_range=[1, 10])
    print(result)
