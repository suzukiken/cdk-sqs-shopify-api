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
SHOPIFY_PASSWORD = os.environ.get('SHOPIFY_PASSWORD')
SHOPIFY_SHOP = os.environ.get('SHOPIFY_SHOP')
SHOPIFY_GRAPHQL_URL = '{}.myshopify.com'.format(SHOPIFY_SHOP)

TABLE_NAME = os.environ.get('TABLE_NAME')

config = botocore.config.Config(retries={'max_attempts': 10, 'mode': 'standard'})
resource = boto3.resource('dynamodb', config=config)
table = resource.Table(TABLE_NAME)

session = shopify.Session(SHOPIFY_GRAPHQL_URL, SHOPIFY_VERSION, SHOPIFY_PASSWORD)
shopify.ShopifyResource.activate_session(session)

def lambda_handler(event, context):
  print(event)
  
  for record in event['Records']:
    
    start = datetime.now()
    
    costs = []
    
    SKU = random.randint(1, 99999)
    PCS = random.randint(1, 10)
    
    # 商品を登録する
    
    tempstr_create = """
      mutation {
        productCreate(input: {
          title: "テスト商品"
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
        }
      }
    """
    
    gqlstr = Template(tempstr_create).substitute(sku=SKU)
    res = shopify.GraphQL().execute(gqlstr)
    
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
    
    inventory_item_query = Template(template_inventory_item).substitute(
      sku=SKU
    )
    
    res = shopify.GraphQL().execute(inventory_item_query)
    
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
          userErrors {
            field
            message
          }
        }
      }
    """
    
    inventory_adjust_query = Template(template_inventory_adjust).substitute(
      graphqlid_level=graphqlid_level,
      pcs=PCS
    )
    
    res = shopify.GraphQL().execute(inventory_adjust_query)
    
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
    
    available_query = Template(template_available).substitute(graphqlid_item=graphqlid_item)
    
    res = shopify.GraphQL().execute(available_query)
    
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
        
    template_query = Template(template_delete).substitute(graphqlid_product=graphqlid_product)
    
    res = shopify.GraphQL().execute(template_query)
    
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
      'batch': record['body'],
      'epoch': int(datetime.now().timestamp() * 1000),
      'total': int(total),
      'costs': recosts,
      'available': int(available),
      'duration': duration
    }
    
    print(item)
    
    response = table.put_item(Item=item)
    print(response)