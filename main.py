"""
Project Snapshotter Script

This script recursively traverses a specified project directory, reads all text files,
and concatenates their contents into a single .txt file. The output file
includes the relative path of each file followed by its content, formatted
with triple backticks.

The script provides options to use the project's .gitignore file for exclusions
or to manually enter exclusion patterns. The final output file is saved in
the same directory where this script is executed.
"""

from typing import List, Set
import fnmatch
import os

def parse_gitignore(gitignore_path: str) -> Set[str]:
    """
    Parses a .gitignore file and returns a set of patterns.
    
    Args:
        gitignore_path: The absolute path to the .gitignore file.
        
    Returns:
        A set of strings, where each string is a gitignore pattern.
        Lines that are empty or start with '#' are ignored.
    """
    patterns = set()
    if not os.path.isfile(gitignore_path):
        return patterns
        
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                # Ignore comments and empty lines
                if stripped_line and not stripped_line.startswith('#'):
                    patterns.add(stripped_line)

    except Exception as e:
        print(f"Warning: Could not read .gitignore file at {gitignore_path}. Error: {e}")

    return patterns

def get_user_exclusions() -> Set[str]:
    """
    Prompts the user to manually enter exclusion patterns.
    
    Returns:
        A set of strings, where each string is a user-provided pattern.
        Input is split by commas.
    """
    print("\nPlease enter patterns to exclude (e.g., *.log, dist, build, *.tmp)")
    user_input = input("Separate multiple patterns with a comma: ").strip()
    
    if not user_input:
        return set()
        
    # Split by comma and strip whitespace from each pattern
    patterns = {pattern.strip() for pattern in user_input.split(',')}
    return patterns

def create_project_snapshot(root_dir: str, exclude_patterns: Set[str], output_file_path: str):
    """
    Generates the project snapshot text file.
    
    It walks through the root_dir, skipping excluded files/directories,
    and writes the formatted content to the output_file_path.
    
    Args:
        root_dir: The absolute path to the target project directory.
        exclude_patterns: A set of patterns (fnmatch/gitignore style) to exclude.
        output_file_path: The absolute path where the final .txt file will be saved.
    """
    
    # Get just the filename of the output file to prevent it from being included
    # if the script is run on the same directory it's in.
    output_filename = os.path.basename(output_file_path)
    
    all_file_contents = []

    print("\nStarting project traversal...")

    # os.walk allows us to traverse the directory tree
    # topdown=True lets us "prune" directories from the traversal,
    # which is much more efficient than checking every file inside.
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        
        # --- Directory Pruning ---
        # We modify dirnames *in-place* to prevent os.walk from descending
        # into directories that match our exclusion patterns.
        
        # Create a list of directories to keep
        dirs_to_keep = []
        for d in dirnames:
            # Check if the directory name itself matches any pattern
            is_excluded = any(fnmatch.fnmatch(d, p) for p in exclude_patterns)
            if not is_excluded:
                dirs_to_keep.append(d)
        
        # This in-place modification is the key to pruning
        dirnames[:] = dirs_to_keep

        # --- File Processing ---
        for filename in filenames:
            
            # 1. Skip the output file itself
            if filename == output_filename:
                continue
                
            file_path = os.path.join(dirpath, filename)
            
            # 2. Get the relative path for display and pattern matching
            # We normalize to forward slashes (/) for consistency, just like in .gitignore
            try:
                relative_path = os.path.relpath(file_path, root_dir).replace(os.sep, '/')

            except ValueError:
                # This can happen on Windows if root_dir and file_path are on different drives
                print(f"Skipping file on different drive: {file_path}")
                continue

            # 3. Check if the file or its path matches any exclusion pattern
            # We check both the simple filename (e.g., "test.log")
            # and the relative path (e.g., "src/logs/test.log")
            if any(fnmatch.fnmatch(filename, p) or fnmatch.fnmatch(relative_path, p) for p in exclude_patterns):
                continue

            # 4. Try to read the file as text
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Format the content as requested
                formatted_block = f"{relative_path}\n```\n{content}\n```\n\n"
                all_file_contents.append(formatted_block)
                
            except UnicodeDecodeError:
                # This catches binary files (images, executables, etc.)
                print(f"Ignoring binary or non-UTF-8 file: {relative_path}")

            except IOError as e:
                # This catches permission errors or other I/O issues
                print(f"Error reading file {relative_path}: {e}")

            except Exception as e:
                # Catch-all for other unexpected errors
                print(f"Unexpected error processing file {relative_path}: {e}")

    # --- Writing the Output File ---
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write("".join(all_file_contents))
        
        print("\n" + "="*50)
        print("✅ Success! Project snapshot created.")
        print(f"Output file location: {output_file_path}")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Critical Error: Failed to write output file.")
        print(f"Path: {output_file_path}")
        print(f"Error: {e}")

# --- Main Execution Block ---
if __name__ == "__main__":
    
    # --- 1. Determine Output Path ---
    # The output file will be saved in the *same directory as this script*.
    try:
        # '__file__' is the path to the currently running script
        script_dir = os.path.dirname(os.path.abspath(__file__))

    except NameError:
        # Fallback if running in an environment where __file__ is not defined (e.g., some IDEs)
        script_dir = os.getcwd()
        print("Warning: Could not determine script directory, using current working directory for output.")
        
    output_filename = "project_snapshot.txt"
    output_file_path = os.path.join(script_dir, output_filename)

    # --- 2. Get Target Project Path ---
    project_path = input("Please enter the path to the root directory of your project: ").strip()
    
    # Validate the path
    if not os.path.isdir(project_path):
        print(f"Error: The path provided is not a valid directory.")
        print(f"Path: {project_path}")
        exit(1) # Exit the script with an error code
        
    # Convert to absolute path for reliability
    project_path = os.path.abspath(project_path)

    # --- 3. Handle Exclusions ---
    
    # Start with a base set of common, high-noise directories
    # These will be excluded regardless of user choice.
    final_exclude_patterns = {
        '.git', 
        'node_modules', 
        '__pycache__', 
        'venv', 
        '.venv', 
        '.vscode', 
        '.idea',
        'dist',
        'build',
        '*.pyc',
        '*.tmp',
        '.DS_Store'
    }

    gitignore_path = os.path.join(project_path, ".gitignore")
    
    if os.path.isfile(gitignore_path):
        # A .gitignore file exists, so we ask the user what to do
        print(f"\nA .gitignore file was found at: {gitignore_path}")
        use_gitignore = input("Do you want to add its rules to the exclusion list? (yes/no): ").strip().lower()
        
        if use_gitignore in ('yes', 'y'):
            # User said yes, parse the file
            print("Loading patterns from .gitignore...")
            gitignore_patterns = parse_gitignore(gitignore_path)
            final_exclude_patterns.update(gitignore_patterns)
            print(f"Loaded {len(gitignore_patterns)} new patterns from .gitignore.")
        
        else:
            # User said no, ask for manual input
            print("Ignoring .gitignore file.")
            user_patterns = get_user_exclusions()
            final_exclude_patterns.update(user_patterns)
            
    else:
        # No .gitignore file was found
        print("\nNo .gitignore file found in the project root.")
        add_manual = input("Do you want to manually add exclusion patterns? (yes/no): ").strip().lower()
        
        if add_manual in ('yes', 'y'):
            user_patterns = get_user_exclusions()
            final_exclude_patterns.update(user_patterns)
            
        else:
            print("Proceeding with default exclusions only.")

    # --- 4. Run the Snapshot ---
    create_project_snapshot(project_path, final_exclude_patterns, output_file_path)