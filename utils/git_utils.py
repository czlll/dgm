import os
import git
import subprocess


def get_git_commit_hash(repo_path='.'):
    try:
        # Load the repository
        repo = git.Repo(repo_path)
        # Get the current commit hash
        commit_hash = repo.head.commit.hexsha
        return commit_hash
    except Exception as e:
        print("Error while getting git commit hash:", e)
        return None

def apply_patch(git_dname, patch_str):
    """
    Apply a patch to the repository at `git_dname`.
    """
    cmd = ["git", "-C", git_dname, "apply", "--reject", "-"]
    result = subprocess.run(
        cmd,
        input=patch_str,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False
    )
    # Check if the patch was applied successfully
    if result.returncode != 0:
        print(f"apply_patch error: Patch did not fully apply. Return code: {result.returncode}, stdout: {result.stdout}, stderr: {result.stderr}")
    else:
        print("apply_patch successful")

def diff_versus_commit(git_dname, commit):
    """
    Take a diff of `git_dname` current contents versus the `commit`, including untracked files,
    without modifying the repository state.
    """
    # Get diff of tracked files
    diff_cmd = ["git", "-C", git_dname, "diff", commit]
    result = subprocess.run(diff_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    diff_output = result.stdout.decode()

    # Get list of untracked files
    untracked_files_cmd = ["git", "-C", git_dname, "ls-files", "--others", "--exclude-standard"]
    result = subprocess.run(untracked_files_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    untracked_files = result.stdout.decode().splitlines()

    # Generate diffs for untracked files
    for file in untracked_files:
        # Diff untracked file against /dev/null (empty file)
        file_path = os.path.join(git_dname, file)
        devnull = '/dev/null'
        if os.name == 'nt':  # Handle Windows
            devnull = 'NUL'
        diff_file_cmd = ["git", "-C", git_dname, "diff", "--no-index", devnull, file]
        result = subprocess.run(
            diff_file_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=git_dname,
            check=False
        )
        diff_file_output = result.stdout.decode('utf-8', errors='replace')
        diff_output += diff_file_output

    return diff_output

def reset_to_commit(git_dname, commit):
    """
    Reset the repository at `git_dname` to the given `commit`.
    """
    # Step 1: Hard-reset tracked files
    reset_cmd = ["git", "-C", git_dname, "reset", "--hard", commit]
    result_reset = subprocess.run(
        reset_cmd,
        capture_output=True,
        text=True,
        check=False
    )
    if result_reset.returncode != 0:
        print(f"reset_to_commit error: Failed to reset {git_dname} to commit '{commit}'. STDOUT: {result_reset.stdout} STDERR: {result_reset.stderr}")
    else:
        print(f"reset_to_commit successful: {commit}")

    # Step 2: Clean untracked files (the "new files") and directories
    clean_cmd = ["git", "-C", git_dname, "clean", "-fd"]
    result_clean = subprocess.run(
        clean_cmd,
        capture_output=True,
        text=True,
        check=False
    )
    if result_clean.returncode != 0:
        print(f"reset_to_commit clean error: Failed to clean {git_dname}. STDOUT: {result_clean.stdout} STDERR: {result_clean.stderr}")
    else:
        print(f"reset_to_commit clean successful: {commit}")


def filter_patch_by_files(patch_str, target_files):
    """
    Filters out the diff blocks related to any of the target_files in a patch string.

    Args:
        patch_str (str): The complete patch text.
        target_files (list[str]): A list of filenames for which to extract changes (e.g. ['affine_cipher.py', 'other.py']).

    Returns:
        str: A string containing only the diff blocks for the specified target files.
    """
    lines = patch_str.splitlines()
    filtered_lines = []
    include_block = False

    for line in lines:
        # When we encounter a new diff block header, check if the block is for any of the target files.
        if line.startswith("diff --git"):
            include_block = any(f"a/{target}" in line and f"b/{target}" in line for target in target_files)
        if include_block:
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def remove_patch_by_files(patch_str, keyword='polyglot'):
    """
    Removes diff blocks related to files containing the keyword from a patch string.

    Args:
        patch_str (str): The complete patch text.
        keyword (str): Keyword to match in filenames for removal (default: 'polyglot').

    Returns:
        str: A string containing the patch with diff blocks for matching files removed.
    """
    lines = patch_str.splitlines()
    filtered_lines = []
    include_block = True

    for line in lines:
        # When we encounter a new diff block header, check if the block contains the keyword
        if line.startswith("diff --git"):
            include_block = keyword.lower() not in line.lower()
        if include_block:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)


def is_patch_empty_or_test_only(patch_str, test_keywords=None):
    """
    Check if a patch is empty or only modifies test files.
    
    Args:
        patch_str (str): The patch content
        test_keywords (list): Keywords to identify test files (default: common test patterns)
    
    Returns:
        tuple: (is_empty, is_test_only, modified_files)
    """
    if test_keywords is None:
        test_keywords = ['test_', '_test', 'tests/', '/test/', 'test.py', 'conftest.py', 'pytest', 'unittest']
    
    # Check if patch is empty
    if not patch_str or not patch_str.strip():
        return True, False, []
    
    # Extract modified files from patch
    modified_files = []
    lines = patch_str.splitlines()
    
    for line in lines:
        if line.startswith("diff --git"):
            # Extract file paths from diff header
            # Format: diff --git a/path/to/file b/path/to/file
            parts = line.split()
            if len(parts) >= 4:
                file_a = parts[2][2:]  # Remove 'a/' prefix
                file_b = parts[3][2:]  # Remove 'b/' prefix
                # Use the 'b/' file path (destination) as it represents the current state
                modified_files.append(file_b)
    
    if not modified_files:
        return True, False, []
    
    # Check if all modified files are test files
    source_files = []
    test_files = []
    
    for file_path in modified_files:
        is_test_file = any(keyword in file_path.lower() for keyword in test_keywords)
        if is_test_file:
            test_files.append(file_path)
        else:
            source_files.append(file_path)
    
    is_test_only = len(source_files) == 0 and len(test_files) > 0
    
    return False, is_test_only, modified_files


def get_patch_summary(patch_str):
    """
    Get a summary of what files are modified in a patch.
    
    Args:
        patch_str (str): The patch content
    
    Returns:
        str: A human-readable summary of the patch
    """
    is_empty, is_test_only, modified_files = is_patch_empty_or_test_only(patch_str)
    
    if is_empty:
        return "Empty patch - no files modified"
    
    if is_test_only:
        return f"Test-only patch - modified {len(modified_files)} test file(s): {', '.join(modified_files)}"
    
    # Count source vs test files
    test_keywords = ['test_', '_test', 'tests/', '/test/', 'test.py', 'conftest.py', 'pytest', 'unittest']
    source_files = []
    test_files = []
    
    for file_path in modified_files:
        is_test_file = any(keyword in file_path.lower() for keyword in test_keywords)
        if is_test_file:
            test_files.append(file_path)
        else:
            source_files.append(file_path)
    
    summary_parts = []
    if source_files:
        summary_parts.append(f"{len(source_files)} source file(s): {', '.join(source_files)}")
    if test_files:
        summary_parts.append(f"{len(test_files)} test file(s): {', '.join(test_files)}")
    
    return f"Patch modifies {len(modified_files)} file(s) - " + "; ".join(summary_parts)