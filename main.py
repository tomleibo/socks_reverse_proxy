import os

from infrastructure.wrappers.fcm import Fcm
from infrastructure.wrappers.infra_logger import Logger

from connection_pool import ConnectionPool
from database import Database
from config import config
from frontend_server import FrontendServer
from offline_device_handler import OfflineDeviceHandler
from peer_server import PeerServer
from periodic_tasks import PeriodicTasks
from super_proxy import SuperProxy


def run(conf):
    logger = Logger("Main")
    logger.info(f'Running backend in {os.getcwd()}')
    db: Database = Database(conf['db_host'], conf['db_name'])
    connection_pool: ConnectionPool = ConnectionPool()
    fcm_wrapper: Fcm = Fcm(conf['fcm_api_key'])
    offline_device_handler: OfflineDeviceHandler = OfflineDeviceHandler(db, fcm_wrapper)
    peer_server: PeerServer = PeerServer(db, conf['peer_server_port'], connection_pool)
    peer_server.start()
    super_proxy: SuperProxy = SuperProxy(conf['country_to_port'], connection_pool, db)
    tasks: PeriodicTasks = PeriodicTasks(db)
    tasks.start()
    frontend: FrontendServer = FrontendServer(conf['frontend_port'], connection_pool, offline_device_handler, super_proxy, conf['country_to_port'])
    frontend.start()
    peer_server.stop()
    super_proxy.shutdown()
    connection_pool.close_all_connections()


if __name__ == '__main__':
    run(config)
