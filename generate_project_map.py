import os


def generate_project_map(start_path='.', output_file='project_map.txt'):
    """
    Generate a tree-like map of the project directory structure and save it to a file.

    Args:
        start_path (str): The starting directory (default is current directory).
        output_file (str): The name of the output file to save the map.
    """

    def print_directory(path, prefix='', file_handle=None):
        """
        Recursively print the directory structure with proper indentation.

        Args:
            path (str): Current directory path.
            prefix (str): Prefix for indentation in the tree structure.
            file_handle: File handle to write the output.
        """
        try:
            # Get all entries in the directory
            entries = sorted(os.listdir(path))
            for index, entry in enumerate(entries):
                if entry.startswith('.'):  # Skip hidden files/folders (e.g., .git, .idea)
                    continue
                entry_path = os.path.join(path, entry)
                is_last = index == len(entries) - 1
                # Use different symbols for the last item in the list
                current_prefix = prefix + ('└── ' if is_last else '├── ')

                # Write the current entry
                file_handle.write(current_prefix + entry + '\n')

                # If it's a directory, recurse into it
                if os.path.isdir(entry_path):
                    # Adjust prefix for nested items
                    next_prefix = prefix + ('    ' if is_last else '│   ')
                    print_directory(entry_path, next_prefix, file_handle)
        except PermissionError:
            file_handle.write(prefix + '├── [Permission Denied]\n')
        except Exception as e:
            file_handle.write(prefix + f'├── [Error: {str(e)}]\n')

    # Ensure the start_path is valid
    start_path = os.path.abspath(start_path)
    if not os.path.exists(start_path):
        print(f"Error: The path '{start_path}' does not exist.")
        return

    # Open the output file and generate the map
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Project Map for {start_path}\n")
        f.write('.\n')
        print_directory(start_path, '', f)

    print(f"Project map has been generated and saved to '{output_file}'.")


if __name__ == "__main__":
    # Example usage: Generate map for the current project directory
    generate_project_map()