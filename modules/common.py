import yaml

def read_device_file(dev_file, type='yaml'):
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