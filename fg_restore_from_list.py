"""
Nick Petersen  77npete@gmail.com

Receive a list of FortiGates including hostname/IP and apikey. (list via yaml file only currently)

Note: FortiGate does not allow an API session authenticated with admin login & password to execute
a system restore.  For this an "api user" defined on FG must be created with read/write privileges.
as a result, this script first checks that an apikey was provided (not just admin/passwd).

For each fortigate in the list look for possible matching configurations in the defined
backup directory (--backup_dir).

The device yaml file needs to support format like:
----------------
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
"""

from modules.fortigate_api_utils import *
from modules.common import *
import argparse
from str2bool import str2bool
import yaml
import os
import sys


# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--device_file', type=str, default='data/yaml/fgsp_vlans.yml')
parser.add_argument('--backup_dir', type=str, default='data/backups/2023-12-22-114336-fgsp_vlans')
parser.add_argument('--debug', type=str2bool, default=False, help='Flag, enable debug output for API calls')
parser.add_argument('--verbose', type=str2bool, default=False, help='Flag, output operational details')
parser.add_argument('--skip_list', type=str, default=None,
                    help='Optionally, provide path to file with list of words which if the word is in the name '
                         'of any of the devices names in yaml file, backups for that device will be skipped. '
                         'If not defined, no name checks will be performed')
args = parser.parse_args()

# Initialize vars
config_file = False

#######################
# Main
#######################
if __name__ == '__main__':
     # Read device details from file
    fgs = read_device_file(args.device_file)
    if not fgs:
        print("!!! Failed to read device file.  Aborting")
        raise SystemExit 

    # Get list of files in backup_dir
    try:
        restore_files = os.listdir(args.backup_dir)
    except OSError as e:
        print(f'Error opening config file directory {args.backup_dir}, aborting: {e}')
        sys.exit()
    if args.verbose:
        print(f'Configurations List: {restore_files}')

    # list of words that if in name of fg device then we will skip that device
    if args.skip_list:
        try:
            with open(args.skip_list) as f:
                skip_list = f.readlines()
        except IOError as e:
            print(f'Error reading skip list, aborting: {e}')
            raise SystemExit

    # Process each entry under fortigates in yaml file
    for fg in fgs['fortigates']:
        print(f'Processing {fg} at IP: {fgs["fortigates"][fg]["ip"]}')

        # Check if apikey is defined and is a string.  If not, stop processing
        # this fortigate as cannot do restore unless using apikey for auth.
        if 'apikey' not in fgs['fortigates'][fg]:
            print('  Error: no apikey defined.  Restore of config requires apikey login on FG')
            continue

        # Check to see if name of fg contains a word we want to skip, then skip
        if args.skip_list and any(skip_word in fg for skip_word in skip_list):
            print(f' Skipping: {fg} appears to be non-fortigate device (skip_list)')
            continue

        # Create a dictionary of details for the current fg
        device_details = fgs['fortigates'][fg]
        device_details['name'] = fg

        # If we can find a config file containing the device's name, then select that file
        for cfile in restore_files:
            if args.verbose:
              print('  Comparing:')
              print(f'    {fg} --> {cfile}')

            if fg in cfile:
                config_file = f'{args.backup_dir}/{cfile}'
                print(f'  Restore Config:   {config_file}')
                break
            else:
                config_file = None

        if config_file:
            """ Create instances of fg_api_utils with device details """
            fgt = FortiGateApiUtils(device=device_details, verbose=args.verbose, debug=args.debug)
            try:
                r, msg = fgt.login()
            except (FGTBaseException, FGTValueError, FGTConnectionError) as e:
                print(f'  Connection/Login Failed: {e}')
                continue

            # If login appears to have worked then continue to request restore
            if r is True:
                try:
                    result, msg = fgt.restore_config_from_file(config_file=config_file)
                except (FGTBaseException, FGTValueError, FGTConnectionError) as e:
                    print(f'  API Call to FGT Failed: {e}')
                    continue

                if result:
                    print(f'  Success')
                else:
                    print(f'  Failed: {msg}')

            else:
                print(f'  Failed: {msg}')
        else:
            print('  Error: No Config file match found.')
