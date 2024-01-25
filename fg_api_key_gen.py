"""
Created by: Nick Petersen (hyyperlite@gmail.com)

Due to security restrictions in the FortiGate REST API, it is not possible
to execute certain actions or configuration options when using the API with
admin/password instead of via api key.

Limitations with admin/passwd api login happen to include that you cannot 
create accprof (admin profiles) and you cannot create api-user(s). 
Other limitations include that you cannot upgrade firmware or restore
configuration without accessing api via api key. Typically in these
cases you will see 403 error messages.

These limitations make it difficult to upgrade or restore a config to
devices unless an api user with the propper read-write account profile
access exists.  If you want to do all of your config, restores, upgrades
via API then you are just stuck. 

This script will use API to check to see if specific accprof and api-user
exist.  If they do not, it will use SSH (paramiko) to SSH to the FG, login
with admin/password and create the necessary accprof and api-user;
and generate/retrieve an api key for the device.

Note: For restoring config to FG, you must user pre-existing "super_admin" accprof.
Thus "super_admin" is the default. If you use the default "super_admin" accprof, then
checking for its existence are skipped because it is default and cannot be deleted in FG.

The script takes a file in yaml format with a list of fortigates, including
mgmt ip, login, password information.  Will login to each and create the
previously described accprof, api-user and get the api key.  It will then write
the API key as a parameter in the fg yaml file so that the key may be used for
api access in other programs.

I had hoped to assign the api key to a value that could be the same across all FGs
in my yaml list.  However, although the cli option exists to set a key manually, 
it always gives error when try to set it manually.  Thus must generate and record it.
"""

from modules.common import *
from pyFGT.fortigate import *
import argparse
import paramiko
import urllib3
import shutil
from str2bool import str2bool

# Argument processing
parser = argparse.ArgumentParser()
parser.add_argument('--device_file', default=None, help='path to yaml file with device details')
parser.add_argument('--yaml_dir', default=None, help='Instead of --device_file may pass a directory containing yaml files \
                      will then be prompted to select a file from this dir at runtime.')
parser.add_argument('--api_user', help='Fortigate api-user')
parser.add_argument('--accprof', default='super_admin', help='Fortigate account profile (accprof) to apply to api-user')
parser.add_argument('--vdom', default='root', help='specify vdom for api-user if other than "root" this may be a list\
                                                    of vdoms each separated by spackes')
parser.add_argument('--skip_list', help='Path to file containing words that if match in fg name then skip that fg')
parser.add_argument('--debug', type=str2bool, default=False, help='Enable debug output for API (pyfgt) request/response')
parser.add_argument('--verbose', type=str2bool, default=False, help='Enable more verbose output')
args = parser.parse_args()

# Some variables for use with API (pyfgt)
api_timeout = 30
api_dis_req_warnings = True

args.verbose = False # Verbosity with paramiko input/output not yet working, so overriding this argument

def get_accprof(my_api, my_accprof):
    """
    Use api to FG to get specific accprof from fg.  If it exists
    return the details of the accprof, otherwise return false.
    """
    # Check if the requested admin profile is configured on the FG
    code, msg = my_api.get(f'cmdb/system/accprofile/{my_accprof}') 
    if code == 200:
        return msg
    else:
        return False

def get_api_user(my_api, my_api_user):
    """
    Use api to FG to get specfic api-user from fg.  If it exists
    return the detail of the api-user, otherwise return false.
    """
    code, msg = my_api.get(f'cmdb/system/api-user/{my_api_user}') 
    if code == 200:
        return msg
    else:
        return False

