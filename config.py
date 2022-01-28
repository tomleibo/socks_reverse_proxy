import logging

config = {
    'debug_level': 'DEBUG',
    'log_level': logging.INFO,
    'db_host': '127.0.0.1',
    'db_name': 'appX',
    'fcm_api_key': '',
    'peer_server_port': 8000,
    'frontend_port': 8443,
    'min_port_range': 1025,
    'max_port_range': 4000,
    'max_threads': 200,
    'country_to_port': {'N/A': 1234, 'BE': 2000, 'DE': 3000, 'LU': 4000, 'SE': 5000, 'NL': 6000, 'AE': 7000},
    'service_whitelist_enabled': True,
    'service_whitelist': ['www.ipinfo.io']
}
