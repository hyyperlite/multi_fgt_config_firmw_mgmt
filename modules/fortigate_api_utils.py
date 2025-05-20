from pyFGT.fortigate import *
import base64
import sys


# Prepare fg config file for restore
def file_to_b64(my_file):
    try:
        with open(my_file, 'rb') as f:
            f64 = base64.encodebytes(f.read())
            f64_clean = f64.decode('ASCII').replace('\n', '')
    except IOError as e:
        print('Error opening file or converting to base64')
        raise Exception
    return f64_clean


class FortiGateApiUtils:
    # Class Constants
    API_TIMEOUT = 30
    API_DIS_REQ_WARNINGS = True

    # class initializer
    def __init__(self, device: dict = None, verbose: bool = True, debug: bool = True):
        self.verbose = verbose
        self.debug = debug
        self.device = device

        if 'apikey' in device:
            self.api = FortiGate(device['ip'], device['login'], apikey=device['apikey'], debug=debug,
                                 disable_request_warnings=FortiGateApiUtils.API_DIS_REQ_WARNINGS,
                                 timeout=FortiGateApiUtils.API_TIMEOUT)
        elif 'password' in device:
            self.api = FortiGate(device['ip'], device['login'], passwd=device['password'], debug=debug,
                                 disable_request_warnings=FortiGateApiUtils.API_DIS_REQ_WARNINGS,
                                 timeout=FortiGateApiUtils.API_TIMEOUT)
        else:
            raise Exception('Neither "passwd" nor "apikey" were provided, must define one of these.')

    # Stringify the class instance
    def __str__(self):
        # Return all instance variables as string
        return str(vars(self))

    # API login to FG
    def login(self):
        r = self.api.login()
        # pyfgt login doesn't seem to validate that the apikey is valid on the target host
        # thus we run a quick api get call to verify authentication before return result
        if self.api.api_key_used:
            print('using apikey')
            self.api.debug = False # Since this is not a user requested check we want to not output debug to stdout
            code, msg = self.api.get('monitor/system/status')
            self.api.debug = self.debug  # reset the debug status to whatever was last defined
            if code == 'success':
                return True, 'Connected'
            else:
                return False, 'Likely, the apikey was not verified/authenticated by FG'
        else:
            if 'instance connnected' in str(r):
                return True, 'Connected'
            else:
                return False, "Error logging in to FG (check IP, password, etc)"

    # API logout from FG
    def logout(self):
        try:
            self.api.logout()
        except FGTBaseException:
            return False, 'Something failed, oh well, probably can ignore since is logout'
            pass

    # Method to get FG instance backup and write it to backup_dir with timestamp and tag
    def backup_to_file(self, backup_dir, date: str = '', file_tag: str = ''):
        response = self.api.post('/monitor/system/config/backup', 'scope=global')
        # Need to extract data from response object at second position of returned tuple

        # Very simple check for validity of returned file
        config = response[1].content.decode('ASCII')
        if not config.startswith('#config-version'):
            return False, 'Backup file check, file may not be valid config'

        # Open file for writing and write config to file
        try:
            with open(f'{backup_dir}/{date}{self.device["name"]}{file_tag}.conf', 'w+') as backup_file:
                backup_file.write(config)
        except IOError as e:
            return False, f'Error writing backup file: {e}'
        return True, f'{backup_dir}/{date}{self.device["name"]}{file_tag}.conf'

    # Method to execute upgrade of fgt instance
    def upgrade_image(self, image_source: str = 'fortiguard', img_ver_rev: str = None):
        if not img_ver_rev:
            raise Exception('var "img_ver_rev" is required by was not supplied')

        if image_source == 'fortiguard':
            if self.verbose:
                print(f'<<< Starting upgrade from FortiGuard >>>')

            # Query current available firmware from fortiguard available to this device
            code, msg = self.api.get('/monitor/system/firmware')

            # Check if current version is same as requested version and exit if so
            if msg['results']['current']['version'].lstrip('v') == img_ver_rev:
                return True, f"Version requested {img_ver_rev }is same as current version, skipping"

            # Split requested version var (img_ver_rev) to major, minor, patch vars
            os_major, os_minor, os_patch = img_ver_rev.split(".")

            # Identify if requested versions available on this device through fortiguard
            for avail_ver in msg['results']['available']:
                if avail_ver['major'] == int(os_major) and avail_ver['minor'] == int(os_minor) and \
                        avail_ver['patch'] == int(os_patch):

                    if self.verbose:
                        print(f'  Found available image {avail_ver["version"]} with ID: {avail_ver["id"]}')
                        print(f'  Initiating upgrade with image ID: {avail_ver["id"]}: ', end='')

                    code, msg = self.api.post('/monitor/system/firmware/upgrade', vdom='root', source='fortiguard',
                                              filename=avail_ver["id"])

                    if msg['results']['status'] == 'success':
                        return True, msg
                    else:
                        return False, f'Upgrade request for image id {avail_ver["id"]} failed {msg}'
                else:
                    return False, f'No image found for {img_ver_rev} for this device'
        else:
            # Read image file, base64 encode it then convert to string
            try:
                img64 = file_to_b64(img_ver_rev)
            except Exception as e:
                print('Unable to either read image  file or convert it to base64')
                sys.exit()

            # Upgrade firmware image
            print(f'  Sending image {image_source} to {self.device["name"]}: ', end='')

            self.api.timeout = 600
            code, msg = self.api.post('/monitor/system/firmware/upgrade', vdom='root', source='upload',
                                          scope='global', ignore_invalid_sinature='true', file_content=img64)
            # Set timeout back to standard
            self.api.timeout = 30
            # code, msg = json.loads(json_response.decode())

            return code, msg

    #  Upload config for restore
    def restore_config_from_file(self, config_file: str):
        # FG API does not allow to restore using standard admin user with password
        # must use api user and then via cli set the api user to super admin privs.
        # We will check here to verify if using api key to login at a minimuim.
        if 'apikey' in self.device:
            # Check if API key is string
            if isinstance(self.device['apikey'], str):
                # Convert config string to b64 (and remove whitespace)
                b64_file = file_to_b64(config_file)

                # Upload config to restore
                code, msg = self.api.post('/monitor/system/config/restore', source='upload',
                                          scope='global', file_content=b64_file)

                if code == 'success':
                    return True, msg
                else:
                    return False, msg

        # If apikey not provided or is not string will fall to this
        return False, 'Must use apikey to restore config file'