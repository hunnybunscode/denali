import yaml
from dataclasses import dataclass
from typing import List

@dataclass
class Subnet:
    subnet_id: str
    availability_zone: str

@dataclass
class Networking:
    vpc_id: str
    subnets: List[Subnet]
    security_group_id: str

@dataclass
class Config:
    namespace: str
    region: str
    version: str
    networking: Networking

def get_configs(config_file: str) -> Config:
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    networking = Networking(
        vpc_id=config['networking']['vpc_id'],
        subnets=[Subnet(**s) for s in config['networking']['subnets']],
        security_group_id=config['networking']['security_group_id']
    )
    
    return Config(
        namespace=config['namespace'],
        version=config['version'],
        region=config['region'],
        networking=networking
    )