def check_vdom_mode(my_api):
    """ Use API to check currently configured vdom mode and return it """
    code, msg = my_api.get('cmdb/system/global')
    if msg['results'].get('vdom-mode') == 'no-vdom':
        return False
    else:
        return True

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

    # Read device details from file
    fgs = read_device_file(args.device_file)
    if not fgs:
        print("!!! Failed to read device file.  Aborting")
        raise SystemExit

     # List of words that if in name of fg device then we will skip that device
    if args.skip_list:
        try:
            with open(args.skip_list) as f:
                skip_list = f.readlines()
        except IOError as e:
            print(f'Error reading skip list, aborting: {e}')
            raise SystemExit

    # Process each entry under fortigates in yaml file
    for fg in fgs['fortigates']:
        print(f'Processing: {fg} at ip {fgs["fortigates"][fg]["ip"]}: ')

        # Check to see if name of fg contains a word we want to skip, then skip
        if args.skip_list and any(skip_word in fg for skip_word in skip_list):
            print(f' Skipping: {fg} appears to be non-fortigate device (skip_list)')
            continue

        # Just to make it easier later, add the details of this fg to fg_info
        # Allows to not have to reference keys/values with long fgs['fortigates'][fg]['key']
        fg_info = fgs['fortigates'][fg]

        # Check that the data necessary for API and SSH access exists in the fg_info dict()
        if not 'ip' in fg_info :
            raise ValueError('"ip" not defined for FG')
        if not 'login' in fg_info:
            raise ValueError('"login" not defined for FG')
        if not 'password' in fg_info:
            raise ValueError('"password" not defined for FG')

        # Instantiate pyfgt object
        api = FortiGate(fg_info['ip'], fg_info['login'], passwd=fg_info['password'], debug=args.debug,
                        disable_request_warnings=api_dis_req_warnings, timeout=api_timeout)

        # Attempt login to FG API to check valid
        try:
            api.login()
        except (FGTConnectionError, FGTConnectTimeout) as e:
            print(f'  Login to FG failed: {e}, continue to next FG if any')
            continue

        # Check to see if if fg is in vdom mode
        # If it is, then add config global and end to pre/post cmds
        if check_vdom_mode(api):
            vdom_mode = True
            print('  vdom-mode is: multi-vdom')
            pre_cmd = 'config global\n'
            post_cmd = 'end\n'
        else:
            vdom_mode = False
            print('  vdom-mode is: no-vdom ')
            pre_cmd = ''
            post_cmd = ''

        # Create Paramiko SSH connection
        # Even if accprof and api-user exist (identified by api calls)
        # we will need to re-generate the api key via SSH
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(fg_info['ip'], username=fg_info['login'], password=fg_info['password'])
        
        # If the profile does not exist then create it via SSH
        print(f'  Check for account profile "{args.accprof}": ', end='')
        if args.accprof == 'super_admin':
            print('Found')
        else:
            if get_accprof(api, args.accprof):
                print('Found')
            else:
                print('Not Found')
                print(f'    Create acccprofile "{args.accprof}" via SSH:', end='')
                # Command to create rw accprof
                cmd = f"""
                    config system accprof
                    edit {args.accprof}
                    set secfabgrp read-write
                    set ftviewgrp read-write
                    set authgrp read-write
                    set sysgrp read-write
                    set netgrp read-write
                    set loggrp read-write
                    set fwgrp read-write
                    set vpngrp read-write
                    set utmgrp read-write
                    set wanoptgrp read-write
                    set wifi read-write
                    next
                    end
                    
                """
                # SSH execute create accprof cmd
                _stdin, _stdout, _stderr = client.exec_command(pre_cmd + cmd + post_cmd)

                # Check via API if accprofile now exists
                if get_accprof(api, args.accprof):
                    print('Success')    
                else:
                    print('Failed')
                    print('  Moving to next FG if any')
                    continue

        # Check existence of, and, if needed, add api-user
        print(f'  Add/update api-user "{args.api_user}": ', end='')
        cmd = f"""
            config system api-user
            edit {args.api_user}
            set accprofile {args.accprof}
            set vdom {args.vdom}
            next
            end

        """

        # SSH execute create accprof cmd
        _stdin, _stdout, _stderr = client.exec_command(pre_cmd + cmd + post_cmd)

        # Check via api if api-user now exists
        result = get_api_user(api, args.api_user)
        if result:
            if result['results'][0].get('accprofile') == args.accprof:
                print('Success')    
            else:
                print('Failed')
                print('  Moving to next FG, if any are left...')
        else:
            print('Failed')
            print('  Moving to next FG, if any are left...')
            continue

        # Execute api keygen via SSH
        print(f'  Generate and retrieve API key for {args.api_user} via SSH: ', end='')
        cmd = f'execute api-user generate-key {args.api_user}\n'
        _stdin, _stdout, _stderr = client.exec_command(pre_cmd + cmd + post_cmd)
        result = _stdout.read().decode()

        if 'New API key:' in result:
            # SSH command causes multiple lines of response, need to pull out the api key from it.
            # The response is on a different line when vdom mode vs no vdom.
            if vdom_mode:
                apikey = result.splitlines()[2].rsplit(' ', 1)[1]
            else:
                apikey = result.splitlines()[1].rsplit(' ', 1)[1]

            if len(apikey) == 30:
                print(f'{apikey}')

                # Update the fg device info dictionary with the new apikey
                fgs['fortigates'][fg]['apikey'] = apikey

            else:
                print("Failed")

        else:
            print('Failed')

        # Close out connections to FG
        api.logout()
        client.close()


    print('########################################')

    # Copy original device file to <original_file>.orig
    print(f'Copy original device file to {args.device_file}.orig')
    try:
        shutil.copy(args.device_file, f'{args.device_file}.orig')
    except (shutil.Error):
        print('Could not copy device file for safe keeping')

    # Overwrite device file with same details plus new apikeys
    print('Overwite device file with new details to include apikey')
    try:
        with open(args.device_file, 'w') as f:
            yaml.dump(fgs, f)
    except (FileNotFoundError, FileExistsError) as e:
        print(f'!!! ERROR Writing File {e}')

    print('########################################')

