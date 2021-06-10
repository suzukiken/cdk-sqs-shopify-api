import boto3
import os
import sys
import json
from datetime import datetime

client = boto3.client('s3')
sts = boto3.client('sts')

caller_identity = sts.get_caller_identity()
account = caller_identity['Account']

sqs = boto3.resource('sqs')

QUEUE_NAME = os.environ.get('QUEUE_NAME')

def main(args):
    
    maxcount = int(args[1])
    body = json.dumps({
        'batch': str(int(datetime.now().timestamp())),
        'shop': 'figmentresearchshop1' # figmentresearchshop1 figmentres
    })

    QUEUE_URL = 'https://sqs.ap-northeast-1.amazonaws.com/{}/{}'.format(account, QUEUE_NAME)
    queue = sqs.Queue(QUEUE_URL)
    
    count = 0
    
    while True:
        response = queue.send_message(MessageBody=body)
        
        print(response)

        count += 1
        if maxcount <= count:
            break

if __name__ == "__main__":
    main(sys.argv)