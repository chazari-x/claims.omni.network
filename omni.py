import random
import threading
from queue import Queue
import requests
import urllib3
from progress.bar import IncrementalBar
from pyuseragents import random as random_useragent
import time

urllib3.disable_warnings()

def load_proxies(fp: str):
    if fp == "": fp = "prx.txt"

    proxies = []
    with open(file=fp, mode="r", encoding="utf-8") as File:
        lines = File.read().split("\n")
    for line in lines:
        try:
            if line != "": proxies.append(f"http://{line}")
        except ValueError:
            pass

    if proxies.__len__() < 1:
        raise Exception("can't load empty proxies file!")

    print("{} proxies loaded successfully!".format(proxies.__len__()))

    return proxies

class PrintThread(threading.Thread):
    def __init__(self, queue, file: str):
        threading.Thread.__init__(self)
        self.queue = queue
        self.file = file

    def printfiles(self, addr: str, file: str):
        with open(file, "a", encoding="utf-8") as ff:
            ff.write(addr)

    def run(self):
        while True:
            self.printfiles(self.queue.get(), self.file)
            self.queue.task_done()

class ProcessThread(threading.Thread):
    def __init__(self, in_queue, out_queue):
        threading.Thread.__init__(self)
        self.in_queue = in_queue
        self.out_queue = out_queue

    def run(self):
        while True:
            response = self.func(self.in_queue.get())
            if response != "": self.out_queue.put(response)
            self.in_queue.task_done()

    def func(self, addr: str):
        queryId = ""
        while queryId == "":
            try:
                with proxy_pool_lock:
                    if proxy_pool:
                        selected_proxy = proxy_pool.pop(0)
                    else:
                        print("Proxy pool is empty\n")
                        continue

                sess = requests.session()
                sess.proxies = {'all': selected_proxy}
                sess.headers = {
                    'user-agent': random_useragent(),
                    'accept': '*/*',
                    "Content-Type": "application/json"
                }
                sess.verify = False 
                ss = sess.post(f'https://claims.omni.network/clique-omni-issuer-node/credentials', 
                               json = {
                                   "pipelineVCName": "omniEcosystemScore",
                                   "identifier": addr,
                                   "params": {
                                       "walletAddresses": [addr]
                                       }
                                    }
                                )
                if ss.status_code == 200: 
                    if ss.json(): 
                        queryId = ss.json()['queryId']
                elif ss.json():
                    print(ss.json())
                    continue
            except Exception as e:
                if f"{e}" != "Expecting value: line 1 column 1 (char 0)":
                    print(f"\n{e}")
                with proxy_pool_lock:
                    proxy_pool.append(selected_proxy)
                pass
        try:
            str = self.cred(queryId, sess)
            bar.next()
            if str != "": return f'{addr} | {str}\n'
            return ""
        finally:
            with proxy_pool_lock:
                proxy_pool.append(selected_proxy)

    def cred(self, queryId: str, sess):
        while True:
            try:
                time.sleep(2)
                ss = sess.get(f'https://claims.omni.network/clique-omni-issuer-node/credentials/{queryId}')
                if ss.status_code == 200: 
                    if ss.json(): 
                        if ss.json()['status'] == 'Complete':
                            if ss.json()['data']['pipelines']['numOmniOATsHeld'] == 0 and ss.json()['data']['pipelines']['tokenQualified'] == 0:
                                return ""
                            elif ss.json()['data']['pipelines']['numOmniOATsHeld'] == ss.json()['data']['pipelines']['tokenQualified']:
                                return f'{ss.json()["data"]["pipelines"]["numOmniOATsHeld"]}'
                            str = ""
                            if ss.json()['data']['pipelines']['numOmniOATsHeld'] != 0:  str = f'numOmniOATsHeld: {ss.json()["data"]["pipelines"]["numOmniOATsHeld"]}'
                            if ss.json()['data']['pipelines']['tokenQualified'] != 0:  
                                if str != "": str += f' | tokenQualified: {ss.json()["data"]["pipelines"]["tokenQualified"]}'
                                else: str = f'tokenQualified: {ss.json()["data"]["pipelines"]["tokenQualified"]}'
                            return str
                elif ss.json():
                    print(ss.json())
            except Exception as e:
                if f"{e}" != "Expecting value: line 1 column 1 (char 0)":
                    print(f"\n{e}")
                pass

proxy_pool = load_proxies(input('Path to proxies: '))
# proxy_pool = load_proxies('prx.txt')
proxy_pool_lock = threading.Lock()

file = input('\nPath to file with adr: ')
# file = 'adr.txt'

with open(file, encoding="utf-8") as f:
    mnemonics = f.read().splitlines()

print(f'Loaded {len(mnemonics)} address')

threads = int(input('\nMax threads: '))
# threads = 100

path_to_save = input('\nPath to save: ')
# path_to_save = "hhhhhh.txt"

bar = IncrementalBar('Progress', max=len(mnemonics), suffix="%(index)d/%(max)d - %(elapsed_td)s")

print('\nstarted\n')

pathqueue = Queue()
resultqueue = Queue()

# spawn threads to process
for i in range(0, threads):
    t = ProcessThread(pathqueue, resultqueue)
    t.daemon = True
    t.start()

# spawn threads to print
t = PrintThread(resultqueue, path_to_save)
t.daemon = True
t.start()

# add paths to queue
for path in mnemonics:
    pathqueue.put(path)

# wait for queue to get empty
pathqueue.join()
resultqueue.join()