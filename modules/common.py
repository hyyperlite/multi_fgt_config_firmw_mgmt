import yaml
import os
import platform

def read_device_file(dev_file, type='yaml'):
    """
    Read yaml and return as dict()
    """
    if type != 'yaml':
        raise NotImplementedError('Only YAML type device files are currently supported') 
    try:
        # Open device yaml file for reading.
        with open(dev_file) as file:
            try:
                # Read yaml file to python dict()
                fgt_details = yaml.safe_load(file)

            except yaml.YAMLError as e:
                print(f'Error processing device yaml file: {e}')
                return False
        
            return fgt_details
        
    except IOError as e:
        print(f'Error reading device yaml file: {e}')
        return False


def user_file_selection(fdir):
    """
    Get a list of files from input directoory 'fdir'
    Request input from user via CLI to select one of the files
    """
    # List to track indexes in directory file list
    fdir_idx = []
    # Get list of files in backup_dir
    try:
        fdir_files = os.listdir(fdir)
    except OSError as e:
        print(f'Error opening device file directory {fdir}, aborting: {e}')
        raise SystemExit

    print('Select a device file to use for this operation:')
    for f in fdir_files:
        fdir_idx.append(str(fdir_files.index(f)))
        print(f'  [{fdir_files.index(f)}] {f}')

    print('  [Q] Quit this program')

    valid_input = False
    # Until user provides valid selection, keep re-running
    while valid_input is False:
        # Get selection input from CLI
        try:
            uinput = input('Enter Selection: ')
        except Exception as e:
            print(f'Failed to process input {e}, Aborting')

        # User input validation
        print()
        if uinput not in fdir_idx and uinput.upper() != "Q":
            print(f'!!! You must select/input one of {fdir_idx[0]} - {fdir_idx[-1]} or "Q":')
        else:
            # If user input is Q then exit program
            if uinput.upper() == "Q":
                print("Goodbye")
                raise SystemExit

        valid_input = True

    return f"{fdir}/{fdir_files[int(uinput)]}"

def get_user_dir_path(dir_type):
    """
    Prompt user to provide directory path.  Validate the path and return it.
    """
    input_valid = False
    print(f'Input {dir_type} directory path or "Q" to quit:')
    while not input_valid:
        try:
            uinput = input('Enter path > ')
            print()
        except Exception as e:
            print('Unable to get/process user input, Aborting')
            print()

        # Quit if user input is q or Q
        if uinput.upper() == 'Q':
            print("Goodbye")
            raise SystemExit

        # Validate folder exists
        if os.path.exists(uinput.lstrip().rstrip()):
            input_valid = True
        else:
            print(f"Note: This program is running from {platform.system()} path should be in {platform.system()} format")
            print("Directory provided does not exist.  Enter another path or 'Q' to quit")
            print()

    return uinput