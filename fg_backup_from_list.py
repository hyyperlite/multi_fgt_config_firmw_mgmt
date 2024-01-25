"""
Nick Petersen  77npete@gmail.com

Receive a list of FortiGates including hostname/IP, admin user, password and/or apikey
For each fortigate in the list get config backup via api call and store that config to file.

By default, a new directory will be created under the defined backup_dir directory for each run
and the backup files will all be created red within that new directory.  Optionally, new files
can all be stored in the defined backup_dir without new subdirectories created.
Use "--create_new_dir false" in cli arguments to use the  alternate behavior.

Additionally, a file containing a list of words (one per line) can be provided with --skip_list argument.
The words in this list will be compared against the names of each FG defined in the yaml file.
If any of the names for the FGs contains the words in the skip list, the script will not attempt to
back up that FG device. (This skip_list is primarily used to avoid attempting to back up device in the
file which may not actually be a fortigate device.)

The device yaml file needs to support format like:
------------------------------------------
fortigates:
  fg-1:
     ip: 192.168.1.1
     apikey: nGcsNy89z9Q9bGrm8f4Nps5pxnbQN0
  fg-2:
    ip: 192.168.1.2
    login: admin
    password: fortinet
  fg-3:
    ip: 192.168.1.3
    login: admin
    password: fortinet
    apikey: ghhwmpbd89Hj14563gj4s84r709sr0
------------------------------------------
Where in the above the ip is required, if using login/password api auth then the login & password attribute is required.
If using api key to log in then apikey is required.   If login, password and apikey is all defined then apikey will
be used over login/password for api calls. Also note, that other attributes may be defined under each fortigate
attribute and will be ignored.  Additionally, other top level attributes besides "fortigates" may be defined and will
be ignored.

Additionally, for backups, in the device yaml file a lab_name attribute can be defined. 
This will be used "if defined", in the file or directory naming for the resulting device backup files.
This is used if --lab_name_from is passed with "yaml" value.  Otherwise by default user is prompted for this info.
------------------------------------------
lab_name: "this_is_my_lab_name"
"""

from modules.fortigate_api_utils import *
from modules.common import *
import argparse
from str2bool import str2bool
import os
import sys
import datetime


# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--device_file', default=None, type=str, help="yaml file with device details")
parser.add_argument('--yaml_dir', default=None, type=str, help='Instead of --device_file may pass a directory containing yaml files, \
                       will then be prompted to select a file from this directory at runtime.')
parser.add_argument('--backup_dir', type=str, default=None, help='directory to put backups in')
parser.add_argument('--create_new_dir', type=str2bool, default=True,
                       help='If true, create a new directory for backups each time script is run')
parser.add_argument('--lab_name_from', type=str, choices=['none', 'prompt', 'yaml'], default='prompt', \
                       help='Optionally for detailed backup directory naming, provide lab name via one of: \
                             none="just use date/time", \
                             prompt="prompt user input on cli" \
                             yaml="get lab name from lab_name param in device yaml file"')
parser.add_argument('--debug', type=str2bool, default=False, help='Flag, enable debug output for API calls')
parser.add_argument('--verbose', type=str2bool, default=False, help='Flag, output operational details')
parser.add_argument('--skip_list', type=str, default=None,
                       help='Optionally, provide path to file with list of words in which if the word is in the name '
                            'of any of the device\'s names in yaml file, backups for that device will be skipped. '
                            'If not defined, no name checks will be performed')
args = parser.parse_args()

#######################
# Main
#######################
if __name__ == '__main__':
    # Check if --device_file or --yaml_dir parameters passed
    if not args.device_file:
        if args.yaml_dir:
            # From modules/common call user_file_selection function
            # This will get a list of files in --yaml_dir directory and prompt user to select one
            args.device_file = user_file_selection(args.yaml_dir)
        else:
            print("Must provide one of following parameters --device_file or --yaml_dir, Aborting")
            raise SystemExit

    if args.backup_dir:
        # Make sure the target backup folder path exists, if provided. 
        if not os.path.exists(args.backup_dir):
            print(f"Error backup directory path {args.backup_dir} is not valid, Aborting")
    else:
        # If --backup_dir not provided as parmeter then prompt user for the path, validate it, then move on
        # From modules/common call get_user_dir_path
        args.backup_dir = get_user_dir_path('Backup')

    # Read device details from file
    # From modules/common call read_device_file
    fgs = read_device_file(args.device_file)
    if not fgs:
        print("!!! Failed to read device file.  Aborting")
        raise SystemExit

    # list of words that if in name of fg device then we will skip that device
    if args.skip_list:
        try:
            with open(args.skip_list) as f:
                skip_list = f.readlines()
        except IOError as e:
            print(f'Error reading skip list, aborting: {e}')
            sys.exit()

    # Some logic for some file tagging options that can be derived from the yaml file
    if args.lab_name_from == 'yaml' and 'lab_name' in fgs:
            lab_name = fgs['lab_name']

    if args.lab_name_from == 'prompt':
        print('Enter lab name for use in file naming (concise)')
        lab_name = input('Lab name > ')
        print()

    # Set tag for use in backup folder name
    date_tag = f'{datetime.date.today()}-{datetime.datetime.now().strftime("%H%M%S")}'
    if lab_name:
        backup_tag = f'-{lab_name}'
    else:
        backup_tag = ''

    if args.create_new_dir:
        backup_dir = f'{args.backup_dir}/{date_tag}{backup_tag}'
        # date tag and backup tag used in dir name, so don't need in file name, reset these vars
        date_tag = ''
        backup_tag = ''

        try:
            os.mkdir(backup_dir)
        except (OSError, FileExistsError) as e:
            print(f'Unable to create new backup directory {backup_dir}, {e}, aborting')
            sys.exit()
    else:
        backup_dir = args.backup_dir

    # Process each entry under fortigates in yaml file
    for fg in fgs['fortigates']:
        print(f'Backup: {fg} at IP {fgs["fortigates"][fg]["ip"]}: ', end='')

        # Check to see if name of fg contains a word we want to skip, then skip
        if args.skip_list:
            if any(skip_word in fg for skip_word in skip_list):
                print(f' Skipping, {fg} appears to be non-fortigate device')
                continue

        # Create a dictionary of details for the current fg
        device_details = fgs['fortigates'][fg]
        if 'name' not in device_details:
            device_details['name'] = fg

        # Create instances of fg_api_utils with device details
        fgt = FortiGateApiUtils(device=device_details, verbose=args.verbose, debug=args.debug)
        try:
            r, msg = fgt.login()
        except Exception as e:
            print(f'Failed to login to FGT: \n  {e}')
            continue

        if r is False:
            print(f'Failed {msg}')
            continue

        # Execute backup using fortigate_api_utils.backup_to_file
        try:
            result, msg = fgt.backup_to_file(backup_dir=backup_dir, date=date_tag, file_tag=backup_tag)
        except (FGTBaseException, FGTValueError) as e:
            print(f'Error initiating backup API call to FG: \n  {e}')
            continue

        if result:
            print('Success')
            if args.verbose:
                print(f'  file-> {msg}')
        else:
            print(f'Failed {msg}')
