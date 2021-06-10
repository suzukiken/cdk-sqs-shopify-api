from datetime import datetime, timedelta
import json
import os
import boto3
import botocore
import uuid

TABLE_NAME = os.environ.get('TABLE_NAME')

config = botocore.config.Config(retries={'max_attempts': 10, 'mode': 'standard'})
resource = boto3.resource('dynamodb', config=config)
table = resource.Table(TABLE_NAME)

def lambda_handler(event, context):
  for record in event['Records']:
    if record['eventSource'] != "aws:sqs":
      continue
    
    print('action:rejected:{}'.format(record['body']))
    
    try:
      body = json.loads(record['body'])
    except:
      body = record['body']
      
    item = {
      'id': record['messageId'],
      'error': record['messageId'],
      'body': body,
      'batch': body['batch'],
      'epoch': int(datetime.now().timestamp() * 1000)
    }
    
    print(item)
    
    response = table.put_item(Item=item)
    
    print(item)
    