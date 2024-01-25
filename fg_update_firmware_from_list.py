"""
Nick Petersen  77npete@gmail.com

Receive a list of FortiGates including hostname/IP, login, password and/or apikey.
For each fortigate in the list attempt to upgrade the FG to the FOS image defined.

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
be used over login/password for api calls.  Also note, that other attributes may be defined under each fortigate
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
parser.add_argument('--device_file', type=str, help="yaml file with device data")
parser.add_argument('--yaml_dir', type=str, help='Instead of --device_file may pass a directory containing yaml files \
                      will then be prompted to select a file from this dir at runtime.')
parser.add_argument('--upgrade_source', type=str, choices=['file', 'fortiguard'])
parser.add_argument('--img_ver_rev', type=str, default=None,
                    help='The value assigned to this parameter will depend on the value selected in the '
                         '--upgrade_source attribute.  If --upgrade_source is set to "file" then this attributed'
                         'should be a filesystem path to an FOS image file.   If --upgrade_source is set to "fortiguard'
                         'then this attribute should be set to a value containing an FOS image versions such as'
                         '"7.2.6".')
parser.add_argument('--debug', type=str2bool, default=False, help='Flag, enable debug output for API calls')
parser.add_argument('--verbose', type=str2bool, default=False, help='Flag, output operational details')
parser.add_argument('--skip_list', type=str, default=None,
                    help='Optionally, provide path to file with list of words which if the word is in the name '
                         'of any of the devices names in yaml file, backups for that device will be skipped. '
                         'If not defined, no name checks will be performed')
args = parser.parse_args()

#######################
# Main
#######################
if __name__ == '__main__':
      # Check if --device_file or --yaml_dir parameters passed
    if not args.device_file:
        if args.yaml_dir:
            # from "common" module, call user_file_selection function
            args.device_file = user_file_selection(args.yaml_dir)
        else:
            print("Must provide one of following parameters --device_file or --yaml_dir, Aborting")
            raise SystemExit

    try:
        # Open device file for reading
        with open(args.device_file) as file:
            try:
                # read yaml file to python dict()
                fgs = yaml.safe_load(file)
            except yaml.YAMLError as e:
                print(f'Error processing device yaml file {e}, aborting')
                sys.exit()
    except IOError as e:
        print(f'Error reading device yaml file, aborting: {e}')
        sys.exit()

    # Check upgrade_source and img arguments to verify they correlate as expected
    if args.upgrade_source == 'file':
        if args.img_ver_rev:
            # Check if image file is accessible
            if not os.path.exists(args.img_ver_rev):
                print(f'Error, cannot access image file {args.img_ver_rev}, aborting')
                sys.exit()
        else:
            print(f'Error, upgrade_source request is "file", but no file path provided via --img, aborting')
            sys.exit()
    elif args.upgrade_source == 'fortiguard':
        os_major, os_minor, os_patch = args.img_ver_rev.split('.')
        if not 6 <= int(os_major) <= 7:
            print(f'Error version provided via --img {args.img_ver_rev} '
                  f'is not in range of FOS major version 6 or 7, aborting')
            sys.exit()
        if not 0 <= int(os_minor) << 4:
            print(f'Error version provided via --img {args.img_ver_rev} '
                  f'is not in range of FOS minor version 0 - 4, aborting')
            sys.exit()
        if not 0 <= int(os_patch) <= 20:
            print(f'Error version provided via --img {args.img_ver_rev} '
                  f'is not in range of FOS minor version 0 - 4, aborting')
            sys.exit()
    else:
        print(f'Unsupported --upgrade_source defined: {args.upgrade_source}, '
              f'currently only support "file" or "fortiguard", aborting')
        sys.exit()

    # If skip_list provided attempt to read the skip words to python list()
    if args.skip_list:
        try:
            with open(args.skip_list) as f:
                skip_list = f.readlines()
        except IOError as e:
            print(f'Error reading skip list, aborting: {e}')
            sys.exit()

    # Process each entry under fortigates in yaml file
    for fg in fgs['fortigates']:
        print(f'Upgrade {fg} at IP {fgs["fortigates"][fg]["ip"]}')

        # Check to see if name of fg contains a word we want to skip, then skip
        if args.skip_list and any(skip_word in fg for skip_word in skip_list):
            print(f' SKIPPING: {fg} appears to be non-fortigate device')
            continue

        # Create a dictionary of details for the current fg
        device_details = fgs['fortigates'][fg]
        device_details['name'] = fg

        # Check if apikey is defined and is a string.  If not, stop processing
        # this fortigate as cannot do restore unless using apikey for auth.
        if 'apikey' not in device_details:
            print('Error: no apikey defined.  Upgrading of image on FG requires apikey login (not user/pass)')
            continue

        """ Create instance of fg_api_utils with device details """
        fgt = FortiGateApiUtils(device=device_details, verbose=args.verbose, debug=args.debug)
        try:
            r, msg = fgt.login()
        except (FGTBaseException, FGTValueError, FGTConnectionError) as e:
            print(f'  Connection/Login Failed: {e}')
            continue

        # If login appears to have worked then continue to request restore
        if r is True:
            try:
                code, msg = fgt.upgrade_image(image_source=args.upgrade_source, img_ver_rev=args.img_ver_rev)
                print('#############')
                print(code)
                print(msg)
            except (FGTBaseException, FGTValueError, FGTConnectionError) as e:
                print(f'  API Call to FGT Failed: {e}')
                continue









