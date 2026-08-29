import os
import redis
import requests

REDIS_URL = os.getenv('REDIS_URL')
API_URL = os.getenv('SERVICE_API_URL')

if __name__ == '__main__':
    print('worker started')
    print(REDIS_URL)
    print(API_URL)
