from qka.adapters.server import QMTServer

server = QMTServer(account_id='55003152', mini_qmt_path=r'D:\国金QMT交易端模拟\userdata_mini')
server.start()