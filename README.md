# Project-Snapshotter

A Python utility to consolidate all text-based files from a project directory into a single, formatted text file, perfect for context-feeding AI models.

-----

## Overview & Purpose

Have you ever tried to paste your entire project's codebase into an AI model (like GPT, Claude, or Gemini) for debugging, refactoring, or analysis?

It's a tedious process. You have to copy-paste file by file, you lose the directory structure, and you're constantly fighting with token limits.

**Project-Snapshotter** solves this. It's a single Python script that:

1.  Recursively walks through your project directory.
2.  Intelligently ignores non-essential files and folders (like `.git`, `node_modules`, `venv`, and binaries).
3.  Asks you if you want to use your project's `.gitignore` file for exclusions.
4.  Combines all relevant code into *one* clean `.txt` file.

The primary goal is to create a single, comprehensive "context dump" of your project. This makes it trivial to paste your entire codebase into an LLM prompt, providing it with the full context it needs to give you a high-quality response.

-----

## Features

  * **Recursive Traversal:** Scans the entire project tree, including sub-directories.
  * **Smart Exclusions:** Comes with a built-in list of common files/folders to ignore (e.g., `.git`, `__pycache__`, `node_modules`).
  * **.gitignore Integration:** Automatically detects and offers to use the rules from your project's `.gitignore` file.
  * **Custom Exclusions:** Allows you to add your own exclusion patterns (e.g., `*.log`, `temp/`) if you don't use `.gitignore`.
  * **Binary File Skipping:** Automatically detects and skips non-text files (images, executables, etc.).
  * **Clean Output:** Formats the output with file paths and markdown code blocks for maximum readability.
  * **Self-Contained:** Runs as a single script with **no external dependencies**.

-----

## Tech Stack

This project is intentionally lightweight and has no external dependencies.

  * **Technology:** Python 3.6+
  * **Standard Libraries Used:**
      * `os`: For walking directory structures and handling paths.
      * `fnmatch`: For matching file/directory names against `gitignore`-style patterns (e.g., `*.log`, `build/*`).
      * `typing`: For type hinting and cleaner code.

-----

## How to Use

1.  **Save the Script:** Save the Python code as `snapshot.py` (or any name you prefer) on your computer. It can be placed anywhere.
2.  **Open Your Terminal:** Open your preferred command line (e.g., Terminal, PowerShell, CMD).
3.  **Run the Script:**
    ```bash
    python path/to/snapshot.py
    ```
4.  **Enter Project Path:** The script will first ask for the path to your project's root directory.
    ```
    Please enter the path to the root directory of your project: C:\Users\YourName\Projects\my-web-app
    ```
5.  **Handle Exclusions:** The script will then check for a `.gitignore` file.
      * **If `.gitignore` is found:** It will ask if you want to use its rules.
        ```
        A .gitignore file was found...
        Do you want to add its rules to the exclusion list? (yes/no): yes
        ```
      * **If no `.gitignore` is found (or you say "no"):** It will ask if you want to add patterns manually.
        ```
        No .gitignore file found...
        Do you want to manually add exclusion patterns? (yes/no): yes
        Please enter patterns to exclude...: *.log, *.tmp, dist
        ```
6.  **Get the Output:** The script will process all the files and create `project_snapshot.txt` **in the same directory where you ran the `snapshot.py` script.** You can now open this file, copy its contents, and paste it into your AI model.

### Example Output (`project_snapshot.txt`)

The generated file will look like this, making it easy for both humans and AI to read:

```plaintext
    main.py
    ```
    import os
    from my_app import create_app

    app = create\_app(os.getenv("CONFIG\_TYPE"))

    if name == "main":
        app.run()
    ```

    src/handlers/users.js
    ```
    // User handler file

    function getUser(id) {
    // logic to get user
    return { id, name: "Test User" };
    }

    export { getUser };
    ```


    README.md
    ```
    # My Web App

    This is a test project.
    ```

```

---

## Key Functions Explained

This script is built around three main functions:

### `parse_gitignore(gitignore_path: str) -> Set[str]`

* **Purpose:** Reads a `.gitignore` file and converts its rules into a set of patterns.
* **How it works:** It opens the file, reads each line, and strips whitespace. It ignores empty lines and comments (lines starting with `#`). It returns a `set` of patterns (e.g., `{'*.log', 'node_modules', '/build'}`).

### `get_user_exclusions() -> Set[str]`

* **Purpose:** An interactive function to get exclusion patterns directly from the user.
* **How it works:** It prompts the user for a comma-separated string of patterns. It then splits this string and cleans up each pattern, returning them as a `set`.

### `create_project_snapshot(root_dir: str, exclude_patterns: Set[str], output_file_path: str)`

* **Purpose:** This is the main engine of the script. It traverses the project and builds the output file.
 
* **How it works:**
    1.  It uses `os.walk(root_dir, topdown=True)` to traverse the directory tree.
    2.  **Key Optimization:** Using `topdown=True` allows us to "prune" directories. We modify the `dirnames` list *in-place* to remove directories that match our `exclude_patterns`. This prevents `os.walk` from ever descending into them (e.g., it won't even *look* inside `node_modules`), saving massive amounts of time.
    3.  For each file, it checks if the filename or its relative path (e.g., `src/temp/test.log`) matches any exclusion pattern using `fnmatch`.
    4.  If a file is not excluded, it attempts to read it as `utf-8` text. If it fails (throwing a `UnicodeDecodeError`), it assumes the file is binary and skips it.
    5.  It formats the file's `relative_path` and `content` into the desired string block and appends it to a list.
    6.  Finally, it joins all blocks and writes the complete string to the `output_file_path`.

---

## Contributing

Feel free to fork this project, suggest improvements, or open an issue. All contributions are welcome!

## License

This project is released under the **MIT License**. See the [`LICENSE`](./LICENSE) file for details.