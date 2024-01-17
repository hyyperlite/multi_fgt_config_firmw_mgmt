## Manage configs and firmware of multiple FortiGates via API ##

All scripts take a path to a yaml file as an argument.  Yaml file contains a list of fortigates along with IP and login info.  The login info must include "login" and either "apikey" or "password".

The fg_restore_from_list.py and fg_update_firmware_from_list.py scripts in order to perform the intended function must use apikey login.  This is due to fortigate security requirements. Thus there is a the fg_api_key_gen.py script.  This script will login to FG via username/password using SSH (required) to add an api user and retrieve apikey and add that key to the yaml file.

(further documentation to come)
