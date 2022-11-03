import os

import yaml


def versions_to_folders(package):
    """Given a package, return a mapping of version number to recipe folder"""
    recipe_folder = os.path.join('recipes', package)
    config_yml_file = os.path.join(recipe_folder, 'config.yml')
    if os.path.exists(config_yml_file):
        with open(config_yml_file, 'r') as config_yml:
            config_data = yaml.safe_load(config_yml)
            return {version: os.path.join(recipe_folder, data['folder'])
                    for version, data in config_data['versions'].items()}
    else:
        with os.scandir(recipe_folder) as dirs:
            def valid(entry):
                return not entry.name.startswith('.') and entry.is_dir()

            return {entry.name: os.path.join(recipe_folder, entry.name) for entry in dirs if valid(entry)}
