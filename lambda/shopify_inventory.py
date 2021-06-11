import shopify
from datetime import datetime, timedelta
import json
from string import Template
import os
from pprint import pprint
import random
import boto3
import botocore
import uuid

SHOPIFY_VERSION = '2020-10'

TABLE_NAME = os.environ.get('TABLE_NAME')

config = botocore.config.Config(retries={'max_attempts': 10, 'mode': 'standard'})
resource = boto3.resource('dynamodb', config=config)
table = resource.Table(TABLE_NAME)

class ShopifyApiError(Exception):
  def __init__(self, message, graphql, response):
    self.message = graphql
    self.graphql = graphql
    self.response = response
    
def raiseIfError(graphql, response):
  try:
    resdic = json.loads(response)
  except:
    raise ShopifyApiError('failed to parse as json', graphql.replace('\n', ' '), response)
  if 'errors' in resdic:
    message = resdic['errors'][0].get('message', 'no message')
    raise ShopifyApiError(message, graphql.replace('\n', ' '), response)
  if 'userErrors' in resdic:
    if resdic['userErrors']:
      message = resdic['userErrors'][0].get('message', 'no message')
      raise ShopifyApiError(message, graphql.replace('\n', ' '), response)
  

def lambda_handler(event, context):
  print(event)
  
  for record in event['Records']:
    
    response = table.get_item(Key={
      'id': record['messageId']
    })
    
    print(response)
    
    if 'Item' in response:
      response = table.update_item(Key={
          'id': record['messageId']
        },
        UpdateExpression='SET again = again + :one',
        ExpressionAttributeValues={
          ':one': 1
        }
      )
      print(response)
      continue
    
    body = json.loads(record['body'])
    
    if body['shop'] == 'figmentresearchshop1':
      SHOPIFY_PASSWORD = os.environ.get('SHOPIFY_PASSWORD_DEV')
      SHOPIFY_SHOP = os.environ.get('SHOPIFY_SHOP_DEV')
    else:
      SHOPIFY_PASSWORD = os.environ.get('SHOPIFY_PASSWORD_PROD')
      SHOPIFY_SHOP = os.environ.get('SHOPIFY_SHOP_PROD')
      
    SHOPIFY_GRAPHQL_URL = '{}.myshopify.com'.format(SHOPIFY_SHOP)
    session = shopify.Session(SHOPIFY_GRAPHQL_URL, SHOPIFY_VERSION, SHOPIFY_PASSWORD)
    shopify.ShopifyResource.activate_session(session)
    
    start = datetime.now()
    
    costs = []
    
    SKU = random.randint(1, 99999)
    PCS = random.randint(1, 10)
    
    # 商品を登録する
    
    title = 'title-{}'.format(SKU)
    
    tempstr_create = """
      mutation {
        productCreate(input: {
          title: "${title}"
          variants: {
            sku: "$sku"
            inventoryManagement: SHOPIFY
          }
        }) {
          product {
            id
            variants(first: 1) {
              edges {
                node {
                  id
                  inventoryItem {
                    id
                    inventoryLevels(first: 1) {
                      edges {
                        node {
                          id
                        }
                      }
                    }
                  }
                }
              }
            }
          }
          userErrors {
            field
            message
          }
        }
      }
    """
    
    gqlstr = Template(tempstr_create).substitute(sku=SKU, title=title)
    print(gqlstr.replace('\n', ' '))
    res = shopify.GraphQL().execute(gqlstr)
    print(res)
    
    raiseIfError(gqlstr, res)
    
    resdir = json.loads(res)
    graphqlid_product = resdir['data']['productCreate']['product']['id']
    graphqlid_variant = resdir['data']['productCreate']['product']['variants']['edges'][0]['node']['id']
    graphqlid_item = resdir['data']['productCreate']['product']['variants']['edges'][0]['node']['inventoryItem']['id']
    graphqlid_level = resdir['data']['productCreate']['product']['variants']['edges'][0]['node']['inventoryItem']['inventoryLevels']['edges'][0]['node']['id']
    print(resdir)
    
    cost = resdir['extensions']['cost']
    print(cost)
    
    costs.append(cost)
    
    # SKUで商品を見つける
    
    template_inventory_item = """
    {
      inventoryItems(first: 1, query: "sku:$sku") {
        edges {
          node {
            inventoryLevels(first:1) {
              edges {
                node {
                  id
                }
              }
            }
          }
        }
      }
    }
    """
    
    gqlstr = Template(template_inventory_item).substitute(
      sku=SKU
    )
    
    print(gqlstr.replace('\n', ' '))
    res = shopify.GraphQL().execute(gqlstr)
    print(res)
    
    raiseIfError(gqlstr, res)
    
    resdir = json.loads(res)
    print(resdir)
    
    graphqlid_level = resdir['data']['inventoryItems']['edges'][0]['node']['inventoryLevels']['edges'][0]['node']['id']
    
    cost = resdir['extensions']['cost']
    print(cost)
    
    costs.append(cost)
    
    # 在庫数を変更する
    
    template_inventory_adjust = """
      mutation {
        inventoryAdjustQuantity(input: {
          inventoryLevelId: "$graphqlid_level",
          availableDelta: $pcs
        }) {
          inventoryLevel {
            id
            item {
              sku
              variant {
                displayName
              }
            }
          }
        }
      }
    """
    
    gqlstr = Template(template_inventory_adjust).substitute(
      graphqlid_level=graphqlid_level,
      pcs=PCS
    )
    
    print(gqlstr.replace('\n', ' '))
    res = shopify.GraphQL().execute(gqlstr)
    print(res)
    
    raiseIfError(gqlstr, res)
    
    resdir = json.loads(res)
    print(resdir)
    
    cost = resdir['extensions']['cost']
    print(cost)
    
    costs.append(cost)
    
    # shopifyの在庫数を確認する
    
    template_available = """
    {
      inventoryItems(first: 1, query: "id=$graphqlid_item") {
        edges {
          node {
            inventoryLevels(first:1) {
              edges {
                node {
                  available
                }
              }
            }
          }
        }
      }
    }
    """
    
    gqlstr = Template(template_available).substitute(graphqlid_item=graphqlid_item)
    
    print(gqlstr.replace('\n', ' '))
    res = shopify.GraphQL().execute(gqlstr)
    print(res)
    
    raiseIfError(gqlstr, res)
    
    resdir = json.loads(res)
    print(resdir)
    
    cost = resdir['extensions']['cost']
    print(cost)
    
    costs.append(cost)
    
    # 商品を削除する
    
    template_delete = """
      mutation {
        productDelete(input: {
          id: "$graphqlid_product"
        }) {
          shop {
            id
          }
          userErrors {
            field
            message
          }
        }
      }
    """
        
    gqlstr = Template(template_delete).substitute(graphqlid_product=graphqlid_product)
    
    print(gqlstr.replace('\n', ' '))
    res = shopify.GraphQL().execute(gqlstr)
    print(res)
    
    raiseIfError(gqlstr, res)
    
    resdir = json.loads(res)
    print(resdir)
    
    cost = resdir['extensions']['cost']
    print(cost)
    
    available = cost['throttleStatus']['currentlyAvailable']
    
    costs.append(cost)
    
    total = 0
    recosts = []
    
    for cost in costs:
      total += cost['actualQueryCost']
      recosts.append({
        'requested': cost['requestedQueryCost'],
        'actual': cost['actualQueryCost'],
        'available': cost['throttleStatus']['currentlyAvailable']
      })
    
    duration = int((datetime.now().timestamp() - start.timestamp()) * 1000)
    
    item = {
      'id': record['messageId'],
      'batch': body['batch'],
      'epoch': int(datetime.now().timestamp() * 1000),
      'total': int(total),
      'costs': recosts,
      'available': int(available),
      'duration': duration,
      'shop': SHOPIFY_SHOP,
      'again': 1
    }
    
    print(item)
    
    response = table.put_item(Item=item)
    print(response)